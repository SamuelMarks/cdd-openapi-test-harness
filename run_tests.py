#!/usr/bin/env python3
"""Script: run_tests.py.

Executes tests within the cdd-ts package via the unified harness registry.
Usage: python run_tests.py
"""

import sys

from harness.errors import DirectoryMissingError
from harness.registry import run_typescript_toolchain_tests


def run_cdd_ts_tests(target_dir: str = "cdd-ts") -> None:
    """Execute unit tests inside the cdd-ts directory.

    Args:
        target_dir: Path to the cdd-ts directory. Defaults to 'cdd-ts'.

    Raises:
        DirectoryMissingError: If the target directory does not exist.
        subprocess.CalledProcessError: If the test execution fails.
    """
    run_typescript_toolchain_tests(target_dir)


def main() -> None:
    """CLI entrypoint to execute tests within the cdd-ts package."""
    try:
        run_cdd_ts_tests("cdd-ts")
    except DirectoryMissingError as exc:
        print(exc.message)
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
