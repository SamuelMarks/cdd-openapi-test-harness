#!/usr/bin/env python3
"""Local test, WASM build, and roundtrip orchestrator (`local_test.py`).

Orchestrates local execution of native tests, WASM builds, and roundtrip tests
across all 13 CDD toolchains.

Usage: python3 local_test.py [roundtrip|all|only-test]
Configuration Variables (Env):
  IGNORE_TESTS: Comma-separated list of toolchains to skip.
  ONLY_TEST: Comma-separated list of toolchains to exclusively run.
  TARGET_TYPE: Filter by target type ('client', 'server', 'all'). Defaults to 'all'.
"""

import argparse
import atexit
import contextlib
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import yaml

from harness.registry import get_toolchain, get_toolchains


def cleanup() -> None:
    """Stop and remove the `petstore_server` Docker container if running."""
    if shutil.which("docker"):
        res = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=petstore_server"],
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
    """Context manager for temporarily changing the current working directory.

    Args:
        path: Directory path to switch into.

    Yields:
        None: Control inside the target working directory.
    """
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def xcmd(cmd_list: Sequence[str]) -> List[str]:
    """Translate executable paths in commands for cross-platform execution.

    Args:
        cmd_list: Sequence of command arguments.

    Returns:
        List[str]: Platform-normalized copy of the command list.
    """
    new_list = list(cmd_list)
    if os.name == "nt" and new_list:
        if new_list[0].startswith("./") or new_list[0].startswith("../"):
            new_list[0] = os.path.normpath(new_list[0])
            if new_list[0].endswith("gradlew"):
                new_list[0] += ".bat"
    return new_list


