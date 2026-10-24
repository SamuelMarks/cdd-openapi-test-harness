#!/usr/bin/env python3
"""Script: `scripts/check_all_conformance.py`.

Runs the conformance checker across all registered language submodules.
Usage: python scripts/check_all_conformance.py
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from harness.registry import get_toolchains


def run_check(
    lang: str,
    build_cmd: Sequence[str],
    check_cmd: Sequence[str],
    root_dir: Optional[Path] = None,
) -> bool:
    """Build and run the conformance checker for a specific language toolchain.

    Args:
        lang: The name of the language toolchain directory (e.g., 'cdd-rust').
        build_cmd: Command sequence to compile or build the toolchain.
        check_cmd: Command sequence to run the toolchain's CLI for conformance checking.
        root_dir: Repository root directory. Defaults to parent of `scripts/`.

    Returns:
        bool: True if the conformance check executed, False if the directory was absent.
    """
    resolved_root = root_dir if root_dir is not None else Path(__file__).resolve().parent.parent
    lang_dir = resolved_root / lang
    md_file = lang_dir / "conformance" / "openapi-3.2.0" / "client-sdk.md"

    print("==========================================================")
    print(f"Checking {lang}")
    print("==========================================================")

    if lang_dir.is_dir():
        if build_cmd:
            prev_dir = os.getcwd()
            os.chdir(lang_dir)
            try:
                subprocess.run(list(build_cmd), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            finally:
                os.chdir(prev_dir)

        check_script = resolved_root / "scripts" / "check_conformance_project.py"
        cmd = [sys.executable, str(check_script), str(lang_dir), str(md_file)] + list(check_cmd)
        subprocess.run(cmd, check=False)
        return True

    print(f"Skipping {lang} (directory not found)")
    return False


def main(root_dir: Optional[Path] = None) -> int:
    """Orchestrate conformance checks across all CDD toolchains.

    Args:
        root_dir: Optional repository root path override for testing.

    Returns:
        int: Exit status code (0 on success, 1 if OAI-OpenAPI-Specification is missing).
    """
    resolved_root = root_dir if root_dir is not None else Path(__file__).resolve().parent.parent
    os.chdir(resolved_root)

    target_dir = resolved_root / "OAI-OpenAPI-Specification"
    if not target_dir.is_dir():
        print("Error: OAI-OpenAPI-Specification submodule not found. Run 'git submodule update --init'")
        return 1

    for spec in get_toolchains():
        run_check(spec.name, spec.build_cmd, spec.check_cmd, root_dir=resolved_root)

    print("==========================================================")
    print("All toolchains tested. Conformance tracking table updated.")
    print("==========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
