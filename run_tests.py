#!/usr/bin/env python3
"""
Script: run_tests.py
Description: Executes tests within the cdd-ts package.
Usage: python run_tests.py
"""

import os
import subprocess
import sys


def main() -> None:
    """Execute tests within the cdd-ts package."""
    try:
        os.chdir("cdd-ts")
    except FileNotFoundError:
        print("Error: Directory 'cdd-ts' not found.")
        sys.exit(1)

    print("Running tests...")
    subprocess.run(["npm", "run", "test", "--run"], check=True)


if __name__ == "__main__":
    main()
