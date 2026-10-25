#!/usr/bin/env python3
"""Updates the 'Current Ecosystem Status' table in `README.md` (`scripts/update_readme_status.py`).

Automates updating the ecosystem status by running the local tests (via
`local_test.py`) for each CDD toolchain and recording whether the native tests,
WASM builds, and roundtrip tests pass or fail. Supports both the canonical
4-column `README.md` table (`| Implementation | Type | Local Test Status | Roundtrip Petstore JSON |`)
and the 5-column table format.
"""

import os
import subprocess
import sys
from typing import List, Optional

from harness.errors import DashboardError


def run_test(repo_name: str, mode: str = "", root_dir: Optional[str] = None) -> str:
    """Run `local_test.py` for a specific repository and mode.

    Args:
        repo_name: The name of the toolchain repository (e.g., 'cdd-ts').
        mode: The execution mode for `local_test.py` (e.g., 'only-test', 'roundtrip', or '').
        root_dir: Optional repository root directory override.

    Returns:
        str: A status string indicating the outcome ('✅ Passed', '❌ Failed', '❌ Timeout', or '❌ Error').
    """
    env = os.environ.copy()
    env["ONLY_TEST"] = repo_name
    cmd: List[str] = [sys.executable, "local_test.py"]
    if mode:
        cmd.append(mode)

    try:
        res = subprocess.run(
            cmd,
            env=env,
            cwd=root_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
            check=False,
        )
        return "✅ Passed" if res.returncode == 0 else "❌ Failed"
    except subprocess.TimeoutExpired:
        return "❌ Timeout"
    except OSError:
        return "❌ Error"


def update_readme_status_table(root_dir: str, stage: bool = False) -> bool:
    """Parse `README.md`, execute tests for each toolchain, and update the status table.

    Args:
        root_dir: Repository root directory containing `README.md`.
        stage: Whether to run `git add` on `README.md` if modified. Defaults to False.

    Returns:
        bool: True if `README.md` was modified, False if already up to date.

    Raises:
        DashboardError: If `README.md` or the Ecosystem Status table is missing.
    """
    readme_path = os.path.join(root_dir, "README.md")
    if not os.path.exists(readme_path):
        raise DashboardError("README.md not found")

    with open(readme_path, encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = -1
    end_idx = -1
    table_columns = 4
    for i, line in enumerate(lines):
        if "| Implementation" in line and "Local Test Status" in line and "Roundtrip" in line:
            start_idx = i + 2
            table_columns = 4
        elif "| Repository | Target Language | Role | Test Status | Roundtrip Status |" in line:
            start_idx = i + 2
            table_columns = 5
        elif start_idx != -1 and (line.strip() == "" or not line.strip().startswith("|")):
            end_idx = i
            break

    if start_idx == -1:
        raise DashboardError("Could not find Ecosystem Status table in README.md")

    if end_idx == -1:
        end_idx = len(lines)

    print("Updating README.md ecosystem status...")
    changed = False
    nl = chr(10)

    for i in range(start_idx, end_idx):
        line = lines[i]
        parts = [p.strip() for p in line.split("|")]
        min_parts = 5 if table_columns == 4 else 6
        if len(parts) < min_parts:
            continue

        repo_col = parts[1]
        repo_name = repo_col.strip("` ")

        print(f"Testing {repo_name}...")

        test_status = run_test(repo_name, "only-test", root_dir=root_dir)
        if test_status == "✅ Passed":
            wasm_and_test = run_test(repo_name, "", root_dir=root_dir)
            if wasm_and_test != "✅ Passed":
                test_status = "✅ Passed (WASM ❌)"

        rt_status = run_test(repo_name, "roundtrip", root_dir=root_dir)

        if table_columns == 4:
            type_col = parts[2]
            new_line = f"| `{repo_name}` | {type_col} | {test_status} | {rt_status} |{nl}"
        else:
            lang_col = parts[2]
            role_col = parts[3]
            new_line = f"| `{repo_name}` | {lang_col} | {role_col} | {test_status} | {rt_status} |{nl}"

        if lines[i] != new_line:
            lines[i] = new_line
            changed = True

    if changed:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("README.md has been updated with the latest test statuses.")
        if stage:
            subprocess.run(["git", "add", readme_path], cwd=root_dir, check=False)
    else:
        print("README.md is already up to date.")
    return changed


def main(root_dir: Optional[str] = None, stage: bool = False) -> int:
    """CLI entrypoint for `update_readme_status.py`.

    Args:
        root_dir: Optional repository root directory override.
        stage: Whether to stage modified `README.md` with `git add`.

    Returns:
        int: Exit status code (0 on success, 1 if `README.md` or the status table is missing).
    """
    resolved_root = root_dir if root_dir is not None else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        update_readme_status_table(resolved_root, stage=stage)
    except DashboardError as exc:
        print(exc.message, file=sys.stderr)
        return exc.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
