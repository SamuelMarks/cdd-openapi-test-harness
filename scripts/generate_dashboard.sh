#!/bin/bash

# Generates a feature support dashboard by checking which OpenAPI features
# are supported across different toolchains based on their COMPLIANCE.md files.
# It then updates the root COMPLIANCE.md file with a dashboard matrix.

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Call the more robust python script
python3 "$ROOT_DIR/scripts/generate_dashboard.py"
