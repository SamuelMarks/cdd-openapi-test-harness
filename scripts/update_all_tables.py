#!/usr/bin/env python3
"""Script: `scripts/update_all_tables.py`.

Orchestrates the execution of Python scripts to update the dynamically
generated tables ('Current Ecosystem Status' and 'Testing Coverage') in `README.md`.
Usage: python scripts/update_all_tables.py
"""

import os
import subprocess
import sys
from typing import Optional

from harness.errors import DashboardError


def update_all_readme_tables(root_dir: str) -> None:
    """Execute the README table update scripts in sequence.

    Args:
        root_dir: Repository root directory containing `scripts/`.

    Raises:
        DashboardError: If either table update script exits with a non-zero status code.
    """
    print("1. Updating 'Current Ecosystem Status' table...")
    res1 = subprocess.run(
        [
            sys.executable,
            os.path.join(root_dir, "scripts", "update_readme_status.py"),
        ],
        check=False,
    )
    if res1.returncode != 0:
        raise DashboardError("Failed to update 'Current Ecosystem Status' table.")

    print("2. Updating 'Testing Coverage' table...")
    res2 = subprocess.run(
        [
            sys.executable,
            os.path.join(root_dir, "scripts", "update_testing_coverage.py"),
        ],
        check=False,
    )
    if res2.returncode != 0:
        raise DashboardError("Failed to update 'Testing Coverage' table.")

    print("README tables have been updated successfully.")


def main(root_dir: Optional[str] = None) -> int:
    """CLI entrypoint to execute the README table update scripts in sequence.

    Args:
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 if both scripts succeed, non-zero otherwise).
    """
    resolved_root = root_dir if root_dir is not None else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        update_all_readme_tables(resolved_root)
    except DashboardError as exc:
        print(exc.message, file=sys.stderr)
        return exc.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
