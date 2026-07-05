#!/usr/bin/env python3
"""
Script: update_all_tables.py
Description: Orchestrates the execution of Python scripts to update the
             dynamically generated tables ('Current Ecosystem Status' and
             'Testing Coverage') in the project's README.md.
Usage: python scripts/update_all_tables.py
"""

import sys
import subprocess
import os


def main() -> None:
    """Run table update scripts."""
    print("Updating Current Ecosystem Status table...")
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    res1 = subprocess.run(
        [sys.executable, os.path.join(root_dir, "scripts", "update_readme_status.py")]
    )
    if res1.returncode != 0:
        sys.exit(res1.returncode)

    print("Updating Testing Coverage table...")
    res2 = subprocess.run(
        [
            sys.executable,
            os.path.join(root_dir, "scripts", "update_testing_coverage.py"),
        ]
    )
    if res2.returncode != 0:
        sys.exit(res2.returncode)

    print("README tables have been updated successfully.")


if __name__ == "__main__":
    main()
