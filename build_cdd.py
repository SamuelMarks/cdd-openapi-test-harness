#!/usr/bin/env python3
"""
Script: build_cdd.py
Description: Installs dependencies and builds the cdd-ts package.
Usage: python build_cdd.py
"""

import os
import subprocess
import sys


def main() -> None:
    """Install dependencies and build the cdd-ts package."""
    try:
        os.chdir("cdd-ts")
    except FileNotFoundError:
        print("Error: Directory 'cdd-ts' not found.")
        sys.exit(1)

    print("Installing dependencies...")
    subprocess.run(["npm", "i"], check=True)

    print("Building cdd-ts...")
    subprocess.run(["npm", "run", "build"], check=True)


if __name__ == "__main__":
    main()