def run_cmd(
    cmd: Sequence[str],
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = False,
    ignore_errors: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command without `shell=True` or mutating the input list.

    Args:
        cmd: Sequence of command strings to execute.
        check: Whether to raise an exception on non-zero exit code.
        cwd: Optional working directory for the command.
        env: Optional environment variable overrides.
        capture_output: Whether to capture stdout and stderr.
        ignore_errors: Whether to suppress failure log messages.

    Returns:
        subprocess.CompletedProcess[str]: Completed process result (never a CalledProcessError).

    Raises:
        subprocess.CalledProcessError: If `check=True` and the subprocess exits non-zero.
        Exception: If `check=True` and an OS-level execution error occurs.
    """
    resolved_cmd = list(cmd)
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    exe = shutil.which(resolved_cmd[0])
    if exe:
        resolved_cmd[0] = exe

    try:
        return subprocess.run(
            resolved_cmd,
            check=check,
            cwd=cwd,
            env=full_env,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if not ignore_errors:
            print(f"Command '{' '.join(resolved_cmd)}' failed with exit code {exc.returncode}")
        if check:
            raise
        return subprocess.CompletedProcess(
            args=resolved_cmd,
            returncode=exc.returncode,
            stdout=exc.stdout,
            stderr=exc.stderr,
        )
    except Exception as exc:
        if not ignore_errors:
            print(f"Exception running command '{' '.join(resolved_cmd)}': {exc}")
        if check:
            raise
        return subprocess.CompletedProcess(
            args=resolved_cmd,
            returncode=1,
            stdout="",
            stderr=str(exc),
        )


def is_client(module: str) -> bool:
    """Determine if a given module is a registered client toolchain.

    Args:
        module: Toolchain submodule name.

    Returns:
        bool: True if the module supports client generation, False otherwise.
    """
    try:
        return get_toolchain(module).is_client_role
    except KeyError:
        return False


def is_server(module: str) -> bool:
    """Determine if a given module is a registered server toolchain.

    Args:
        module: Toolchain submodule name.

    Returns:
        bool: True if the module supports server generation, False otherwise.
    """
    try:
        return get_toolchain(module).is_server_role
    except KeyError:
        return False


def should_run(module: str) -> bool:
    """Determine if a given module should be executed based on environment variables.

    Args:
        module: Toolchain submodule name.

    Returns:
        bool: True if the module passes `ONLY_TEST`, `IGNORE_TESTS`, and `TARGET_TYPE` filters.
    """
    only_test = os.environ.get("ONLY_TEST", "")
    ignore_tests = os.environ.get("IGNORE_TESTS", "")
    target_type = os.environ.get("TARGET_TYPE", "all")

    if only_test:
        return module in [item.strip() for item in only_test.split(",") if item.strip()]

    if ignore_tests and module in [item.strip() for item in ignore_tests.split(",") if item.strip()]:
        print(f"Skipping {module} (in IGNORE_TESTS)")
        return False

    if target_type == "client" and not is_client(module):
        print(f"Skipping {module} (not a client)")
        return False

    if target_type == "server" and not is_server(module):
        print(f"Skipping {module} (not a server)")
        return False

    return True


def start_petstore(base_path: str = "/v2") -> None:
    """Start the `petstore_server` Docker container for integration tests.

    Args:
        base_path: Swagger base path environment variable for the Petstore server.
    """
    if shutil.which("docker"):
        print(f"Starting petstore server via docker (Base Path: {base_path})...")
        subprocess.run(["docker", "rm", "-f", "petstore_server"], capture_output=True, check=False)
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "-p",
                "8080:8080",
                "-e",
                "SWAGGER_HOST=http://localhost:8080",
                "-e",
                f"SWAGGER_BASE_PATH={base_path}",
                "--name",
                "petstore_server",
                "swaggerapi/petstore",
            ],
            stdout=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(3)
    else:
        print("Warning: docker is not installed or available. Integration tests relying on localhost:8080 may fail.")


def setup_emsdk() -> None:
    """Clone, install, and activate the Emscripten SDK if not already present."""
    if not os.path.isdir("emsdk"):
        print("Setting up emsdk...")
        run_cmd(["git", "clone", "https://github.com/emscripten-core/emsdk.git"])
        with chdir("emsdk"):
            run_cmd(xcmd(["./emsdk", "install", "latest"]))
            run_cmd(xcmd(["./emsdk", "activate", "latest"]))


def run_wasm_builds() -> None:
    """Trigger WebAssembly builds across all registered WASM-capable toolchains."""
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


def run_test_with_audit(
    lang_name: str,
    spec_file: str,
    base_path: str,
    action: Callable[[], None],
) -> bool:
    """Run 3-phase integration tests (Happy Path + Coverage, HTTP 500, Invalid Schema).

    Args:
        lang_name: Toolchain identifier (e.g., 'cdd-ts').
        spec_file: OpenAPI specification filename under test.
        base_path: Base URL path for the specification ('/v2' or '/api/v3').
        action: Zero-argument callable executing the toolchain's test suite.

    Returns:
        bool: True if all three audit phases succeed, False otherwise.
    """
    if not should_run(lang_name):
        return True

    print("===================================")
    print(f"Auditing {lang_name} against {spec_file}")
    print("===================================")

    print(f"[{lang_name}] Phase 1: Happy Path & Coverage...")
    start_petstore(base_path)
    try:
        action()
    except Exception as exc:
        print(f"[{lang_name}] Happy path failed: {exc}")
        return False

    print(f"[{lang_name}] Validating Endpoint Coverage...")
    res = subprocess.run(
        ["docker", "logs", "petstore_server"],
        capture_output=True,
        text=True,
        check=False,
    )
    logs = chr(10).join([res.stdout, res.stderr])
    if os.path.exists("java_petstore_access.log"):
        with open("java_petstore_access.log", encoding="utf-8") as f:
            logs += f.read()

    verify_res = subprocess.run(
        [sys.executable, "verify_coverage.py", spec_file, base_path],
        input=logs,
        text=True,
        capture_output=True,
        check=False,
    )
    if verify_res.returncode != 0:
        print(f"[{lang_name}] Coverage validation failed.")
        print(verify_res.stdout)
        print(verify_res.stderr)
        return False

    print(f"[{lang_name}] Phase 2: Status Audit (Expect Tests to Fail on 500s)...")
    subprocess.run(["docker", "rm", "-f", "petstore_server"], capture_output=True, check=False)
    saboteur = subprocess.Popen([sys.executable, "saboteur_server.py", "500", "8080"])
    time.sleep(2)
    try:
        action()
        print(f"[{lang_name}] Audit Failed: Tests passed even though the server returned HTTP 500.")
        saboteur.kill()
        saboteur.wait()
        return False
    except Exception:
        pass
    saboteur.kill()
    saboteur.wait()

    print(f"[{lang_name}] Phase 3: Schema Audit (Expect Tests to Fail on Invalid Payloads)...")
    saboteur = subprocess.Popen([sys.executable, "saboteur_server.py", "invalid_schema", "8080"])
    time.sleep(2)
    try:
        action()
        print(f"[{lang_name}] Audit Failed: Tests passed even though the server returned invalid JSON schema.")
        saboteur.kill()
        saboteur.wait()
        return False
    except Exception:
        pass
    saboteur.kill()
    saboteur.wait()

    print(f"[{lang_name}] All audits passed successfully.")
    return True


def test_cdd_ts(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-ts`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-ts"):
        run_cmd(["npm", "install"])
        run_cmd(["npm", "run", "build"])

    shutil.rmtree("angular-client", ignore_errors=True)
    run_cmd(["npm", "cache", "clean", "--force"], check=False)
    run_cmd(["npx", "-p", "@angular/cli", "ng", "new", "angular-client", "--defaults", "--skip-git"])

    with chdir("angular-client"):
        run_cmd(
            ["npx", "ng", "add", "@angular/material", "--skip-confirmation", "--defaults"],
            check=False,
        )

    with chdir("cdd-ts"):
        run_cmd(
            [
                "node",
                "dist/cli.js",
                "from_openapi",
                "to_sdk",
                "-i",
                f"../{spec_file}",
                "--output",
                "../angular-client/src/app/api",
                "--implementation",
                "angular",
                "--platform",
                "browser",
            ]
        )

    with chdir("angular-client"):
        run_cmd(["npm", "install"])
        run_cmd(["npm", "run", "test", "--", "--watch=false"], check=True)

    with chdir("cdd-ts"):
        shutil.rmtree("node-client", ignore_errors=True)
        os.makedirs("node-client", exist_ok=True)
        with chdir("node-client"):
            run_cmd(["npm", "init", "-y"])
            run_cmd(["npm", "install", "typescript", "vitest", "@types/node"])

        run_cmd(
            [
                "node",
                "dist/cli.js",
                "from_openapi",
                "to_sdk",
                "-i",
                f"../{spec_file}",
                "--output",
                "node-client",
                "--implementation",
                "node",
                "--platform",
                "node",
            ]
        )

        with chdir("node-client"):
            tsconfig_data = {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "NodeNext",
                    "moduleResolution": "NodeNext",
                    "esModuleInterop": True,
                    "strict": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                }
            }
            with open("tsconfig.json", "w", encoding="utf-8") as f:
                json.dump(tsconfig_data, f, indent=2)
            vitest_lines = [
                'import { defineConfig } from "vitest/config";',
                "",
                "export default defineConfig({",
                "    test: {",
                '        include: ["src/**/*.spec.ts"]',
                "    }",
                "});",
                "",
            ]
            with open("vitest.config.ts", "w", encoding="utf-8") as f:
                f.write(os.linesep.join(vitest_lines))
            run_cmd(["npx", "vitest", "run", "src/integration.spec.ts"])


def test_cdd_kotlin(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-kotlin`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    env = _discover_kotlin_env()

    with chdir("cdd-kotlin"):
        run_cmd(xcmd(["./gradlew", "jvmJar"]), env=env)
        shutil.rmtree("../kotlin-client", ignore_errors=True)
        run_cmd(
            xcmd(
                [
                    "./gradlew",
                    "run",
                    f"--args=from_openapi to_sdk -i ../{spec_file} --output ../kotlin-client --tests",
                ]
            ),
            env=env,
        )

    with chdir("kotlin-client"):
        if "JAVA_HOME" in env:
            with open("gradle.properties", "w", encoding="utf-8") as f:
                print(f"org.gradle.java.home={env['JAVA_HOME']}", file=f)
        run_cmd(["gradle", "test", "--no-daemon"], check=True, env=env)


def test_cdd_go(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-go`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-go"):
        run_cmd(["make", "test"])
        run_cmd(["make", "build"])
        shutil.rmtree("../cdd-go-client", ignore_errors=True)
        run_cmd(
            xcmd(
                [
                    "./bin/cdd-go",
                    "from_openapi",
                    "to_sdk",
                    "-i",
                    f"../{spec_file}",
                    "-o",
                    "../cdd-go-client",
                    "-create-composable-tests",
                ]
            )
        )

    with chdir("cdd-go-client"):
        run_cmd(["go", "mod", "tidy"])
        run_cmd(["go", "test", "./..."])


def test_cdd_csharp(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-csharp`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-csharp"):
        run_cmd(["dotnet", "restore"])
        run_cmd(["dotnet", "build", "--no-restore"])
        run_cmd(["dotnet", "test", "tests/Cdd.OpenApi.Tests", "--no-build"])
        shutil.rmtree("../cdd-csharp-client", ignore_errors=True)
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
            ]
        )

    with chdir("cdd-csharp-client"):
        run_cmd(["dotnet", "test", "GeneratedProject.sln"])


def test_cdd_python_all(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-python-all`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-python-all"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-python-client", ignore_errors=True)
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
            ]
        )

    with chdir("cdd-python-client"):
        run_cmd([sys.executable, "-m", "venv", ".venv"])
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        pip_bin = os.path.join(".venv", bin_dir, "pip")
        pytest_bin = os.path.join(".venv", bin_dir, "pytest")
        run_cmd([pip_bin, "install", "-e", ".[dev]"])
        run_cmd([pytest_bin, "test/"])


def test_cdd_rust(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-rust`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-rust"):
        run_cmd(["cargo", "test"])
        shutil.rmtree("../cdd-rust-client", ignore_errors=True)
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
            ]
        )

    with chdir("cdd-rust-client"):
        run_cmd(["cargo", "test"])


def test_cdd_swift(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-swift`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-swift"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-swift-client", ignore_errors=True)
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
            ]
        )

    with chdir("cdd-swift-client"):
        run_cmd(["swift", "test"])


def test_cdd_c(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-c`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-c"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-c-client", ignore_errors=True)
        run_cmd(
            xcmd(
                [
                    "./bin/cdd-c",
                    "from_openapi",
                    "to_sdk",
                    "-i",
                    f"../{spec_file}",
                    "-o",
                    "../cdd-c-client",
                    "--tests",
                ]
            )
        )

    with chdir("cdd-c-client"):
        run_cmd(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"])
        run_cmd(["cmake", "--build", "."])
        run_cmd(["ctest", "--output-on-failure"], check=True)
        run_cmd(xcmd(["./src/test_generated_client"]))


def test_cdd_cpp(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-cpp`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-cpp"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-cpp-client", ignore_errors=True)
        run_cmd(
            xcmd(
                [
                    "./build/cdd-cpp",
                    "from_openapi",
                    "to_sdk",
                    "-i",
                    f"../{spec_file}",
                    "-o",
                    "../cdd-cpp-client",
                    "--tests",
                ]
            )
        )

    with chdir("cdd-cpp-client"):
        run_cmd(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"])
        run_cmd(["cmake", "--build", "."])
        run_cmd(["ctest", "--output-on-failure"], check=True)
        run_cmd(xcmd(["./src/test_generated_client"]))


def test_cdd_java(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-java`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-java"):
        run_cmd(["make", "test"])
        run_cmd(["make", "build"])
        shutil.rmtree("../cdd-java-client", ignore_errors=True)
        cp = f"lib/*{os.pathsep}bin"
        run_cmd(
            [
                "java",
                "-cp",
                cp,
                "cli.Main",
                "from_openapi",
                "to_sdk",
                "-i",
                f"../{spec_file}",
                "--tests",
                "-o",
                "../cdd-java-client",
            ]
        )

    with chdir("cdd-java-client"):
        run_cmd(["mvn", "test"])


def test_cdd_php(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-php`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-php"):
        run_cmd(["make", "test"])
        print("Generating PHP SDK and running integration tests...")
        shutil.rmtree("../php-client", ignore_errors=True)
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
            ]
        )

    with chdir("php-client"):
        run_cmd(["composer", "install"])
        run_cmd(["composer", "test"], check=True)


def test_cdd_ruby(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-ruby`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-ruby"):
        if os.path.exists("Gemfile.lock"):
            os.remove("Gemfile.lock")
        run_cmd(xcmd(["bundle", "install"]))
        run_cmd(xcmd(["bundle", "exec", "rspec"]))
        shutil.rmtree("../cdd-ruby-client", ignore_errors=True)
        run_cmd(
            xcmd(
                [
                    "ruby",
                    "bin/cdd-ruby",
                    "from_openapi",
                    "to_sdk",
                    "-i",
                    f"../{spec_file}",
                    "-o",
                    "../cdd-ruby-client",
                ]
            )
        )

    with chdir("cdd-ruby-client"):
        if os.path.exists("Gemfile.lock"):
            os.remove("Gemfile.lock")
        run_cmd(xcmd(["bundle", "install"]))
        run_cmd(xcmd(["bundle", "exec", "rspec"]))


def test_cdd_sh(spec_file: str) -> None:
    """Execute native SDK generation and integration tests for `cdd-sh`.

    Args:
        spec_file: Path to the OpenAPI specification file relative to root.
    """
    with chdir("cdd-sh"):
        run_cmd(xcmd(["./test.sh"]))
        if shutil.which("shellcheck"):
            files: List[str] = []
            for d in glob.glob("src/*"):
                if os.path.isdir(d):
                    files.extend(glob.glob(f"{d}/*.sh"))
            run_cmd(["shellcheck", "cdd.sh"] + files, check=False)
        else:
            print("Warning: shellcheck is not installed. Skipping shellcheck.")

        print("Generating SDK and running integration tests...")
        shutil.rmtree("../sh-client", ignore_errors=True)
        yaml_to_json(f"../{spec_file}", "temp-petstore.json")
        env = os.environ.copy()
        env["CDD_TESTS"] = "1"
        run_cmd(
            xcmd(["./cdd.sh", "from_openapi", "to_sdk", "-i", "temp-petstore.json", "-o", "../sh-client"]),
            check=True,
            env=env,
        )

    if os.path.exists("sh-client"):
        with chdir("sh-client"):
            test_routes = os.path.join("tests", "test_routes.sh")
            if os.path.exists(test_routes):
                os.chmod(test_routes, 0o755)
                run_cmd(xcmd([f"./{test_routes}"]), check=True)


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
    """Execute native integration and chaos audits for each enabled toolchain."""
    specs = ["petstore.json", "petstore_oas3.json"]

    for lang_name, runner in TEST_RUNNERS:
        for spec_name in specs:
            base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
            if not run_test_with_audit(
                lang_name,
                spec_name,
                base_path,
                lambda s=spec_name, r=runner: r(s),  # type: ignore[misc]
            ):
                sys.exit(1)


def run_roundtrip() -> None:
    """Execute bidirectional `from_openapi` -> `to_openapi` roundtrip tests across toolchains."""
    print("===================================")
    print("Running Roundtrip Tests")
    print("===================================")

    if should_run("cdd-ts"):
        with chdir("cdd-ts"):
            run_cmd(["npm", "install"])
            run_cmd(["npm", "run", "build"])
        for spec_file in ["petstore.json", "petstore_oas3.json"]:
            if os.path.exists(spec_file):
                print(f"Testing {spec_file} with cdd-ts...")
                run_cmd(["node", "cdd-ts/dist/cli.js", "from_openapi", "to_sdk", "-i", spec_file, "-o", "temp-ng"])
                run_cmd(
                    [
                        "node",
                        "cdd-ts/dist/cli.js",
                        "to_openapi",
                        "-i",
                        "temp-ng",
                        "--format",
                        "yaml",
                        "-o",
                        "temp-ng-spec.yaml",
                    ]
                )
                shutil.rmtree("temp-ng", ignore_errors=True)
                if os.path.exists("temp-ng-spec.yaml"):
                    os.remove("temp-ng-spec.yaml")

    for spec_file in ["petstore.json", "petstore_oas3.json"]:
        if not os.path.exists(spec_file):
            continue

        if should_run("cdd-kotlin"):
            print(f"Testing {spec_file} with cdd-kotlin...")
            with chdir("cdd-kotlin"):
                run_cmd(xcmd(["./gradlew", "run", f"--args=from_openapi to_sdk -i ../{spec_file} --output ../temp-kt"]))
                run_cmd(
                    xcmd(["./gradlew", "run", "--args=to_openapi -i ../temp-kt --format yaml -o ../temp-kt-spec.yaml"])
                )
            shutil.rmtree("temp-kt", ignore_errors=True)
            if os.path.exists("temp-kt-spec.yaml"):
                os.remove("temp-kt-spec.yaml")

        if should_run("cdd-rust"):
            print(f"Testing {spec_file} with cdd-rust...")
            with chdir("cdd-rust"):
                run_cmd(["cargo", "test"])
                shutil.rmtree("../cdd-rust-client", ignore_errors=True)
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
                        "../petstore.json",
                        "-o",
                        "../cdd-rust-client",
                        "--tests",
                    ]
                )

            with chdir("cdd-rust-client"):
                shutil.rmtree("../temp-rs", ignore_errors=True)
                run_cmd(
                    [
                        "cargo",
                        "run",
                        "-p",
                        "cdd-cli",
                        "--",
                        "from_openapi",
                        "to_sdk",
                        "-i",
                        f"../{spec_file}",
                        "-o",
                        "../temp-rs",
                    ]
                )
                run_cmd(
                    [
                        "cargo",
                        "run",
                        "-p",
                        "cdd-cli",
                        "--",
                        "--target",
                        "client",
                        "to_openapi",
                        "-i",
                        "../temp-rs",
                        "-o",
                        "../temp-rs/spec.yaml",
                    ]
                )
            shutil.rmtree("temp-rs", ignore_errors=True)

        if should_run("cdd-c"):
            print(f"Testing {spec_file} with cdd-c...")
            with chdir("cdd-c"):
                os.makedirs("../temp-c", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-c-spec.json")
                run_cmd(
                    xcmd(["./bin/cdd-c", "from_openapi", "to_sdk", "-i", "../temp-c-spec.json", "-o", "../temp-c"]),
                    check=True,
                )
                run_cmd(
                    xcmd(["./bin/cdd-c", "to_openapi", "-i", "../temp-c", "-o", "../temp-c/spec.yaml"]),
                    check=True,
                )
            shutil.rmtree("temp-c", ignore_errors=True)
            if os.path.exists("temp-c-spec.json"):
                os.remove("temp-c-spec.json")

        if should_run("cdd-cpp"):
            print(f"Testing {spec_file} with cdd-cpp...")
            with chdir("cdd-cpp"):
                os.makedirs("../temp-cpp", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-cpp-spec.json")
                run_cmd(
                    xcmd(
                        ["./bin/cdd-cpp", "from_openapi", "to_sdk", "-i", "../temp-cpp-spec.json", "-o", "../temp-cpp"]
                    ),
                    check=True,
                )
                run_cmd(
                    xcmd(["./bin/cdd-cpp", "to_openapi", "-i", "../temp-cpp", "-o", "../temp-cpp/spec.yaml"]),
                    check=True,
                )
            shutil.rmtree("temp-cpp", ignore_errors=True)
            if os.path.exists("temp-cpp-spec.json"):
                os.remove("temp-cpp-spec.json")

        if should_run("cdd-php"):
            print(f"Testing {spec_file} with cdd-php...")
            with chdir("cdd-php"):
                os.makedirs("../temp-php", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-php-spec.json")
                run_cmd(
                    [
                        "php",
                        "bin/cdd-php",
                        "from_openapi",
                        "to_sdk",
                        "-i",
                        "../temp-php-spec.json",
                        "-o",
                        "../temp-php",
                    ],
                    check=True,
                )
                run_cmd(
                    ["php", "bin/cdd-php", "to_openapi", "-i", "../temp-php", "-o", "../temp-php/spec.yaml"],
                    check=True,
                )
            shutil.rmtree("temp-php", ignore_errors=True)
            if os.path.exists("temp-php-spec.json"):
                os.remove("temp-php-spec.json")

        if should_run("cdd-ruby"):
            print(f"Testing {spec_file} with cdd-ruby...")
            with chdir("cdd-ruby"):
                os.makedirs("../temp-rb", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-rb-spec.json")
                run_cmd(
                    xcmd(
                        [
                            "ruby",
                            "bin/cdd-ruby",
                            "from_openapi",
                            "to_sdk",
                            "-i",
                            "../temp-rb-spec.json",
                            "-o",
                            "../temp-rb",
                        ]
                    ),
                    check=True,
                )
                run_cmd(
                    xcmd(["ruby", "bin/cdd-ruby", "to_openapi", "-i", "../temp-rb", "-o", "../temp-rb/spec.yaml"]),
                    check=True,
                )
            shutil.rmtree("temp-rb", ignore_errors=True)
            if os.path.exists("temp-rb-spec.json"):
                os.remove("temp-rb-spec.json")

        if should_run("cdd-java"):
            print(f"Testing {spec_file} with cdd-java...")
            with chdir("cdd-java"):
                os.makedirs("../temp-java", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-java-spec.json")
                run_cmd(
                    xcmd(["./gradlew", "run", "--args=from_openapi to_sdk -i ../temp-java-spec.json -o ../temp-java"]),
                    check=True,
                )
                run_cmd(
                    xcmd(["./gradlew", "run", "--args=to_openapi -i ../temp-java -o ../temp-java/spec.yaml"]),
                    check=True,
                )
            shutil.rmtree("temp-java", ignore_errors=True)
            if os.path.exists("temp-java-spec.json"):
                os.remove("temp-java-spec.json")

    if should_run("cdd-python-all"):
        print("Testing with cdd-python-all...")
        with chdir("cdd-python-all"):
            run_cmd([sys.executable, "-m", "pip", "install", "pyyaml"])
            run_cmd([sys.executable, "-m", "pip", "install", "-e", "."])
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    os.makedirs("temp-py", exist_ok=True)
                    yaml_to_json(spec_file, "temp-py-spec.json")
                    run_cmd(["cdd-python-all", "from_openapi", "-i", "temp-py-spec.json", "-o", "temp-py/"])
                    run_cmd(["cdd-python-all", "to_openapi", "-i", "temp-py/", "-o", "temp-py-spec.json"])
                    shutil.rmtree("temp-py", ignore_errors=True)
                    if os.path.exists("temp-py-spec.json"):
                        os.remove("temp-py-spec.json")

    if should_run("cdd-swift"):
        print("Testing with cdd-swift...")
        with chdir("cdd-swift"):
            run_cmd(["swift", "build", "-c", "release"])
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-swift-spec.json")
                    run_cmd(
                        [".build/release/cdd-swift", "from_openapi", "-i", "temp-swift-spec.json", "-o", "temp-swift"]
                    )
                    run_cmd(
                        [
                            ".build/release/cdd-swift",
                            "to_openapi",
                            "-i",
                            "temp-swift/Sources/GeneratedSDK/temp-swift-spec.swift",
                            "-o",
                            "temp-swift-out.json",
                        ]
                    )
                    shutil.rmtree("temp-swift", ignore_errors=True)
                    if os.path.exists("temp-swift-spec.json"):
                        os.remove("temp-swift-spec.json")
                    if os.path.exists("temp-swift-out.json"):
                        os.remove("temp-swift-out.json")

    if should_run("cdd-sh"):
        print("Testing with cdd-sh...")
        with chdir("cdd-sh"):
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-sh-spec.json")
                    run_cmd(xcmd(["./cdd.sh", "from_openapi", "-i", "temp-sh-spec.json", "-o", "temp-sh-dir"]))
                    run_cmd(xcmd(["./cdd.sh", "to_openapi", "-i", "temp-sh-dir", "-o", "temp-sh-out.json"]))
                    shutil.rmtree("temp-sh-dir", ignore_errors=True)
                    if os.path.exists("temp-sh-spec.json"):
                        os.remove("temp-sh-spec.json")
                    if os.path.exists("temp-sh-out.json"):
                        os.remove("temp-sh-out.json")
                    if os.path.exists("ast.json"):
                        os.remove("ast.json")

    if should_run("cdd-go"):
        print("Testing with cdd-go...")
        with chdir("cdd-go"):
            run_cmd(["make", "build"])
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-go-spec.json")
                    run_cmd(xcmd(["./bin/cdd-go", "from_openapi", "-i", "temp-go-spec.json", "-o", "temp-go"]))
                    run_cmd(xcmd(["./bin/cdd-go", "to_openapi", "-i", "temp-go", "-o", "temp-go-out.json"]))
                    shutil.rmtree("temp-go", ignore_errors=True)
                    if os.path.exists("temp-go-spec.json"):
                        os.remove("temp-go-spec.json")
                    if os.path.exists("temp-go-out.json"):
                        os.remove("temp-go-out.json")

    if should_run("cdd-csharp"):
        print("Testing with cdd-csharp...")
        with chdir("cdd-csharp"):
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-cs-spec.json")
                    run_cmd(
                        [
                            "dotnet",
                            "run",
                            "--project",
                            "src/Cdd.OpenApi.Cli",
                            "--",
                            "from_openapi",
                            "-i",
                            "temp-cs-spec.json",
                            "-o",
                            "temp-cs",
                        ]
                    )
                    run_cmd(
                        [
                            "dotnet",
                            "run",
                            "--project",
                            "src/Cdd.OpenApi.Cli",
                            "--",
                            "to_openapi",
                            "-i",
                            "temp-cs",
                            "-o",
                            "temp-cs-out.json",
                        ]
                    )
                    shutil.rmtree("temp-cs", ignore_errors=True)
                    if os.path.exists("temp-cs-spec.json"):
                        os.remove("temp-cs-spec.json")
                    if os.path.exists("temp-cs-out.json"):
                        os.remove("temp-cs-out.json")


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

    if mode == "roundtrip":
        run_roundtrip()
        print("===================================")
        print("All roundtrip tests completed successfully!")
        print("===================================")
    elif mode == "all":
        start_petstore()
        run_test()
        run_wasm_builds()
        run_roundtrip()
        print("===================================")
        print("All local tests completed successfully!")
        print("===================================")
    elif mode == "only-test":
        start_petstore()
        run_test()
        print("===================================")
        print("All local tests completed successfully (WASM skipped)!")
        print("===================================")
    else:
        start_petstore()
        run_test()
        run_wasm_builds()
        print("===================================")
        print("All test.yml local tests completed successfully!")
        print("===================================")
        print("Run 'python3 local_test.py roundtrip' to execute roundtrip tests.")


if __name__ == "__main__":
    main()
