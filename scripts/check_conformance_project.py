#!/usr/bin/env python3
"""Script: `scripts/check_conformance_project.py`.

Tests a CDD toolchain for OpenAPI 3.2.0 compliance and updates its associated
conformance markdown table.
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
from typing import Optional, Sequence

import yaml


def _cleanup_temp(temp_dir: str, temp_out_spec: str, temp_input: str) -> None:
    """Remove temporary directory and specification files created during a check.

    Args:
        temp_dir: Path to temporary output directory.
        temp_out_spec: Path to temporary output OpenAPI JSON file.
        temp_input: Path to temporary input OpenAPI JSON file.
    """
    shutil.rmtree(temp_dir, ignore_errors=True)
    for path in (temp_out_spec, temp_input):
        if os.path.exists(path):
            os.remove(path)


def check_project(
    project_dir: str,
    markdown_file: str,
    run_cmd: Sequence[str],
    root_dir: Optional[Path] = None,
) -> int:
    """Execute roundtrip conformance tests for a single toolchain project.

    Args:
        project_dir: Path to the toolchain submodule directory.
        markdown_file: Path to the markdown conformance checklist to update.
        run_cmd: Command prefix used to execute the toolchain CLI.
        root_dir: Optional repository root path override.

    Returns:
        int: Exit status code (0 on completion).
    """
    resolved_root = root_dir if root_dir is not None else Path(__file__).resolve().parent.parent
    abs_markdown_file = os.path.abspath(markdown_file)

    specs_dir = resolved_root / "OAI-OpenAPI-Specification" / "examples"
    spec_files: list[str] = []
    for ext in ("*.yaml", "*.json"):
        spec_files.extend(glob.glob(str(specs_dir / "**" / ext), recursive=True))

    petstore_30 = resolved_root / "petstore_oas3.json"
    if petstore_30.exists():
        spec_files.append(str(petstore_30))

    print(f"Found {len(spec_files)} test specifications for {project_dir}...")

    prev_dir = os.getcwd()
    os.chdir(project_dir)
    try:
        for spec in spec_files:
            temp_dir = tempfile.mkdtemp(prefix="cdd_conf_")
            fd_out, temp_out_spec = tempfile.mkstemp(suffix=".json")
            os.close(fd_out)
            fd_in, temp_input = tempfile.mkstemp(suffix=".json")
            os.close(fd_in)

            try:
                with open(spec, encoding="utf-8") as f_in:
                    data = yaml.safe_load(f_in)
                with open(temp_input, "w", encoding="utf-8") as f_out:
                    json.dump(data, f_out)
            except Exception:
                _cleanup_temp(temp_dir, temp_out_spec, temp_input)
                continue

            if len(run_cmd) > 0 and run_cmd[-1].startswith("--args="):
                base_cmd = list(run_cmd[:-1])
                arg_prefix = run_cmd[-1]
                cmd1 = base_cmd + [f"{arg_prefix}from_openapi to_sdk -i {temp_input} -o {temp_dir}"]
                cmd2 = base_cmd + [f"{arg_prefix}from_openapi -i {temp_input} -o {temp_dir}"]
            else:
                cmd1 = list(run_cmd) + ["from_openapi", "to_sdk", "-i", temp_input, "-o", temp_dir]
                cmd2 = list(run_cmd) + ["from_openapi", "-i", temp_input, "-o", temp_dir]

            res1 = subprocess.run(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res1.returncode != 0:
                res2 = subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if res2.returncode != 0:
                    _cleanup_temp(temp_dir, temp_out_spec, temp_input)
                    continue

            snapshot = os.path.join(temp_dir, "openapi.snapshot.json")
            if os.path.exists(snapshot):
                shutil.copyfile(snapshot, temp_out_spec)
            else:
                in_target = temp_dir
                if "cdd-swift" in project_dir and os.path.exists(os.path.join(temp_dir, "Sources", "GeneratedSDK")):
                    swift_files = glob.glob(os.path.join(temp_dir, "Sources", "GeneratedSDK", "*.swift"))
                    if swift_files:
                        in_target = swift_files[0]

                if len(run_cmd) > 0 and run_cmd[-1].startswith("--args="):
                    base_cmd = list(run_cmd[:-1])
                    arg_prefix = run_cmd[-1]
                    cmd_to = base_cmd + [f"{arg_prefix}to_openapi -i {in_target} -o {temp_out_spec}"]
                else:
                    cmd_to = list(run_cmd) + ["to_openapi", "-i", in_target, "-o", temp_out_spec]

                res_to = subprocess.run(cmd_to, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if res_to.returncode != 0:
                    _cleanup_temp(temp_dir, temp_out_spec, temp_input)
                    continue

            if os.path.exists(temp_out_spec) and os.path.getsize(temp_out_spec) > 0:
                detect_script = resolved_root / "scripts" / "detect_conformance.py"
                subprocess.run(
                    [
                        sys.executable,
                        str(detect_script),
                        temp_input,
                        temp_out_spec,
                        "--markdown",
                        abs_markdown_file,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

            _cleanup_temp(temp_dir, temp_out_spec, temp_input)
    finally:
        os.chdir(prev_dir)

    print(f"Conformance checking completed for {project_dir}.")
    return 0


def main(argv: Optional[Sequence[str]] = None, root_dir: Optional[Path] = None) -> int:
    """CLI entrypoint for `check_conformance_project.py`.

    Args:
        argv: Optional sequence of CLI arguments (excluding script name).
        root_dir: Optional repository root directory override.

    Returns:
        int: Exit status code (0 on success, 1 on invalid usage).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 3:
        print(f"Usage: {sys.argv[0]} <project_dir> <markdown_file> <run_cmd...>")
        return 1

    return check_project(args[0], args[1], args[2:], root_dir=root_dir)


if __name__ == "__main__":
    sys.exit(main())
