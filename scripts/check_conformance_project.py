#!/usr/bin/env python3
"""Script: `scripts/check_conformance_project.py`.

Tests a CDD toolchain for OpenAPI 3.2.0 compliance and updates its associated
conformance markdown table without mutating global working directories or
bypassing `to_openapi` via snapshots.
Usage: python check_conformance_project.py <project_dir> <markdown_file> <run_cmd...>
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Union

import yaml

from harness.errors import ConformanceError


def _cleanup_temp(temp_dir: str, temp_in_spec: str, temp_out_spec: str) -> None:
    """Remove temporary directory and temporary specification files.

    Args:
        temp_dir: Path to temporary directory created for SDK generation.
        temp_in_spec: Path to temporary input JSON file.
        temp_out_spec: Path to temporary output JSON file.
    """
    shutil.rmtree(temp_dir, ignore_errors=True)
    if os.path.exists(temp_in_spec):
        os.remove(temp_in_spec)
    if os.path.exists(temp_out_spec):
        os.remove(temp_out_spec)


def check_project(
    project_dir: str,
    markdown_file: str,
    run_cmd: Sequence[str],
    root_dir: Optional[Union[str, Path]] = None,
) -> int:
    """Execute roundtrip conformance checks for a single toolchain project.

    Args:
        project_dir: Path to the toolchain project directory (e.g., `'cdd-rust'`).
        markdown_file: Path to the target conformance markdown file.
        run_cmd: Sequence of command tokens to invoke the toolchain CLI.
        root_dir: Optional override for the repository root directory.

    Returns:
        int: Exit status code (0 on completion).

    Raises:
        ConformanceError: If `project_dir` or `markdown_file` does not exist.
    """
    resolved_root = (
        Path(root_dir).resolve()
        if root_dir is not None
        else Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    )
    examples_dir = resolved_root / "OAI-OpenAPI-Specification" / "examples"
    detect_script = resolved_root / "scripts" / "detect_conformance.py"

    abs_project_dir = os.path.abspath(project_dir)
    abs_markdown_file = os.path.abspath(markdown_file)
    if not os.path.isdir(abs_project_dir):
        raise ConformanceError(f"Project directory not found: {project_dir}")
    if not os.path.exists(abs_markdown_file):
        raise ConformanceError(f"Markdown file not found: {markdown_file}")

    specs: List[str] = []
    for ext in ("*.yaml", "*.json"):
        specs.extend(glob.glob(os.path.join(str(examples_dir), "**", ext), recursive=True))

    petstore_oas3 = resolved_root / "petstore_oas3.json"
    if petstore_oas3.exists():
        specs.append(str(petstore_oas3))

    cmd_list = list(run_cmd)
    print(f"Found {len(specs)} specifications to test against {project_dir}.")

    for spec in specs:
        temp_dir = tempfile.mkdtemp(prefix="cdd_conf_")
        temp_in_spec = tempfile.mktemp(suffix=".json", prefix="cdd_in_")
        temp_out_spec = tempfile.mktemp(suffix=".json", prefix="cdd_out_")

        try:
            with open(spec, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            with open(temp_in_spec, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except (OSError, yaml.YAMLError, TypeError, ValueError):
            _cleanup_temp(temp_dir, temp_in_spec, temp_out_spec)
            continue

        if cmd_list[-1].startswith("--args="):
            c1 = [*cmd_list[:-1], f"{cmd_list[-1]}from_openapi to_sdk -i {temp_in_spec} -o {temp_dir}"]
            c2 = [*cmd_list[:-1], f"{cmd_list[-1]}from_openapi -i {temp_in_spec} -o {temp_dir}"]
        else:
            c1 = [*cmd_list, "from_openapi", "to_sdk", "-i", temp_in_spec, "-o", temp_dir]
            c2 = [*cmd_list, "from_openapi", "-i", temp_in_spec, "-o", temp_dir]

        r1 = subprocess.run(
            c1,
            cwd=abs_project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if r1.returncode != 0:
            r2 = subprocess.run(
                c2,
                cwd=abs_project_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if r2.returncode != 0:
                _cleanup_temp(temp_dir, temp_in_spec, temp_out_spec)
                continue

        in_target = temp_dir
        if "cdd-swift" in project_dir:
            swift_files = glob.glob(os.path.join(temp_dir, "Sources", "GeneratedSDK", "*.swift"))
            if swift_files:
                in_target = swift_files[0]
        elif "cdd-rust" in project_dir and os.path.isdir(os.path.join(temp_dir, "src")):
            in_target = os.path.join(temp_dir, "src")

        if cmd_list[-1].startswith("--args="):
            c3 = [*cmd_list[:-1], f"{cmd_list[-1]}to_openapi -i {in_target} -o {temp_out_spec}"]
        else:
            c3 = [*cmd_list, "to_openapi", "-i", in_target, "-o", temp_out_spec]

        r3 = subprocess.run(
            c3,
            cwd=abs_project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if r3.returncode != 0 or not os.path.exists(temp_out_spec):
            _cleanup_temp(temp_dir, temp_in_spec, temp_out_spec)
            continue

        subprocess.run(
            [
                sys.executable,
                str(detect_script),
                temp_in_spec,
                temp_out_spec,
                "--markdown",
                abs_markdown_file,
            ],
            cwd=abs_project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        _cleanup_temp(temp_dir, temp_in_spec, temp_out_spec)

    print(f"Finished updating {abs_markdown_file}")
    return 0


def main(
    argv: Optional[Sequence[str]] = None,
    root_dir: Optional[Union[str, Path]] = None,
) -> int:
    """CLI entrypoint for `check_conformance_project.py`.

    Args:
        argv: Optional sequence of CLI arguments (excluding script name).
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 on success, 1 on invalid usage or ConformanceError).
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    if len(args) < 3:
        print(f"Usage: {sys.argv[0]} <project_dir> <markdown_file> <run_cmd...>")
        return 1

    try:
        return check_project(args[0], args[1], args[2:], root_dir=root_dir)
    except ConformanceError as exc:
        print(exc.message, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
