#!/usr/bin/env python3
"""Updates the 'Testing Coverage' table in `README.md` (`scripts/update_testing_coverage.py`).

Parses the 'Testing Coverage' table in `README.md` and updates the Native and
WebAssembly (WASM) build and test statuses for each language toolchain based on
the canonical toolchain registry and `WASM.md` documentation.
"""

import os
import subprocess
import sys
from typing import Optional

from harness.registry import get_toolchain


def _determine_native_status(root_dir: str, repo_name: str) -> str:
    """Determine whether a toolchain submodule has native build/test support present.

    Args:
        root_dir: Root directory of the test harness repository.
        repo_name: Submodule directory name (e.g., 'cdd-ts').

    Returns:
        str: '✅ Yes' if the toolchain directory exists and is registered, '❌ No' otherwise.
    """
    repo_dir = os.path.join(root_dir, repo_name)
    if not os.path.isdir(repo_dir):
        return "❌ No"
    try:
        get_toolchain(repo_name)
        return "✅ Yes"
    except KeyError:
        return "❌ No"


def _determine_wasm_status(root_dir: str, repo_name: str) -> str:
    """Determine WASM support status from the toolchain registry and `WASM.md` documentation.

    Args:
        root_dir: Root directory of the test harness repository.
        repo_name: Submodule directory name (e.g., 'cdd-ts').

    Returns:
        str: '✅ Yes' if supported and documented, '❌ No' otherwise.
    """
    wasm_md_path = os.path.join(root_dir, repo_name, "WASM.md")
    if not os.path.exists(wasm_md_path):
        return "❌ No"

    with open(wasm_md_path, encoding="utf-8") as wf:
        content = wf.read().lower()
    if "not supported" in content or "unsupported" in content:
        return "❌ No"

    try:
        spec = get_toolchain(repo_name)
        if not spec.supports_wasm and "wasm" not in content:
            return "❌ No"
    except KeyError:
        pass
    return "✅ Yes"


def main(root_dir: Optional[str] = None) -> int:
    """Parse `README.md`, check native and WASM support, and update the 'Testing Coverage' table.

    Args:
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 on success, 1 if `README.md` or the coverage table is missing).
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
        if "| Repository | Native Build/Tests | WASM Build/Tests |" in line:
            start_idx = i + 2
        elif start_idx != -1 and (line.strip() == "" or not line.strip().startswith("|")):
            end_idx = i
            break

    if start_idx == -1:
        print("Could not find Testing Coverage table in README.md", file=sys.stderr)
        return 1

    if end_idx == -1:
        end_idx = len(lines)

    print("Updating Testing Coverage table in README.md...")
    changed = False

    for i in range(start_idx, end_idx):
        line = lines[i]
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue

        repo_col = parts[1]
        repo_name = repo_col.strip("` ")

        native_status = _determine_native_status(resolved_root, repo_name)
        wasm_status = _determine_wasm_status(resolved_root, repo_name)

        nl = chr(10)
        new_line = f"| `{repo_name}` | {native_status} | {wasm_status} |{nl}"
        if lines[i] != new_line:
            lines[i] = new_line
            changed = True

    if changed:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("README.md Testing Coverage table has been updated.")
        subprocess.run(["git", "add", readme_path], cwd=resolved_root, check=False)
    else:
        print("Testing Coverage table is already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
