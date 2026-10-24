"""Toolchain registry and metadata specifications for all 13 CDD toolchains.

Provides an immutable `ToolchainSpec` dataclass and canonical registry mapping
every language submodule to its target role, build commands, CLI invocation,
and WebAssembly capabilities.
"""

import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple


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
    ),
    ToolchainSpec(
        name="cdd-cpp",
        language="C++",
        target_type="client",
        build_cmd=("make", "build"),
        check_cmd=("./build/cdd-cpp",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
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
    ),
    ToolchainSpec(
        name="cdd-go",
        language="Go",
        target_type="client",
        build_cmd=("go", "build", "-o", "bin/cdd_go", "./cmd/cdd-go"),
        check_cmd=("./bin/cdd_go",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
    ),
    ToolchainSpec(
        name="cdd-java",
        language="Java",
        target_type="client",
        build_cmd=(),
        check_cmd=("./gradlew", "run", "--args="),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=False,
        is_client_role=True,
        is_server_role=False,
    ),
    ToolchainSpec(
        name="cdd-kotlin",
        language="Kotlin (Multiplatform)",
        target_type="client",
        build_cmd=(),
        check_cmd=("./cdd.sh",),
        wasm_cmd=("./gradlew", "assemble"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
    ),
    ToolchainSpec(
        name="cdd-php",
        language="PHP",
        target_type="client",
        build_cmd=(),
        check_cmd=("php", "bin/cdd-php"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
    ),
    ToolchainSpec(
        name="cdd-python-all",
        language="Python",
        target_type="client_cli",
        build_cmd=(sys.executable, "-m", "pip", "install", "-e", "."),
        check_cmd=("cdd-python",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
    ),
    ToolchainSpec(
        name="cdd-ruby",
        language="Ruby",
        target_type="client",
        build_cmd=(),
        check_cmd=("ruby", "bin/cdd-ruby"),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
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
    ),
    ToolchainSpec(
        name="cdd-sh",
        language="Shell (/bin/sh)",
        target_type="client",
        build_cmd=(),
        check_cmd=("./cdd.sh",),
        wasm_cmd=("make", "build_wasm"),
        supports_wasm=True,
        is_client_role=True,
        is_server_role=False,
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
