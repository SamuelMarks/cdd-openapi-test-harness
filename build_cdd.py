#!/usr/bin/env python3
"""Script: build_cdd.py.

Installs dependencies and builds the cdd-ts package.
Usage: python build_cdd.py
"""

import os
import subprocess
import sys

from harness.errors import DirectoryMissingError


def build_cdd_ts(target_dir: str = "cdd-ts") -> None:
    """Install dependencies and build the cdd-ts package in the given directory.

    Args:
        target_dir: Path to the cdd-ts directory. Defaults to 'cdd-ts'.

    Raises:
        DirectoryMissingError: If the target directory does not exist.
        subprocess.CalledProcessError: If npm install or build fails.
    """
    prev_dir = os.getcwd()
    try:
        os.chdir(target_dir)
    except FileNotFoundError as exc:
        raise DirectoryMissingError(target_dir) from exc

    try:
        print("Installing dependencies...")
        subprocess.run(["npm", "i"], check=True)

        print("Building cdd-ts...")
        subprocess.run(["npm", "run", "build"], check=True)
    finally:
        os.chdir(prev_dir)


def main() -> None:
    """CLI entrypoint to install dependencies and build the cdd-ts package."""
    try:
        build_cdd_ts("cdd-ts")
    except DirectoryMissingError as exc:
        print(exc.message)
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
