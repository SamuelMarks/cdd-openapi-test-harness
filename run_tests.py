#!/usr/bin/env python3
"""Script: run_tests.py.

Executes tests within the cdd-ts package.
Usage: python run_tests.py
"""

import os
import subprocess
import sys

from harness.errors import DirectoryMissingError


def run_cdd_ts_tests(target_dir: str = "cdd-ts") -> None:
    """Execute unit tests inside the cdd-ts directory.

    Args:
        target_dir: Path to the cdd-ts directory. Defaults to 'cdd-ts'.

    Raises:
        DirectoryMissingError: If the target directory does not exist.
        subprocess.CalledProcessError: If the test execution fails.
    """
    prev_dir = os.getcwd()
    try:
        os.chdir(target_dir)
    except FileNotFoundError as exc:
        raise DirectoryMissingError(target_dir) from exc

    try:
        print("Running tests...")
        subprocess.run(["npm", "run", "test", "--run"], check=True)
    finally:
        os.chdir(prev_dir)


def main() -> None:
    """CLI entrypoint to execute tests within the cdd-ts package."""
    try:
        run_cdd_ts_tests("cdd-ts")
    except DirectoryMissingError as exc:
        print(exc.message)
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
