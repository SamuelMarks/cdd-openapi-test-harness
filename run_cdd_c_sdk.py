#!/usr/bin/env python3
"""Script: run_cdd_c_sdk.py.

Runs standard tests for the C SDK and performs integration tests using a
generated C SDK client without mutating tracked repository specification files
or monkey-patching generated C code.
Usage: python run_cdd_c_sdk.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

from harness.errors import CommandExecutionError


def run_c_sdk_suite(
    c_dir: str = "cdd-c",
    client_dir: str = "cdd-c-client",
    spec_yaml: str = "petstore.yaml",
) -> None:
    """Execute the C SDK test suite and integration tests on generated C code.

    Args:
        c_dir: Path to the cdd-c submodule directory. Defaults to 'cdd-c'.
        client_dir: Output directory for the generated C SDK client.
        spec_yaml: Path to the input YAML specification file.

    Raises:
        CommandExecutionError: If CTest or SDK build/generation fails.
        subprocess.CalledProcessError: If make or cmake commands fail.
    """
    prev_dir = os.getcwd()
    print("Running standard C SDK tests...")
    os.chdir(c_dir)
    try:
        subprocess.run(["make", "test"], check=True)
    finally:
        os.chdir(prev_dir)

    print("Generating C SDK and running integration tests...")
    if os.path.exists(client_dir):
        shutil.rmtree(client_dir)

    with open(spec_yaml, encoding="utf-8") as file:
        data = yaml.safe_load(file)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp_spec:
        temp_spec_path = tmp_spec.name
        json.dump(data, tmp_spec)

    try:
        subprocess.run(
            [
                os.path.join(c_dir, "bin", "cdd-c"),
                "from_openapi",
                "to_sdk",
                "--tests",
                "-i",
                temp_spec_path,
                "-o",
                client_dir,
            ],
            check=True,
        )
    finally:
        if os.path.exists(temp_spec_path):
            os.remove(temp_spec_path)

    os.chdir(client_dir)
    try:
        subprocess.run(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"], check=True)
        subprocess.run(["cmake", "--build", "."], check=True)

        result = subprocess.run(["ctest", "--output-on-failure"], check=False)
        if result.returncode != 0:
            print("cdd-c sdk tests failed")
            raise CommandExecutionError(["ctest", "--output-on-failure"], result.returncode)
    finally:
        os.chdir(prev_dir)


def main() -> None:
    """CLI entrypoint to execute C SDK test suite and check generated C code."""
    try:
        run_c_sdk_suite()
    except CommandExecutionError as exc:
        sys.exit(exc.code)


if __name__ == "__main__":
    main()
