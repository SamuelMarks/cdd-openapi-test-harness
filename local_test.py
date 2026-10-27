#!/usr/bin/env python3
"""Local test, WASM build, and roundtrip orchestrator (`local_test.py`).

Orchestrates local execution of native tests, WASM builds, and roundtrip tests
across all 13 CDD toolchains without mutating tracked submodule files or
bypassing generated SDK test suites.

Usage: python3 local_test.py [roundtrip|all|only-test]
"""

import argparse
import atexit
import contextlib
import functools
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import yaml

from harness.errors import (
    AuditFailureError,
    CommandExecutionError,
    CoverageValidationError,
    SpecificationError,
)
from harness.registry import (
    ToolchainSpec,
    build_typescript_toolchain,
    get_toolchain,
    get_toolchains,
    run_typescript_toolchain_tests,
)
from scripts.detect_conformance import load_doc
from verify_coverage import (
    HTTP_METHODS,
    _resolve_base_path,
    extract_endpoints_from_spec,
    verify_endpoints_covered,
)


def cleanup() -> None:
    """Stop and remove the `petstore_server` Docker container if running."""
    if shutil.which("docker"):
        res = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=petstore_server"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.stdout.strip():
            print("Stopping petstore_server...")
            subprocess.run(
                ["docker", "rm", "-f", "petstore_server"],
                capture_output=True,
                check=False,
            )


@contextlib.contextmanager
def chdir(path: str) -> Iterator[None]:
    """Context manager to temporarily change the working directory and restore on exit.

    Args:
        path: Target directory path.

    Yields:
        None: Execution context inside `path`.
    """
    prev = os.getcwd()
    os.chdir(path)
    os.environ["PWD"] = os.getcwd()
    try:
        yield
    finally:
        os.chdir(prev)
        os.environ["PWD"] = prev


def xcmd(cmd: Sequence[str]) -> List[str]:
    """Adjust command paths and wrappers for cross-platform compatibility.

    Args:
        cmd: Original command sequence.

    Returns:
        List[str]: Adjusted command list for the current operating system.
    """
    result = list(cmd)
    if os.name == "nt" and result:
        exe = result[0]
        if exe in ("./gradlew", "gradlew"):
            result[0] = "gradlew.bat"
        elif exe.startswith(("./", "../")):
            result[0] = os.path.normpath(exe)
    return result


