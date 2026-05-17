#!/usr/bin/env python3
"""
update_readme_status.py

This script automates the process of updating the 'Current Ecosystem Status' table
in the README.md file. It runs the local tests (via `local-test.sh`) for each
CDD toolchain to determine if the local tests and roundtrip tests pass or fail,
and dynamically updates the markdown table with the live results.
"""

import os
import re
import subprocess
import sys

def run_test(toolchain: str, test_type: str) -> bool:
    """
    Executes the local test script for a specific toolchain and test type.

    Args:
        toolchain (str): The name of the CDD toolchain directory (e.g., 'cdd-java').
        test_type (str): The type of test to run ('only-test' or 'roundtrip').

    Returns:
        bool: True if the test execution completes successfully (exit code 0), False otherwise.
    """
    print(f"Running {test_type} for {toolchain}...")
    env = os.environ.copy()
    env["ONLY_TEST"] = toolchain
    
    cmd = ["./local-test.sh", test_type]
    try:
        # Run with timeout to prevent hanging
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )
        # return true if exit code 0
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Timeout for {toolchain} {test_type}")
        return False
    except Exception as e:
        print(f"Error running {toolchain} {test_type}: {e}")
        return False

def main() -> None:
    """
    Main entry point. Parses README.md, locates the ecosystem status table,
    runs validation tests for each identified toolchain, and overwrites README.md
    if the statuses have changed.
    """
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        print("README.md not found.")
        sys.exit(1)
        
    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_table = False
    start_idx = -1
    
    for i, line in enumerate(lines):
        if "| Implementation" in line and "| Local Test Status" in line:
            in_table = True
            start_idx = i
            break
            
    if start_idx == -1:
        print("Could not find the target table in README.md")
        sys.exit(1)
        
    updated_lines = lines[:]
    changed = False
    
    for i in range(start_idx + 2, len(lines)):
        line = lines[i].strip()
        if not line or not line.startswith("|"):
            break
            
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:
            impl_name = parts[1].strip("` ")
            type_val = parts[2].strip("` ")
            
            if impl_name.startswith("cdd-"):
                local_ok = run_test(impl_name, "only-test")
                roundtrip_ok = run_test(impl_name, "roundtrip")
                
                local_status = "✅ Passed" if local_ok else "❌ Failed"
                roundtrip_status = "✅ Passed" if roundtrip_ok else "❌ Failed"
                
                # Format to keep the markdown table somewhat aligned
                # | `cdd-c`             | `client`     | ✅ Passed          | ✅ Passed                |
                impl_col = f"`{impl_name}`"
                type_col = f"`{type_val}`"
                
                new_line = f"| {impl_col.ljust(19)} | {type_col.ljust(12)} | {local_status.ljust(17)} | {roundtrip_status.ljust(23)} |\n"
                
                if lines[i] != new_line:
                    updated_lines[i] = new_line
                    changed = True

    if changed:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)
        print("README.md has been updated.")
        # Optionally add to git so the pre-commit hook includes the change
        subprocess.run(["git", "add", "README.md"], check=False)
    else:
        print("README.md is already up to date.")

if __name__ == "__main__":
    main()