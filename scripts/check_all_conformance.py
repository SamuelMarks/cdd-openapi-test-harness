#!/usr/bin/env python3
"""Script: `scripts/check_all_conformance.py`.

Runs the conformance checker across all registered language submodules without
mutating process-global working directory state.
Usage: python scripts/check_all_conformance.py
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Union

from harness.errors import ConformanceError
from harness.registry import get_toolchains


def run_check(
    proj_dir: str,
    build_cmd: Sequence[str],
    check_cmd: Sequence[str],
    root_dir: Optional[Union[str, Path]] = None,
) -> bool:
    """Build a single toolchain project and invoke `check_conformance_project.py` on it.

    Args:
        proj_dir: Toolchain directory name relative to `root_dir` (e.g., `'cdd-c'`).
        build_cmd: Command sequence to compile/build the toolchain.
        check_cmd: Command sequence to run the toolchain's CLI.
        root_dir: Optional root directory override; defaults to the repository root.

    Returns:
        bool: True if the project directory exists and checks were invoked, False if skipped.
    """
    resolved_root = (
        Path(root_dir).resolve()
        if root_dir is not None
        else Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    )
    target_path = resolved_root / proj_dir
    if not target_path.is_dir():
        return False

    print("==========================================================")
    print(f"Checking OpenAPI 3.2.0 Conformance for {proj_dir}")
    print("==========================================================")

    if build_cmd:
        subprocess.run(
            list(build_cmd),
            cwd=str(target_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    md_file = target_path / "conformance" / "openapi-3.2.0" / "client-sdk.md"
    checker_script = resolved_root / "scripts" / "check_conformance_project.py"

    cmd = [
        sys.executable,
        str(checker_script),
        str(target_path),
        str(md_file),
        *list(check_cmd),
    ]
    subprocess.run(cmd, cwd=str(resolved_root), check=False)
    return True


def main(root_dir: Optional[Union[str, Path]] = None) -> int:
    """Run conformance checks across all 13 registered CDD toolchains.

    Args:
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 on success, 1 if `OAI-OpenAPI-Specification` is missing).
    """
    resolved_root = (
        Path(root_dir).resolve()
        if root_dir is not None
        else Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    )
    oai_dir = resolved_root / "OAI-OpenAPI-Specification"
    try:
        if not oai_dir.is_dir():
            raise ConformanceError(
                "Error: OAI-OpenAPI-Specification directory not found. Run 'git submodule update --init' first."
            )
    except ConformanceError as exc:
        print(exc.message)
        return exc.code

    for spec in get_toolchains():
        run_check(spec.name, spec.build_cmd, spec.check_cmd, root_dir=resolved_root)

    print("==========================================================")
    print("All toolchains tested. Conformance tracking table updated.")
    print("==========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