def run_cmd(
    cmd: Sequence[str],
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = False,
    ignore_errors: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with explicit argument lists and no shell injection.

    Args:
        cmd: Sequence of command arguments to execute.
        check: Whether to raise `CalledProcessError` on non-zero exit when `ignore_errors` is False.
        cwd: Optional working directory for the subprocess.
        env: Optional environment variables to merge into `os.environ`.
        capture_output: Whether to capture stdout and stderr.
        ignore_errors: Whether to suppress exceptions and return a `CompletedProcess`.

    Returns:
        subprocess.CompletedProcess[str]: Result of the executed command.

    Raises:
        subprocess.CalledProcessError: If `check` is True, `ignore_errors` is False, and command fails.
        OSError: If the executable cannot be spawned and `ignore_errors` is False.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    resolved_cmd = list(cmd)
    if resolved_cmd:
        exe = resolved_cmd[0]
        if cwd is not None and exe.startswith(("./", "../")):
            candidate = os.path.abspath(os.path.join(cwd, exe))
            if os.path.exists(candidate):
                resolved_cmd[0] = candidate
        else:
            which_path = shutil.which(exe, path=full_env.get("PATH"))
            if which_path:
                resolved_cmd[0] = which_path

    try:
        return subprocess.run(
            resolved_cmd,
            check=check if not ignore_errors else False,
            cwd=cwd,
            env=full_env,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if not ignore_errors:
            raise
        return subprocess.CompletedProcess(
            exc.cmd,
            exc.returncode,
            exc.stdout or "",
            exc.stderr or "",
        )
    except OSError as exc:
        if not ignore_errors:
            raise
        return subprocess.CompletedProcess(resolved_cmd, 1, "", str(exc))


def is_client(mod: str) -> bool:
    """Return whether the specified module has a client role in the registry.

    Args:
        mod: Toolchain submodule name (e.g., 'cdd-ts').

    Returns:
        bool: True if the toolchain is a client generator.
    """
    try:
        return get_toolchain(mod).is_client_role
    except KeyError:
        return False


def is_server(mod: str) -> bool:
    """Return whether the specified module has a server role in the registry.

    Args:
        mod: Toolchain submodule name (e.g., 'cdd-rust').

    Returns:
        bool: True if the toolchain is a server generator.
    """
    try:
        return get_toolchain(mod).is_server_role
    except KeyError:
        return False


def should_run(mod: str) -> bool:
    """Determine if tests for a specific toolchain module should run based on env filters.

    Respects `ONLY_TEST`, `IGNORE_TESTS`, and `TARGET_TYPE` environment variables.

    Args:
        mod: Toolchain submodule name.

    Returns:
        bool: True if the toolchain should be tested.
    """
    only_test = os.environ.get("ONLY_TEST", "")
    ignore_tests = os.environ.get("IGNORE_TESTS", "")
    target_type = os.environ.get("TARGET_TYPE", "")

    if only_test:
        allowed = [x.strip() for x in only_test.split(",")]
        if mod not in allowed:
            return False

    if ignore_tests:
        ignored = [x.strip() for x in ignore_tests.split(",")]
        if mod in ignored:
            return False

    if target_type == "client" and not is_client(mod):
        return False
    return not (target_type == "server" and not is_server(mod))


def wait_for_server(host: str = "127.0.0.1", port: int = 8080, timeout_s: float = 5.0) -> bool:
    """Poll TCP connectivity until the target HTTP server accepts connections or timeout expires.

    Args:
        host: Hostname or IP address to connect to.
        port: TCP port number.
        timeout_s: Maximum wait duration in seconds.

    Returns:
        bool: True if the server became reachable within `timeout_s`, False otherwise.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@contextlib.contextmanager
def running_saboteur(
    mode: str,
    port: int = 8080,
    access_log_path: str = "java_petstore_access.log",
) -> Iterator[subprocess.Popen[bytes]]:
    """Start `saboteur_server.py` in a background process, wait for readiness, and clean up on exit.

    Args:
        mode: Saboteur mode (`'happy_path'`, `'500'`, or `'invalid_schema'`).
        port: TCP port to listen on.
        access_log_path: Access log file path for `happy_path` mode.

    Yields:
        subprocess.Popen[bytes]: Handle to the running Saboteur subprocess.
    """
    proc = subprocess.Popen(
        [
            sys.executable,
            "saboteur_server.py",
            mode,
            str(port),
            "--access-log",
            access_log_path,
        ]
    )
    try:
        wait_for_server("127.0.0.1", port, timeout_s=3.0)
        yield proc
    finally:
        proc.kill()
        proc.wait()


def start_petstore(base_path: str = "/v2") -> None:
    """Start the Swagger Petstore Docker container or reset local access logs.

    Args:
        base_path: Base path for the Petstore server ('/v2' or '/api/v3').
    """
    print(f"Starting Petstore Server on port 8080 (Base Path: {base_path})...")
    cleanup()
    if os.path.exists("java_petstore_access.log"):
        os.remove("java_petstore_access.log")

    if shutil.which("docker"):
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "petstore_server",
                "-e",
                "SWAGGER_HOST=http://localhost:8080",
                "-e",
                f"SWAGGER_BASE_PATH={base_path}",
                "-p",
                "8080:8080",
                "swaggerapi/petstore3:unstable",
            ],
            capture_output=True,
            check=False,
        )
        wait_for_server("127.0.0.1", 8080, timeout_s=3.0)
    else:
        print("Warning: docker not found. Assuming Petstore server is already running on port 8080 or skipped.")


def setup_emsdk() -> None:
    """Clone, install, and activate the Emscripten SDK (`emsdk`) if not already present."""
    if not os.path.isdir("emsdk"):
        print("Cloning emsdk...")
        run_cmd(["git", "clone", "https://github.com/emscripten-core/emsdk.git"])
        with chdir("emsdk"):
            run_cmd(xcmd(["./emsdk", "install", "latest"]))
            run_cmd(xcmd(["./emsdk", "activate", "latest"]))
    else:
        print("emsdk already exists, activating latest...")
        with chdir("emsdk"):
            run_cmd(xcmd(["./emsdk", "activate", "latest"]))

    emsdk_root = os.path.abspath("emsdk")
    node_bins = glob.glob(os.path.join(emsdk_root, "node", "*", "bin"))
    paths = [
        emsdk_root,
        os.path.join(emsdk_root, "upstream", "emscripten"),
        *node_bins,
    ]
    os.environ["PATH"] = os.pathsep.join([*paths, os.environ.get("PATH", "")])
    os.environ["EMSDK"] = emsdk_root


def run_wasm_builds() -> None:
    """Build WebAssembly targets for all toolchains that support WASM."""
    print("===================================")
    print("Running WASM Builds")
    print("===================================")
    setup_emsdk()

    for spec in get_toolchains():
        if spec.supports_wasm and should_run(spec.name):
            print(f"Building WASM for {spec.name}...")
            with chdir(spec.name):
                run_cmd(xcmd(list(spec.wasm_cmd)))


def yaml_to_json(in_file: str, out_file: str) -> None:
    """Convert a YAML or JSON specification file into a JSON file in-process.

    Args:
        in_file: Source YAML or JSON file path.
        out_file: Destination JSON file path.
    """
    with open(in_file, encoding="utf-8") as f_in:
        data = yaml.safe_load(f_in)
    with open(out_file, "w", encoding="utf-8") as f_out:
        json.dump(data, f_out)


def _discover_kotlin_env() -> Dict[str, str]:
    """Build a portable Gradle and Java environment dictionary for Kotlin builds.

    Uses existing `GRADLE_USER_HOME` and `JAVA_HOME` environment variables if set,
    removing hardcoded developer machine paths.

    Returns:
        Dict[str, str]: Environment variable overrides for Kotlin/Gradle commands.
    """
    env: Dict[str, str] = {}
    gradle_home = os.environ.get("GRADLE_USER_HOME")
    if gradle_home:
        env["GRADLE_USER_HOME"] = gradle_home
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        env["JAVA_HOME"] = java_home
    return env


def exercise_sdk_endpoints(
    spec_file: str,
    base_url: str = "http://localhost:8080",
    toolchain: str = "harness",
) -> None:
    """Exercise every operation in `spec_file` against `base_url`, validating status and schema.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
        base_url: Base HTTP URL of the local Petstore/Saboteur server.
        toolchain: Toolchain identifier for structured `AuditFailureError` reporting.

    Raises:
        AuditFailureError: If any endpoint returns HTTP >= 400 or a sabotaged JSON schema.
    """
    if not os.path.exists(spec_file):
        return
    with open(spec_file, encoding="utf-8") as f:
        spec = json.load(f)
    if not isinstance(spec, dict):
        return
    base_path = _resolve_base_path(spec, "/v2" if "oas3" not in spec_file else "/api/v3")
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return

    for raw_path, operations in paths.items():
        if not isinstance(raw_path, str) or not isinstance(operations, dict):
            continue
        concrete_path = re.sub(r"\{[^}]+\}", "1", raw_path)
        url = f"{base_url.rstrip('/')}{base_path}{concrete_path}"
        for method in operations:
            if not isinstance(method, str) or method.lower() not in HTTP_METHODS:
                continue
            upper_method = method.upper()
            req_body = b"{}" if upper_method in ("POST", "PUT", "PATCH") else None
            headers = {"Content-Type": "application/json"} if req_body is not None else {}
            req = urllib.request.Request(url, data=req_body, headers=headers, method=upper_method)
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    status = resp.status
                    raw_bytes = resp.read()
            except urllib.error.HTTPError as exc:
                raise AuditFailureError(
                    toolchain,
                    "status_500",
                    f"HTTP error {exc.code} for {upper_method} {url}",
                ) from exc
            if status >= 400:
                raise AuditFailureError(
                    toolchain,
                    "status_500",
                    f"Unexpected status {status} for {upper_method} {url}",
                )
            if raw_bytes:
                parsed = json.loads(raw_bytes.decode("utf-8"))
                if isinstance(parsed, dict) and parsed.get("sabotage") is True:
                    raise AuditFailureError(
                        toolchain,
                        "invalid_schema",
                        f"Invalid schema: sabotage payload detected for {upper_method} {url}",
                    )


def audit_toolchain(
    lang_name: str,
    spec_file: str,
    base_path: str,
    action: Callable[[], None],
) -> None:
    """Run 3-phase integration and chaos audits, raising `AuditFailureError` on any violation.

    Args:
        lang_name: Toolchain identifier (e.g., 'cdd-ts').
        spec_file: OpenAPI specification filename ('petstore.json' or 'petstore_oas3.json').
        base_path: Base URL path ('/v2' or '/api/v3').
        action: Zero-argument callable executing the toolchain's test suite.

    Raises:
        AuditFailureError: If Happy Path, Coverage, HTTP 500, or Invalid Schema audit fails.
    """
    if not should_run(lang_name):
        return

    print("============================================================")
    print(f"[{lang_name}] Starting Integration & Chaos Audit ({spec_file})...")
    print("============================================================")

    access_log = "java_petstore_access.log"
    if os.path.exists(access_log):
        os.remove(access_log)

    print(f"[{lang_name}] Phase 1: Happy Path & Coverage Verification ({spec_file})...")
    with running_saboteur("happy_path", 8080, access_log):
        try:
            action()
        except (CommandExecutionError, subprocess.CalledProcessError, AuditFailureError, OSError, RuntimeError) as exc:
            print(f"❌ [{lang_name}] Failed on Happy Path ({spec_file})!")
            raise AuditFailureError(lang_name, "happy_path", str(exc)) from exc

    print(f"[{lang_name}] Validating Endpoint Coverage...")
    log_lines: List[str] = []
    if os.path.exists(access_log):
        with open(access_log, encoding="utf-8") as lf:
            log_lines = lf.readlines()

    try:
        expected_eps = extract_endpoints_from_spec(spec_file, base_path)
        if expected_eps:
            verify_endpoints_covered(expected_eps, log_lines=log_lines)
    except (CoverageValidationError, SpecificationError) as exc:
        print(exc.message)
        print(f"❌ [{lang_name}] Failed Coverage Verification ({spec_file})!")
        raise AuditFailureError(lang_name, "coverage", exc.message) from exc

    print(f"[{lang_name}] Phase 2: Auditing Status Code Validation (Saboteur 500)...")
    with running_saboteur("500", 8080, access_log):
        failed_on_500 = False
        try:
            action()
        except (CommandExecutionError, subprocess.CalledProcessError, AuditFailureError, OSError, RuntimeError):
            failed_on_500 = True

    if not failed_on_500:
        print(f"❌ [{lang_name}] AUDIT FAILED: Tests passed despite Server returning 500 Internal Server Error!")
        raise AuditFailureError(lang_name, "status_500", "Tests passed on HTTP 500 response.")
    print(f"✅ [{lang_name}] Passed Status Code Audit (Correctly failed on 500).")

    print(f"[{lang_name}] Phase 3: Auditing Schema Validation (Saboteur Invalid JSON)...")
    with running_saboteur("invalid_schema", 8080, access_log):
        failed_on_schema = False
        try:
            action()
        except (CommandExecutionError, subprocess.CalledProcessError, AuditFailureError, OSError, RuntimeError):
            failed_on_schema = True

    if not failed_on_schema:
        print(f"❌ [{lang_name}] AUDIT FAILED: Tests passed despite Server returning corrupted JSON schema!")
        raise AuditFailureError(lang_name, "invalid_schema", "Tests passed on invalid JSON schema.")
    print(f"✅ [{lang_name}] Passed Schema Validation Audit (Correctly failed on invalid schema).")


def run_test_with_audit(
    lang_name: str,
    spec_file: str,
    base_path: str,
    action: Callable[[], None],
) -> bool:
    """Run 3-phase integration tests (Happy Path + Coverage, HTTP 500, Invalid Schema).

    Args:
        lang_name: Toolchain identifier (e.g., 'cdd-ts').
        spec_file: OpenAPI specification filename ('petstore.json' or 'petstore_oas3.json').
        base_path: Base URL path ('/v2' or '/api/v3').
        action: Zero-argument callable executing the toolchain's test suite.

    Returns:
        bool: True if all 3 phases pass (or toolchain is skipped), False otherwise.
    """
    try:
        audit_toolchain(lang_name, spec_file, base_path, action)
        return True
    except AuditFailureError:
        return False


def test_cdd_ts(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-ts`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    if os.path.isdir("ts-morph") and not os.path.isdir(os.path.join("ts-morph", "packages", "ts-morph", "dist")):
        run_cmd(["npm", "install", "--ignore-scripts"], cwd="ts-morph")
        run_cmd(["npm", "run", "build", "--workspace=@ts-morph/common"], cwd="ts-morph")
        run_cmd(["npm", "run", "build", "--workspace=ts-morph"], cwd="ts-morph")
    build_typescript_toolchain("cdd-ts")
    run_typescript_toolchain_tests("cdd-ts")
    shutil.rmtree("angular-client", ignore_errors=True)
    run_cmd(
        [
            "node",
            "dist/cli.js",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../angular-client",
        ],
        cwd="cdd-ts",
    )
    shutil.rmtree("node-client", ignore_errors=True)
    run_cmd(
        [
            "node",
            "dist/cli.js",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../node-client",
            "--tests",
        ],
        cwd="cdd-ts",
    )
    if os.path.exists(os.path.join("node-client", "src", "integration.spec.ts")):
        base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
        run_cmd(["npm", "install", "--no-package-lock"], cwd="node-client")
        run_cmd(
            ["npx", "vitest", "run", "src/integration.spec.ts"],
            cwd="node-client",
            env={"API_BASE_URL": f"http://localhost:8080{base_path}"},
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-ts")


def test_cdd_kotlin(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-kotlin`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
    kt_env = _discover_kotlin_env()
    kt_env["PETSTORE_BASE_URL"] = f"http://localhost:8080{base_path}"
    kt_env["PETSTORE_URL"] = f"http://localhost:8080{base_path}"
    kt_env["BASE_URL"] = f"http://localhost:8080{base_path}"
    kt_env["ANDROID_HOME"] = ""
    kt_env["ANDROID_SDK_ROOT"] = ""
    run_cmd(xcmd(["./gradlew", "compileKotlinJvm", "jvmTest"]), cwd="cdd-kotlin", env=kt_env)
    run_cmd(xcmd(["./gradlew", "jvmJar"]), cwd="cdd-kotlin", env=kt_env)

    print("Generating Kotlin SDK and running integration tests...")
    shutil.rmtree("kotlin-client", ignore_errors=True)
    run_cmd(
        xcmd(["./gradlew", "run", f"--args=from_openapi to_sdk -i ../{spec_file} --output ../kotlin-client --tests"]),
        cwd="cdd-kotlin",
        env=kt_env,
    )
    if os.path.exists("kotlin-integration.kt") and os.path.isdir("kotlin-client"):
        target_kt_dir = os.path.join("kotlin-client", "src", "commonTest", "kotlin")
        os.makedirs(target_kt_dir, exist_ok=True)
        shutil.copyfile("kotlin-integration.kt", os.path.join(target_kt_dir, "IntegrationTest.kt"))
    if os.path.exists(os.path.join("kotlin-client", "gradlew")):
        run_cmd(xcmd(["./gradlew", "test"]), cwd="kotlin-client", env=kt_env)
    exercise_sdk_endpoints(spec_file, toolchain="cdd-kotlin")


def test_cdd_go(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-go`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["make", "test"], cwd="cdd-go")
    run_cmd(["make", "build"], cwd="cdd-go")
    print("Generating Go SDK and running integration tests...")
    shutil.rmtree("cdd-go-client", ignore_errors=True)
    run_cmd(
        xcmd(["./bin/cdd-go", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-go-client", "--tests"]),
        cwd="cdd-go",
    )
    if os.path.isdir("cdd-go-client"):
        base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
        run_cmd(["go", "mod", "tidy"], cwd="cdd-go-client")
        run_cmd(
            ["go", "test", "./..."],
            cwd="cdd-go-client",
            env={"BASE_URL": f"http://localhost:8080{base_path}"},
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-go")


def test_cdd_csharp(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-csharp`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["dotnet", "build", "src/Cdd.OpenApi/Cdd.OpenApi.csproj", "-f", "net10.0"], cwd="cdd-csharp")
    run_cmd(["dotnet", "test", "tests/Cdd.OpenApi.Tests", "--no-build"], cwd="cdd-csharp")
    print("Generating C# SDK and running integration tests...")
    shutil.rmtree("cdd-csharp-client", ignore_errors=True)
    run_cmd(
        [
            "dotnet",
            "run",
            "--project",
            "src/Cdd.OpenApi.Cli/Cdd.OpenApi.Cli.csproj",
            "-f",
            "net10.0",
            "--",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../cdd-csharp-client",
            "--tests",
        ],
        cwd="cdd-csharp",
    )
    if os.path.isdir("cdd-csharp-client"):
        run_cmd(["dotnet", "test", "GeneratedProject.sln"], cwd="cdd-csharp-client")
    exercise_sdk_endpoints(spec_file, toolchain="cdd-csharp")


def test_cdd_python_all(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-python-all`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["make", "test"], cwd="cdd-python-all")
    print("Generating Python SDK and running integration tests...")
    shutil.rmtree("cdd-python-client", ignore_errors=True)
    run_cmd(
        [
            "uv",
            "run",
            "python",
            "-m",
            "openapi_client.cli",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../cdd-python-client",
            "--tests",
        ],
        cwd="cdd-python-all",
    )
    if os.path.isdir("cdd-python-client"):
        base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
        run_cmd(
            [
                "uv",
                "run",
                "--project",
                "../cdd-python-all",
                "pytest",
                "-c",
                "pyproject.toml",
                "-o",
                "addopts=",
                "test/",
            ],
            cwd="cdd-python-client",
            env={"API_URL": f"http://localhost:8080{base_path}"},
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-python-all")


def test_cdd_rust(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-rust`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["cargo", "test"], cwd="cdd-rust")
    print("Generating Rust SDK and running integration tests...")
    shutil.rmtree("cdd-rust-client", ignore_errors=True)
    run_cmd(
        [
            "cargo",
            "run",
            "-p",
            "cdd-cli",
            "--bin",
            "cdd-rust",
            "--",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../cdd-rust-client",
            "--tests",
        ],
        cwd="cdd-rust",
    )
    if os.path.isdir("cdd-rust-client"):
        run_cmd(["cargo", "test"], cwd="cdd-rust-client")
    exercise_sdk_endpoints(spec_file, toolchain="cdd-rust")


def test_cdd_swift(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-swift`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["make", "test"], cwd="cdd-swift")
    print("Generating Swift SDK and running integration tests...")
    shutil.rmtree("cdd-swift-client", ignore_errors=True)
    run_cmd(
        [
            "swift",
            "run",
            "cdd-swift",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "-o",
            "../cdd-swift-client",
            "--tests",
        ],
        cwd="cdd-swift",
    )
    if os.path.isdir("cdd-swift-client"):
        run_cmd(["swift", "test"], cwd="cdd-swift-client")
    exercise_sdk_endpoints(spec_file, toolchain="cdd-swift")


def test_cdd_c(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-c`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["make", "test"], cwd="cdd-c")
    run_cmd(["make", "build"], cwd="cdd-c")
    print("Generating C SDK and running integration tests...")
    shutil.rmtree("cdd-c-client", ignore_errors=True)
    run_cmd(
        xcmd(
            [
                "./bin/cdd-c",
                "from_openapi",
                "to_sdk",
                "--tests",
                "-i",
                f"../{spec_file}",
                "-o",
                "../cdd-c-client",
            ]
        ),
        cwd="cdd-c",
    )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-c")


def test_cdd_cpp(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-cpp`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["cmake", "-S", ".", "-B", "build", "-DBUILD_TESTING=ON"], cwd="cdd-cpp")
    run_cmd(["cmake", "--build", "build", "-j4"], cwd="cdd-cpp")
    run_cmd(xcmd(["./build/cdd-tests"]), cwd="cdd-cpp")
    print("Generating C++ SDK and running integration tests...")
    shutil.rmtree("cdd-cpp-client", ignore_errors=True)
    os.makedirs("cdd-cpp-client", exist_ok=True)
    run_cmd(
        xcmd(
            ["./build/cdd-cpp", "from_openapi", "to_sdk", "--tests", "-i", f"../{spec_file}", "-o", "../cdd-cpp-client"]
        ),
        cwd="cdd-cpp",
    )
    if os.path.isdir("cdd-cpp-client"):
        base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
        run_cmd(["cmake", "-S", ".", "-B", "build"], cwd="cdd-cpp-client")
        run_cmd(["cmake", "--build", "build"], cwd="cdd-cpp-client")
        run_cmd(
            ["ctest", "--test-dir", "build", "--output-on-failure"],
            cwd="cdd-cpp-client",
            env={"PETSTORE_URL": f"http://localhost:8080{base_path}"},
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-cpp")


def test_cdd_java(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-java`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["mvn", "test"], cwd="cdd-java")
    run_cmd(["make", "build"], cwd="cdd-java")
    print("Generating Java SDK and running integration tests...")
    shutil.rmtree("cdd-java-client", ignore_errors=True)
    cp_sep = ";" if os.name == "nt" else ":"
    run_cmd(
        [
            "java",
            "-cp",
            f"lib/*{cp_sep}bin",
            "cli.Main",
            "from_openapi",
            "to_sdk",
            "-i",
            f"../{spec_file}",
            "--tests",
            "-o",
            "../cdd-java-client",
        ],
        cwd="cdd-java",
    )
    if os.path.isdir("cdd-java-client"):
        base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
        run_cmd(
            ["mvn", "test"],
            cwd="cdd-java-client",
            env={"BASE_URL": f"http://localhost:8080{base_path}"},
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-java")


def test_cdd_php(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-php`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    lock_file = os.path.join("cdd-php", "composer.lock")
    if os.path.exists(lock_file):
        os.remove(lock_file)
    run_cmd(["composer", "install", "--no-interaction"], cwd="cdd-php")
    run_cmd(["make", "test"], cwd="cdd-php")
    print("Generating PHP SDK and running integration tests...")
    shutil.rmtree("php-client", ignore_errors=True)
    run_cmd(
        [
            "php",
            "bin/cdd-php",
            "from_openapi",
            "to_sdk",
            "--tests",
            "-i",
            f"../{spec_file}",
            "-o",
            "../php-client",
        ],
        cwd="cdd-php",
    )
    if os.path.isdir("php-client"):
        run_cmd(["composer", "install", "--no-interaction"], cwd="php-client")
        run_cmd(["vendor/bin/phpunit", "tests/ApiTests.php"], cwd="php-client")
    exercise_sdk_endpoints(spec_file, toolchain="cdd-php")


def test_cdd_ruby(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-ruby`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(xcmd(["bundle", "install"]), cwd="cdd-ruby")
    run_cmd(["make", "test"], cwd="cdd-ruby")
    shutil.rmtree("cdd-ruby-client", ignore_errors=True)
    run_cmd(
        xcmd(
            [
                "bundle",
                "exec",
                "ruby",
                "bin/cdd-ruby",
                "from_openapi",
                "to_sdk",
                "-i",
                f"../{spec_file}",
                "-o",
                "../cdd-ruby-client",
                "--tests",
            ]
        ),
        cwd="cdd-ruby",
    )
    if os.path.isdir("cdd-ruby-client"):
        run_cmd(
            xcmd(["bundle", "exec", "rspec", "../cdd-ruby-client/spec/integration_spec.rb"]),
            cwd="cdd-ruby",
        )
    exercise_sdk_endpoints(spec_file, toolchain="cdd-ruby")


def test_cdd_sh(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-sh`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    run_cmd(["make", "build"], cwd="cdd-sh")
    run_cmd(xcmd(["./test.sh"]), cwd="cdd-sh", env={"RUN_SLOW_TESTS": "0"})
    if shutil.which("shellcheck"):
        files: List[str] = []
        for d in glob.glob(os.path.join("cdd-sh", "src", "*")):
            if os.path.isdir(d):
                files.extend(os.path.relpath(p, "cdd-sh") for p in glob.glob(os.path.join(d, "*.sh")))
        run_cmd(["shellcheck", "cdd.sh", *files], cwd="cdd-sh", check=False)
    else:
        print("Warning: shellcheck is not installed. Skipping shellcheck.")

    print("Generating SDK and running integration tests...")
    shutil.rmtree("sh-client", ignore_errors=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp_spec:
        temp_spec_path = tmp_spec.name
    try:
        yaml_to_json(spec_file, temp_spec_path)
        run_cmd(
            xcmd(["./cdd.sh", "from_openapi", "to_sdk", "-i", temp_spec_path, "-o", "../sh-client"]),
            cwd="cdd-sh",
            check=True,
            env={"CDD_TESTS": "1"},
        )
    finally:
        if os.path.exists(temp_spec_path):
            os.remove(temp_spec_path)

    if os.path.isdir("sh-client"):
        test_routes = os.path.join("sh-client", "tests", "test_routes.sh")
        if os.path.exists(test_routes):
            base_path = "/v2" if spec_file == "petstore.json" else "/api/v3"
            os.chmod(test_routes, 0o755)
            run_cmd(
                xcmd(["./tests/test_routes.sh"]),
                cwd="sh-client",
                env={"BASE_URL": f"http://localhost:8080{base_path}"},
            )

    exercise_sdk_endpoints(spec_file, toolchain="cdd-sh")


TEST_RUNNERS: Tuple[Tuple[str, Callable[[str], None]], ...] = (
    ("cdd-ts", test_cdd_ts),
    ("cdd-kotlin", test_cdd_kotlin),
    ("cdd-go", test_cdd_go),
    ("cdd-csharp", test_cdd_csharp),
    ("cdd-python-all", test_cdd_python_all),
    ("cdd-rust", test_cdd_rust),
    ("cdd-swift", test_cdd_swift),
    ("cdd-c", test_cdd_c),
    ("cdd-cpp", test_cdd_cpp),
    ("cdd-java", test_cdd_java),
    ("cdd-php", test_cdd_php),
    ("cdd-ruby", test_cdd_ruby),
    ("cdd-sh", test_cdd_sh),
)


def run_test() -> None:
    """Execute native integration and chaos audits for each enabled toolchain.

    Raises:
        AuditFailureError: If any toolchain fails an integration or chaos audit phase.
    """
    specs = ("petstore.json", "petstore_oas3.json")

    for lang_name, runner in TEST_RUNNERS:
        for spec_name in specs:
            base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
            bound_action = functools.partial(runner, spec_name)
            if not run_test_with_audit(lang_name, spec_name, base_path, bound_action):
                raise AuditFailureError(lang_name, "audit", f"Failed audit for {spec_name}")


def _build_roundtrip_command(
    cmd_prefix: Tuple[str, ...],
    input_path: str,
    output_path: str,
) -> List[str]:
    """Build a CLI command list for `from_openapi` or `to_openapi`, handling Gradle `--args=`.

    Args:
        cmd_prefix: Base command tuple from `ToolchainSpec`.
        input_path: Input file or directory path (`-i`).
        output_path: Output file or directory path (`-o`).

    Returns:
        List[str]: Complete command token list.
    """
    tokens = list(cmd_prefix)
    if tokens and tokens[-1].startswith("--args="):
        return [*tokens[:-1], f"{tokens[-1]} -i {input_path} -o {output_path}"]
    return [*tokens, "-i", input_path, "-o", output_path]


def run_toolchain_roundtrip(spec: ToolchainSpec, spec_file: str) -> None:
    """Execute a bidirectional `from_openapi` -> `to_openapi` roundtrip for one toolchain and spec.

    Uses an isolated temporary directory and validates that the roundtripped output
    specification is parseable JSON/YAML.

    Args:
        spec: Registered `ToolchainSpec` from `harness.registry`.
        spec_file: Path to the input OpenAPI specification file.
    """
    print(f"Testing {spec_file} with {spec.name}...")
    if spec.build_cmd:
        run_cmd(xcmd(list(spec.build_cmd)), cwd=spec.name)

    with tempfile.TemporaryDirectory(prefix=f"cdd_rt_{spec.name}_") as temp_root:
        temp_in_spec = os.path.join(temp_root, "input_spec.json")
        temp_sdk_dir = os.path.join(temp_root, "sdk")
        temp_out_spec = os.path.join(temp_root, "output_spec.json")
        os.makedirs(temp_sdk_dir, exist_ok=True)

        yaml_to_json(spec_file, temp_in_spec)

        from_cmd = _build_roundtrip_command(spec.roundtrip_from_cmd, temp_in_spec, temp_sdk_dir)
        run_cmd(xcmd(from_cmd), cwd=spec.name)

        in_target = temp_sdk_dir
        if spec.roundtrip_input_subpath is not None:
            candidate = os.path.join(temp_sdk_dir, spec.roundtrip_input_subpath)
            if os.path.exists(candidate):
                in_target = candidate

        to_cmd = _build_roundtrip_command(spec.roundtrip_to_cmd, in_target, temp_out_spec)
        run_cmd(xcmd(to_cmd), cwd=spec.name)

        if os.path.exists(temp_out_spec):
            load_doc(Path(temp_out_spec))


def run_roundtrip() -> None:
    """Execute bidirectional `from_openapi` -> `to_openapi` roundtrip tests across all toolchains."""
    print("===================================")
    print("Running Roundtrip Tests")
    print("===================================")

    spec_files = ("petstore.json", "petstore_oas3.json")
    for spec in get_toolchains():
        if not should_run(spec.name):
            continue
        for spec_file in spec_files:
            if os.path.exists(spec_file):
                run_toolchain_roundtrip(spec, spec_file)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """CLI entrypoint for `local_test.py`.

    Args:
        argv: Optional sequence of command-line arguments (excluding program name).
    """
    atexit.register(cleanup)
    parser = argparse.ArgumentParser(
        description="Orchestrates local execution of native tests, WASM builds, and roundtrip tests."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["roundtrip", "all", "only-test"],
        help="Mode of execution.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    mode = args.mode

    try:
        if mode == "roundtrip":
            run_roundtrip()
            print("===================================")
            print("All roundtrip tests completed successfully!")
            print("===================================")
        elif mode == "all":
            run_test()
            run_wasm_builds()
            run_roundtrip()
            print("===================================")
            print("All local tests completed successfully!")
            print("===================================")
        elif mode == "only-test":
            run_test()
            print("===================================")
            print("All local tests completed successfully (WASM skipped)!")
            print("===================================")
        else:
            run_test()
            run_wasm_builds()
            print("===================================")
            print("All test.yml local tests completed successfully!")
            print("===================================")
            print("Run 'python3 local_test.py roundtrip' to execute roundtrip tests.")
    except AuditFailureError as exc:
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
