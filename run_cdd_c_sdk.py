#!/usr/bin/env python3
"""Script: run_cdd_c_sdk.py.

Runs standard tests for the C SDK and performs integration tests using a
generated C SDK client without mutating tracked repository specification files
or process-global working directory state.
Usage: python run_cdd_c_sdk.py
"""

import sys

from harness.errors import CommandExecutionError, DirectoryMissingError
from harness.registry import run_c_sdk_test_suite


def run_c_sdk_suite(
    c_dir: str = "cdd-c",
    client_dir: str = "cdd-c-client",
    spec_yaml: str = "petstore.yaml",
) -> None:
    """Execute standard `cdd-c` tests and CMake/CTest integration tests on generated C code.

    Args:
        c_dir: Path to the `cdd-c` submodule directory.
        client_dir: Output directory for the generated C SDK client.
        spec_yaml: Path to the input YAML specification file.

    Raises:
        DirectoryMissingError: If `c_dir` does not exist.
        CommandExecutionError: If `ctest` returns a non-zero exit code.
        subprocess.CalledProcessError: If `make` or `cmake` commands fail.
    """
    run_c_sdk_test_suite(c_dir=c_dir, client_dir=client_dir, spec_yaml=spec_yaml)


def main() -> None:
    """CLI entrypoint to execute C SDK test suite and check generated C code."""
    try:
        run_c_sdk_suite()
    except (CommandExecutionError, DirectoryMissingError) as exc:
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
