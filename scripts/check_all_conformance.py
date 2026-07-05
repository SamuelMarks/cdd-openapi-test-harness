#!/usr/bin/env python3
"""
Script: check_all_conformance.py
Description: Runs the conformance checker across all language submodules.
Usage: python scripts/check_all_conformance.py
"""

import os
import sys
import subprocess


def main() -> None:
    """Run all conformance checks for all language submodules."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)

    target_dir = os.path.join("..", "openapi-conformance", "openapi-3.2.0")
    if not os.path.isdir(target_dir):
        print(f"Error: {target_dir} directory not found.")
        print(
            "Please ensure the openapi-conformance repository is cloned as a sibling directory."
        )
        sys.exit(1)

    markdown_target = os.path.join(target_dir, "client-sdk.md")

    print("==========================================================")
    print("Running universal OpenAPI 3.2.0 conformance checks...")
    print(f"Targeting Markdown: {markdown_target}")
    print("==========================================================")

    checker_script = [
        sys.executable,
        os.path.join("scripts", "check_conformance_project.py"),
    ]

    def run_check(lang: str, build_cmd: list, check_cmd: list) -> None:
        if os.path.isdir(lang):
            print(f"\n---> Testing {lang}")
            if build_cmd:
                subprocess.run(build_cmd, cwd=lang, check=False)
            cmd = checker_script + [lang, markdown_target] + check_cmd
            subprocess.run(cmd, check=False)

    run_check(
        "cdd-ts", ["npm", "run", "build", "--if-present"], ["node", "dist/cli.js"]
    )
    run_check("cdd-c", ["make"], ["./bin/cdd-c"])
    run_check("cdd-cpp", ["make", "build"], ["./build/cdd-cpp"])
    run_check(
        "cdd-csharp",
        ["dotnet", "build", "--configuration", "Release"],
        [
            "dotnet",
            "run",
            "--project",
            "src/Cdd.OpenApi.Cli",
            "--configuration",
            "Release",
            "--",
        ],
    )
    run_check(
        "cdd-go", ["go", "build", "-o", "bin/cdd_go", "./cmd/cdd-go"], ["./bin/cdd_go"]
    )
    run_check("cdd-java", [], ["./gradlew", "run", "--args="])
    run_check("cdd-kotlin", [], ["./cdd.sh"])
    run_check("cdd-php", [], ["php", "bin/cdd-php"])
    run_check(
        "cdd-python-all",
        [sys.executable, "-m", "pip", "install", "-e", "."],
        ["cdd-python"],
    )
    run_check("cdd-ruby", [], ["ruby", "bin/cdd-ruby"])
    run_check(
        "cdd-rust",
        ["cargo", "build", "-p", "cdd-cli", "--release"],
        ["./target/release/cdd-cli"],
    )
    run_check("cdd-sh", [], ["./cdd.sh"])
    run_check(
        "cdd-swift", ["swift", "build", "-c", "release"], [".build/release/cdd-swift"]
    )

    print("\n==========================================================")
    print("All toolchains tested. Conformance tracking table updated.")
    print("==========================================================")


if __name__ == "__main__":
    main()
