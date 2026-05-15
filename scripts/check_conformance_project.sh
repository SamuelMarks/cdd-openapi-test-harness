#!/bin/bash

# check_conformance_project.sh
# Tests an arbitrary CDD toolchain for OpenAPI 3.2.0 compliance
# and updates the associated conformance markdown table.

set -e

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <project_dir> <conformance_markdown_file> <run_command...>"
    echo "Example: $0 cdd-ts ../openapi-conformance/openapi-3.2.0/client-sdk.md node dist/cli.js"
    exit 1
fi

PROJECT_DIR="$1"
MARKDOWN_FILE="$2"
shift 2
RUN_CMD=("$@")

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_DIR="$ROOT_DIR/OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass"

echo "Checking conformance for project in $PROJECT_DIR..."
echo "Markdown to update: $MARKDOWN_FILE"
echo "Command to execute: ${RUN_CMD[*]}"

cd "$ROOT_DIR/$PROJECT_DIR"

# Ensure pyyaml is available for the python script
python3 -m pip install --quiet pyyaml

# We will run the roundtrip over multiple specs to accumulate features
for spec_file in "$SPEC_DIR"/*.yaml; do
    if [ -f "$spec_file" ]; then
        filename=$(basename "$spec_file")
        echo "Processing $filename..."
        
        # Convert YAML to JSON for safer handling (some tools only accept JSON)
        python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$spec_file" > "temp-input.json"
        
        TEMP_SDK_DIR="temp-sdk-out"
        TEMP_OUT_SPEC="temp-out-spec.json"
        
        rm -rf "$TEMP_SDK_DIR" "$TEMP_OUT_SPEC"
        
        # Run from_openapi
        if ! "${RUN_CMD[@]}" from_openapi to_sdk -i "temp-input.json" -o "$TEMP_SDK_DIR" > /dev/null 2>&1; then
            # Some toolchains might not have to_sdk appended. Try without it if it failed.
            if ! "${RUN_CMD[@]}" from_openapi -i "temp-input.json" -o "$TEMP_SDK_DIR" > /dev/null 2>&1; then
                echo "  Warning: from_openapi failed for $filename"
                continue
            fi
        fi
        
        # Determine the entrypoint for to_openapi (usually the directory, sometimes a specific file)
        # We will assume the directory works for most CDD tools
        EXTRACT_INPUT="$TEMP_SDK_DIR"
        # Search for snapshot dir if needed (specifically for TS which outputs to src)
        if [ -d "$TEMP_SDK_DIR/src" ] && [ -f "$TEMP_SDK_DIR/src/openapi.snapshot.json" ]; then
            EXTRACT_INPUT="$TEMP_SDK_DIR/src"
        fi
        
        # Special case for cdd-swift which requires pointing to the generated swift file
        if [ "$PROJECT_DIR" = "cdd-swift" ]; then
            EXTRACT_INPUT="$TEMP_SDK_DIR/Sources/GeneratedSDK/temp-input.swift"
        fi
        
        # Run to_openapi
        if ! "${RUN_CMD[@]}" to_openapi -i "$EXTRACT_INPUT" -o "$TEMP_OUT_SPEC" > /dev/null 2>&1; then
            echo "  Warning: to_openapi failed for $filename"
            continue
        fi
        
        if [ -f "$TEMP_OUT_SPEC" ]; then
            echo "  Successfully roundtripped $filename. Updating conformance matrix..."
            # Run the python script to update the markdown table
            python3 "$ROOT_DIR/scripts/detect_conformance.py" --input "temp-input.json" --output "$TEMP_OUT_SPEC" --markdown "$ROOT_DIR/$MARKDOWN_FILE"
        fi
        
        rm -rf "$TEMP_SDK_DIR" "$TEMP_OUT_SPEC" "temp-input.json"
    fi
done

echo "Conformance checking completed for $PROJECT_DIR."
