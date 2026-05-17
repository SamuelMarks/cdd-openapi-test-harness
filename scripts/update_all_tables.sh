#!/bin/sh
# ==========================================
# Script: update_all_tables.sh
# Description: Orchestrates the execution of Python scripts to update the
#              dynamically generated tables ('Current Ecosystem Status' and 
#              'Testing Coverage') in the project's README.md.
# Usage: ./scripts/update_all_tables.sh
# ==========================================

set -e

echo "Updating Current Ecosystem Status table..."
python3 scripts/update_readme_status.py

echo "Updating Testing Coverage table..."
python3 scripts/update_testing_coverage.py

echo "README tables have been updated successfully."
