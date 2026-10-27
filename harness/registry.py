"""Toolchain registry, metadata specifications, and shared runner helpers for all 13 CDD toolchains.

Provides an immutable `ToolchainSpec` dataclass and canonical registry mapping
every language submodule to its target role, build commands, CLI invocation,
SDK generation/testing commands, roundtrip commands, and WebAssembly capabilities.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml

from harness.errors import CommandExecutionError, DirectoryMissingError


@dataclass(frozen=True)
class ToolchainSpec:
    """Immutable specification describing a CDD language toolchain.

    Attributes:
        name: Submodule directory name (e.g., 'cdd-ts', 'cdd-rust').
        language: Human-readable target language name.
        target_type: Role of the toolchain ('client', 'server', 'client_cli', 'both').
        build_cmd: Command to compile/build the toolchain prior to conformance checks.
        check_cmd: Base CLI command prefix used to invoke the toolchain executable.
        wasm_cmd: Command executed inside the toolchain directory to build WASM targets.
        supports_wasm: Whether the toolchain supports WebAssembly compilation.
        is_client_role: Whether the toolchain acts as a client generator.
        is_server_role: Whether the toolchain acts as a server generator.
        client_output_dir: Default output directory name for generated client SDKs.
        native_test_cmd: Command to execute the toolchain's own unit test suite.
        sdk_generate_cmd: Command prefix to generate an SDK with tests from an OpenAPI spec.
        sdk_test_cmd: Command to execute the generated SDK's integration test suite.
        roundtrip_from_cmd: Command prefix to generate code from an OpenAPI spec in roundtrips.
        roundtrip_to_cmd: Command prefix to extract an OpenAPI spec from generated code.
        roundtrip_input_subpath: Optional subpath inside the generated directory passed to `to_openapi`.
    """

    name: str
    language: str
    target_type: str
    build_cmd: Tuple[str, ...]
    check_cmd: Tuple[str, ...]
    wasm_cmd: Tuple[str, ...]
    supports_wasm: bool = True
    is_client_role: bool = True
    is_server_role: bool = False
    client_output_dir: str = ""
    native_test_cmd: Tuple[str, ...] = ("make", "test")
    sdk_generate_cmd: Tuple[str, ...] = ()
    sdk_test_cmd: Tuple[str, ...] = ()
    roundtrip_from_cmd: Tuple[str, ...] = ()
    roundtrip_to_cmd: Tuple[str, ...] = ()
    roundtrip_input_subpath: Optional[str] = None


TOOLCHAINS: Tuple[ToolchainSpec, ...] = (
    ToolchainSpec(
        name="cdd-c",
        language="C (C89)",
        target_type="client",
        build_cmd=("make",),
        check_cmd=("./bin/cdd-c",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-c-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("./bin/cdd-c", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("ctest", "--output-on-failure"),
        roundtrip_from_cmd=("./bin/cdd-c", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("./bin/cdd-c", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-cpp",
        language="C++",
        target_type="client",
        build_cmd=("cmake", "--build", "build", "-j4"),
        check_cmd=("./build/cdd-cpp",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-cpp-client",
        native_test_cmd=("./build/cdd-tests",),
        sdk_generate_cmd=("./build/cdd-cpp", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("ctest", "--output-on-failure"),
        roundtrip_from_cmd=("./build/cdd-cpp", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("./build/cdd-cpp", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-csharp",
        language="C#",
        target_type="client",
        build_cmd=("dotnet", "build", "--configuration", "Release"),
        check_cmd=(
            "dotnet",
            "run",
            "--project",
            "src/Cdd.OpenApi.Cli",
            "--configuration",
            "Release",
            "--",
        ),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-csharp-client",
        native_test_cmd=("dotnet", "test", "tests/Cdd.OpenApi.Tests", "--no-build"),
        sdk_generate_cmd=(
            "dotnet",
            "run",
            "--project",
            "src/Cdd.OpenApi.Cli/Cdd.OpenApi.Cli.csproj",
            "-f",
            "net10.0",
            "--",
            "from_openapi",
            "to_sdk",
            "--tests",
        ),
        sdk_test_cmd=("dotnet", "test", "GeneratedProject.sln"),
        roundtrip_from_cmd=(
            "dotnet",
            "run",
            "--project",
            "src/Cdd.OpenApi.Cli",
            "-f",
            "net10.0",
            "--",
            "from_openapi",
            "to_sdk",
        ),
        roundtrip_to_cmd=("dotnet", "run", "--project", "src/Cdd.OpenApi.Cli", "-f", "net10.0", "--", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-go",
        language="Go",
        target_type="client",
        build_cmd=("make", "build"),
        check_cmd=("./bin/cdd-go",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-go-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("./bin/cdd-go", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("go", "test", "./..."),
        roundtrip_from_cmd=("./bin/cdd-go", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("./bin/cdd-go", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-java",
        language="Java",
        target_type="client",
        build_cmd=("make", "build"),
        check_cmd=("java", "-cp", "lib/*:bin", "cli.Main"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=False,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-java-client",
        native_test_cmd=("mvn", "test"),
        sdk_generate_cmd=("java", "-cp", "lib/*:bin", "cli.Main", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("mvn", "test"),
        roundtrip_from_cmd=("java", "-cp", "lib/*:bin", "cli.Main", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("java", "-cp", "lib/*:bin", "cli.Main", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-kotlin",
        language="Kotlin (Multiplatform)",
        target_type="client",
        build_cmd=("./gradlew", "jvmJar"),
        check_cmd=("./gradlew", "run", "--args="),
        wasm_cmd=("./gradlew", "assemble"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="kotlin-client",
        native_test_cmd=("./gradlew", "test"),
        sdk_generate_cmd=("./gradlew", "run", "--args=from_openapi to_sdk --tests"),
        sdk_test_cmd=("./gradlew", "test"),
        roundtrip_from_cmd=("./gradlew", "run", "--args=from_openapi to_sdk"),
        roundtrip_to_cmd=("./gradlew", "run", "--args=to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-php",
        language="PHP",
        target_type="client",
        build_cmd=("composer", "install", "--no-interaction"),
        check_cmd=("php", "bin/cdd-php"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="php-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("php", "bin/cdd-php", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("vendor/bin/phpunit", "tests/ApiTests.php"),
        roundtrip_from_cmd=("php", "bin/cdd-php", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("php", "bin/cdd-php", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-python-all",
        language="Python",
        target_type="client_cli",
        build_cmd=(sys.executable, "-m", "pip", "install", "-e", "."),
        check_cmd=("uv", "run", "python", "-m", "openapi_client.cli"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-python-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("uv", "run", "python", "-m", "openapi_client.cli", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("uv", "run", "pytest", "-c", "pyproject.toml", "-o", "addopts=", "test/"),
        roundtrip_from_cmd=("uv", "run", "python", "-m", "openapi_client.cli", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("uv", "run", "python", "-m", "openapi_client.cli", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-ruby",
        language="Ruby",
        target_type="client",
        build_cmd=("bundle", "install"),
        check_cmd=("ruby", "bin/cdd-ruby"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-ruby-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("bundle", "exec", "ruby", "bin/cdd-ruby", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("bundle", "exec", "rspec"),
        roundtrip_from_cmd=("bundle", "exec", "ruby", "bin/cdd-ruby", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("bundle", "exec", "ruby", "bin/cdd-ruby", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-rust",
        language="Rust",
        target_type="server",
        build_cmd=("cargo", "build", "-p", "cdd-cli", "--release"),
        check_cmd=("./target/release/cdd-cli",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=False,
        is_client_role=True,
        is_server_role=True,
        client_output_dir="cdd-rust-client",
        native_test_cmd=("cargo", "test"),
        sdk_generate_cmd=(
            "cargo",
            "run",
            "-p",
            "cdd-cli",
            "--bin",
            "cdd-rust",
            "--",
            "from_openapi",
            "to_sdk",
            "--tests",
        ),
        sdk_test_cmd=("cargo", "test"),
        roundtrip_from_cmd=("cargo", "run", "-p", "cdd-cli", "--", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("cargo", "run", "-p", "cdd-cli", "--", "--target", "client", "to_openapi"),
    ),
    ToolchainSpec(
        name="cdd-sh",
        language="Shell (/bin/sh)",
        target_type="client",
        build_cmd=("make", "build"),
        check_cmd=("./cdd.sh",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="sh-client",
        native_test_cmd=("./test.sh",),
        sdk_generate_cmd=("./cdd.sh", "from_openapi", "to_sdk"),
        sdk_test_cmd=("./tests/test_routes.sh",),
        roundtrip_from_cmd=("./cdd.sh", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=("./cdd.sh", "to_openapi"),
        roundtrip_input_subpath="src/routes.sh",
    ),
    ToolchainSpec(
        name="cdd-swift",
        language="Swift",
        target_type="client",
        build_cmd=("swift", "build", "-c", "release"),
        check_cmd=(".build/release/cdd-swift",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=False,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="cdd-swift-client",
        native_test_cmd=("make", "test"),
        sdk_generate_cmd=("swift", "run", "cdd-swift", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("swift", "test"),
        roundtrip_from_cmd=(".build/release/cdd-swift", "from_openapi", "to_sdk"),
        roundtrip_to_cmd=(".build/release/cdd-swift", "to_openapi"),
        roundtrip_input_subpath="Sources/GeneratedSDK/models.swift",
    ),
    ToolchainSpec(
        name="cdd-ts",
        language="TypeScript",
        target_type="client",
        build_cmd=("npm", "run", "build", "--if-present"),
        check_cmd=("node", "dist/cli.js"),
        wasm_cmd=("npm", "run", "build"),
        supports_wasm=False,
        is_client_role=True,
        is_server_role=False,
        client_output_dir="angular-client",
        native_test_cmd=("npm", "run", "test", "--run"),
        sdk_generate_cmd=("node", "dist/cli.js", "from_openapi", "to_sdk", "--tests"),
        sdk_test_cmd=("npx", "vitest", "run", "src/integration.spec.ts"),
        roundtrip_from_cmd=("node", "dist/cli.js", "from_openapi", "to_sdk", "-f", "angular"),
        roundtrip_to_cmd=("node", "dist/cli.js", "to_openapi"),
    ),
)

_TOOLCHAIN_MAP: Dict[str, ToolchainSpec] = {spec.name: spec for spec in TOOLCHAINS}


def get_toolchains() -> List[ToolchainSpec]:
    """Return the ordered list of all registered CDD toolchains.

    Returns:
        List[ToolchainSpec]: Copy of all registered toolchain specifications.
    """
    return list(TOOLCHAINS)


def get_toolchain(name: str) -> ToolchainSpec:
    """Look up a registered toolchain specification by submodule name.

    Args:
        name: The submodule directory name (e.g., 'cdd-c').

    Returns:
        ToolchainSpec: The matching toolchain specification.

    Raises:
        KeyError: If the toolchain name is not registered.
    """
    return _TOOLCHAIN_MAP[name]


def build_typescript_toolchain(target_dir: str = "cdd-ts") -> None:
    """Install dependencies and build the TypeScript toolchain (`cdd-ts`) using `cwd`.

    Args:
        target_dir: Path to the `cdd-ts` directory. Defaults to `'cdd-ts'`.

    Raises:
        DirectoryMissingError: If `target_dir` does not exist.
        subprocess.CalledProcessError: If `npm i` or `npm run build` fails.
    """
    if not os.path.isdir(target_dir):
        raise DirectoryMissingError(target_dir)

    print("Installing dependencies...")
    subprocess.run(["npm", "i"], cwd=target_dir, check=True)

    print("Building cdd-ts...")
    subprocess.run(["npm", "run", "build"], cwd=target_dir, check=True)


def run_typescript_toolchain_tests(target_dir: str = "cdd-ts") -> None:
    """Execute unit tests inside the TypeScript toolchain (`cdd-ts`) using `cwd`.

    Args:
        target_dir: Path to the `cdd-ts` directory. Defaults to `'cdd-ts'`.

    Raises:
        DirectoryMissingError: If `target_dir` does not exist.
        subprocess.CalledProcessError: If the test command exits non-zero.
    """
    if not os.path.isdir(target_dir):
        raise DirectoryMissingError(target_dir)

    spec = get_toolchain("cdd-ts")
    print("Running tests...")
    subprocess.run(list(spec.native_test_cmd), cwd=target_dir, check=True)


def run_c_sdk_test_suite(
    c_dir: str = "cdd-c",
    client_dir: str = "cdd-c-client",
    spec_yaml: str = "petstore.yaml",
) -> None:
    """Execute standard `cdd-c` tests and CMake/CTest integration tests on generated C SDK code.

    Args:
        c_dir: Path to the `cdd-c` submodule directory. Defaults to `'cdd-c'`.
        client_dir: Output directory for the generated C SDK client.
        spec_yaml: Path to the input YAML/JSON specification file.

    Raises:
        DirectoryMissingError: If `c_dir` does not exist.
        CommandExecutionError: If `ctest` returns a non-zero exit code.
        subprocess.CalledProcessError: If `make` or `cmake` commands fail.
    """
    if not os.path.isdir(c_dir):
        raise DirectoryMissingError(c_dir)

    spec = get_toolchain("cdd-c")
    print("Running standard C SDK tests...")
    subprocess.run(list(spec.native_test_cmd), cwd=c_dir, check=True)
    subprocess.run(["make", "build"], cwd=c_dir, check=True)

    print("Generating C SDK and running integration tests...")
    if os.path.exists(client_dir):
        shutil.rmtree(client_dir)

    with open(spec_yaml, encoding="utf-8") as file:
        data = yaml.safe_load(file)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp_spec:
        temp_spec_path = tmp_spec.name
        json.dump(data, tmp_spec)

    try:
        c_bin = os.path.abspath(os.path.join(c_dir, "bin", "cdd-c"))
        subprocess.run(
            [
                c_bin,
                "from_openapi",
                "to_sdk",
                "--tests",
                "-i",
                temp_spec_path,
                "-o",
                client_dir,
            ],
            check=True,
        )
    finally:
        if os.path.exists(temp_spec_path):
            os.remove(temp_spec_path)

    subprocess.run(
        [
            "cmake",
            ".",
            "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON",
            "-DCMAKE_C_FLAGS=-Wno-deprecated-declarations",
        ],
        cwd=client_dir,
        check=True,
    )
    subprocess.run(["cmake", "--build", "."], cwd=client_dir, check=True)

    ctest_cmd = [*spec.sdk_test_cmd, "--no-tests=ignore"]
    result = subprocess.run(ctest_cmd, cwd=client_dir, check=False)
    if result.returncode != 0:
        print("cdd-c sdk tests failed")
        raise CommandExecutionError(ctest_cmd, result.returncode)
