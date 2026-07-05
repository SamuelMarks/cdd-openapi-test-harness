#!/usr/bin/env python3
"""
Script: check_conformance_project.py
Description: Tests an arbitrary CDD toolchain for OpenAPI 3.2.0 compliance
             and updates the associated conformance markdown table.
Usage: python check_conformance_project.py <project_dir> <conformance_markdown_file> <run_command...>
"""

import os
import sys
import subprocess
import glob
import json
import shutil
import yaml


def main() -> None:
    """Execute the conformance checks for a given project."""
    if len(sys.argv) < 4:
        print(
            f"Usage: {sys.argv[0]} <project_dir> <conformance_markdown_file> <run_command...>"
        )
        print(
            f"Example: {sys.argv[0]} cdd-ts ../openapi-conformance/openapi-3.2.0/client-sdk.md node dist/cli.js"
        )
        sys.exit(1)

    project_dir = sys.argv[1]
    markdown_file = sys.argv[2]
    run_cmd = sys.argv[3:]

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    spec_dir = os.path.join(
        root_dir, "OAI-OpenAPI-Specification", "_archive_", "schemas", "v3.0", "pass"
    )

    print(f"Checking conformance for project in {project_dir}...")
    print(f"Markdown to update: {markdown_file}")
    print(f"Command to execute: {' '.join(run_cmd)}")

    target_dir = os.path.join(root_dir, project_dir)
    os.chdir(target_dir)

    for spec_file in glob.glob(os.path.join(spec_dir, "*.yaml")):
        if os.path.isfile(spec_file):
            filename = os.path.basename(spec_file)
            print(f"Processing {filename}...")

            temp_input = "temp-input.json"
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                with open(temp_input, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except Exception as e:
                print(f"  Error converting YAML to JSON: {e}")
                continue

            temp_sdk_dir = "temp-sdk-out"
            temp_out_spec = "temp-out-spec.json"

            if os.path.exists(temp_sdk_dir):
                shutil.rmtree(temp_sdk_dir)
            if os.path.exists(temp_out_spec):
                os.remove(temp_out_spec)

            # Try from_openapi to_sdk
            cmd1 = run_cmd + [
                "from_openapi",
                "to_sdk",
                "-i",
                temp_input,
                "-o",
                temp_sdk_dir,
            ]
            res1 = subprocess.run(
                cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            if res1.returncode != 0:
                cmd2 = run_cmd + ["from_openapi", "-i", temp_input, "-o", temp_sdk_dir]
                res2 = subprocess.run(
                    cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if res2.returncode != 0:
                    print(f"  Warning: from_openapi failed for {filename}")
                    continue

            extract_input = temp_sdk_dir
            if os.path.isdir(os.path.join(temp_sdk_dir, "src")) and os.path.isfile(
                os.path.join(temp_sdk_dir, "src", "openapi.snapshot.json")
            ):
                extract_input = os.path.join(temp_sdk_dir, "src")
            elif project_dir == "cdd-swift":
                extract_input = os.path.join(
                    temp_sdk_dir, "Sources", "GeneratedSDK", "temp-input.swift"
                )

            # Run to_openapi
            cmd3 = run_cmd + ["to_openapi", "-i", extract_input, "-o", temp_out_spec]
            res3 = subprocess.run(
                cmd3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            if res3.returncode != 0:
                print(f"  Warning: to_openapi failed for {filename}")
                continue

            if os.path.isfile(temp_out_spec):
                print(
                    f"  Successfully roundtripped {filename}. Updating conformance matrix..."
                )
                subprocess.run(
                    [
                        sys.executable,
                        os.path.join(root_dir, "scripts", "detect_conformance.py"),
                        "--input",
                        temp_input,
                        "--output",
                        temp_out_spec,
                        "--markdown",
                        os.path.join(root_dir, markdown_file),
                    ]
                )

            if os.path.exists(temp_sdk_dir):
                shutil.rmtree(temp_sdk_dir)
            if os.path.exists(temp_out_spec):
                os.remove(temp_out_spec)
            if os.path.exists(temp_input):
                os.remove(temp_input)

    print(f"Conformance checking completed for {project_dir}.")


if __name__ == "__main__":
    main()
