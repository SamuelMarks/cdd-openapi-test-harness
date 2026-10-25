#!/usr/bin/env python3
"""Script: build_cdd.py.

Installs dependencies and builds the cdd-ts package via the unified harness registry.
Usage: python build_cdd.py
"""

import sys

from harness.errors import DirectoryMissingError
from harness.registry import build_typescript_toolchain


def build_cdd_ts(target_dir: str = "cdd-ts") -> None:
    """Install dependencies and build the cdd-ts package in the given directory.

    Args:
        target_dir: Path to the cdd-ts directory. Defaults to 'cdd-ts'.

    Raises:
        DirectoryMissingError: If the target directory does not exist.
        subprocess.CalledProcessError: If npm install or build fails.
    """
    build_typescript_toolchain(target_dir)


def main() -> None:
    """CLI entrypoint to install dependencies and build the cdd-ts package."""
    try:
        build_cdd_ts("cdd-ts")
    except DirectoryMissingError as exc:
        print(exc.message)
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
