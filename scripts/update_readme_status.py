#!/usr/bin/env python3
"""Updates the 'Current Ecosystem Status' table in `README.md` (`scripts/update_readme_status.py`).

Automates updating the ecosystem status by running the local tests (via
`local_test.py`) for each CDD toolchain and recording whether the native tests,
WASM builds, and roundtrip tests pass or fail.
"""

import os
import subprocess
import sys
from typing import List, Optional


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
    except Exception:
        return "❌ Error"


def main(root_dir: Optional[str] = None) -> int:
    """Parse `README.md`, execute tests for each toolchain, and update the status table.

    Args:
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 on success, 1 if `README.md` or the status table is missing).
    """
    resolved_root = root_dir if root_dir is not None else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    readme_path = os.path.join(resolved_root, "README.md")
    if not os.path.exists(readme_path):
        print("README.md not found", file=sys.stderr)
        return 1

    with open(readme_path, encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if "| Repository | Target Language | Role | Test Status | Roundtrip Status |" in line:
            start_idx = i + 2
        elif start_idx != -1 and (line.strip() == "" or not line.strip().startswith("|")):
            end_idx = i
            break

    if start_idx == -1:
        print("Could not find Ecosystem Status table in README.md", file=sys.stderr)
        return 1

    if end_idx == -1:
        end_idx = len(lines)

    print("Updating README.md ecosystem status...")
    changed = False

    for i in range(start_idx, end_idx):
        line = lines[i]
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue

        repo_col = parts[1]
        repo_name = repo_col.strip("` ")
        lang_col = parts[2]
        role_col = parts[3]

        print(f"Testing {repo_name}...")

        test_status = run_test(repo_name, "only-test", root_dir=resolved_root)
        if test_status == "✅ Passed":
            wasm_And_test = run_test(repo_name, "", root_dir=resolved_root)
            if wasm_And_test != "✅ Passed":
                test_status = "✅ Passed (WASM ❌)"

        rt_status = run_test(repo_name, "roundtrip", root_dir=resolved_root)

        nl = chr(10)
        new_line = f"| `{repo_name}` | {lang_col} | {role_col} | {test_status} | {rt_status} |{nl}"
        if lines[i] != new_line:
            lines[i] = new_line
            changed = True

    if changed:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("README.md has been updated with the latest test statuses.")
        subprocess.run(["git", "add", readme_path], cwd=resolved_root, check=False)
    else:
        print("README.md is already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
