#!/usr/bin/env python3
"""
update_testing_coverage.py

This script parses the 'Testing Coverage' table in README.md and updates the
WebAssembly (WASM) build and test statuses for each language toolchain. It does
this by reading the `WASM.md` file within each toolchain directory and applying
simple heuristics to determine if WASM is supported, unsupported, or out of scope.
"""
import os
import re
import sys
import subprocess

def main() -> None:
    """
    Main execution logic. Reads the README.md to find the testing coverage table,
    evaluates WASM support for each toolchain based on their respective WASM.md files,
    formats the table lines accordingly, and writes the updated table back to README.md.
    """
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        print("README.md not found.")
        sys.exit(1)

    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = -1
    for i, line in enumerate(lines):
        if "| Repository | Native Build/Tests | WASM Build/Tests | Reason if Skipped |" in line:
            start_idx = i
            break

    if start_idx == -1:
        print("Could not find Testing Coverage table")
        sys.exit(1)

    updated_lines = lines[:]
    changed = False

    for i in range(start_idx + 2, len(lines)):
        line = lines[i].strip()
        if not line or not line.startswith("|"):
            break

        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:
            repo_name = parts[1].strip("` ")
            if repo_name.startswith("cdd-"):
                wasm_md_path = os.path.join(repo_name, "WASM.md")
                has_wasm = False
                reason = ""
                
                if os.path.exists(wasm_md_path):
                    with open(wasm_md_path, "r", encoding="utf-8") as wf:
                        content = wf.read().lower()
                        # Simple heuristics to determine WASM support based on the markdown contents
                        if "unsupported" in content and "possible" not in content and "yes" not in content:
                            reason = "Unsupported as per WASM.md"
                        elif "out of scope" in content:
                            reason = "Out of scope as per WASM.md"
                        elif "missing" in content and "wasm support" in content:
                            reason = "Missing WASM support / WASM.md"
                        else:
                            has_wasm = True
                else:
                    reason = "Missing WASM support / WASM.md"

                wasm_status = "✅ Yes" if has_wasm else "❌ No"
                
                # Align columns
                new_line = f"| `{repo_name}` | ✅ Yes | {wasm_status} | {reason} |\n"
                
                if lines[i] != new_line:
                    updated_lines[i] = new_line
                    changed = True

    if changed:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)
        print("README.md Testing Coverage table has been updated.")
        subprocess.run(["git", "add", "README.md"], check=False)
    else:
        print("Testing Coverage table is already up to date.")

if __name__ == "__main__":
    main()