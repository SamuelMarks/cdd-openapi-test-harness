#!/bin/bash

# check_all_conformance.sh
# Runs the conformance checker across all language submodules.

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d "../openapi-conformance/openapi-3.2.0" ]; then
    echo "Error: ../openapi-conformance/openapi-3.2.0 directory not found."
    echo "Please ensure the openapi-conformance repository is cloned as a sibling directory."
    exit 1
fi

MARKDOWN_TARGET="../openapi-conformance/openapi-3.2.0/client-sdk.md"

echo "=========================================================="
echo "Running universal OpenAPI 3.2.0 conformance checks..."
echo "Targeting Markdown: $MARKDOWN_TARGET"
echo "=========================================================="

# 1. cdd-ts (TypeScript)
if [ -d "cdd-ts" ]; then
    echo -e "\n---> Testing cdd-ts"
    (cd cdd-ts && npm run build --if-present || true)
    ./scripts/check_conformance_project.sh cdd-ts "$MARKDOWN_TARGET" node dist/cli.js || true
fi

# 2. cdd-c (C)
if [ -d "cdd-c" ]; then
    echo -e "\n---> Testing cdd-c"
    (cd cdd-c && make)
    ./scripts/check_conformance_project.sh cdd-c "$MARKDOWN_TARGET" ./bin/cdd-c || true
fi

# 3. cdd-cpp (C++)
if [ -d "cdd-cpp" ]; then
    echo -e "\n---> Testing cdd-cpp"
    (cd cdd-cpp && make build)
    ./scripts/check_conformance_project.sh cdd-cpp "$MARKDOWN_TARGET" ./build/cdd-cpp || true
fi

# 4. cdd-csharp (C#)
if [ -d "cdd-csharp" ]; then
    echo -e "\n---> Testing cdd-csharp"
    (cd cdd-csharp && dotnet build --configuration Release)
    ./scripts/check_conformance_project.sh cdd-csharp "$MARKDOWN_TARGET" dotnet run --project src/Cdd.OpenApi.Cli --configuration Release -- || true
fi

# 5. cdd-go (Go)
if [ -d "cdd-go" ]; then
    echo -e "\n---> Testing cdd-go"
    (cd cdd-go && go build -o bin/cdd_go ./cmd/cdd-go)
    ./scripts/check_conformance_project.sh cdd-go "$MARKDOWN_TARGET" ./bin/cdd_go || true
fi

# 6. cdd-java (Java)
if [ -d "cdd-java" ]; then
    echo -e "\n---> Testing cdd-java"
    # cdd-java uses gradlew run, which compiles on the fly.
    # We pass it as the command sequence.
    ./scripts/check_conformance_project.sh cdd-java "$MARKDOWN_TARGET" ./gradlew run --args= || true
fi

# 7. cdd-kotlin (Kotlin)
if [ -d "cdd-kotlin" ]; then
    echo -e "\n---> Testing cdd-kotlin"
    # Similar to Java, Kotlin uses gradlew
    ./scripts/check_conformance_project.sh cdd-kotlin "$MARKDOWN_TARGET" ./gradlew run --args= || true
fi

# 8. cdd-php (PHP)
if [ -d "cdd-php" ]; then
    echo -e "\n---> Testing cdd-php"
    ./scripts/check_conformance_project.sh cdd-php "$MARKDOWN_TARGET" php bin/cdd-php || true
fi

# 9. cdd-python-all (Python)
if [ -d "cdd-python-all" ]; then
    echo -e "\n---> Testing cdd-python-all"
    (cd cdd-python-all && pip install -e .)
    ./scripts/check_conformance_project.sh cdd-python-all "$MARKDOWN_TARGET" cdd-python-all || true
fi

# 10. cdd-ruby (Ruby)
if [ -d "cdd-ruby" ]; then
    echo -e "\n---> Testing cdd-ruby"
    ./scripts/check_conformance_project.sh cdd-ruby "$MARKDOWN_TARGET" ruby bin/cdd-ruby || true
fi

# 11. cdd-rust (Rust)
if [ -d "cdd-rust" ]; then
    echo -e "\n---> Testing cdd-rust"
    # Note: Using `cargo run -p cdd-cli --` directly within the wrapper
    # we need the target client flag which adds complexity. We'll invoke it using the cargo binary directly if built.
    (cd cdd-rust && cargo build -p cdd-cli --release)
    ./scripts/check_conformance_project.sh cdd-rust "$MARKDOWN_TARGET" ./target/release/cdd-cli || true
fi

# 12. cdd-sh (Shell)
if [ -d "cdd-sh" ]; then
    echo -e "\n---> Testing cdd-sh"
    ./scripts/check_conformance_project.sh cdd-sh "$MARKDOWN_TARGET" ./cdd.sh || true
fi

# 13. cdd-swift (Swift)
if [ -d "cdd-swift" ]; then
    echo -e "\n---> Testing cdd-swift"
    (cd cdd-swift && swift build -c release)
    ./scripts/check_conformance_project.sh cdd-swift "$MARKDOWN_TARGET" .build/release/cdd-swift || true
fi

echo -e "\n=========================================================="
echo "All toolchains tested. Conformance tracking table updated."
echo "=========================================================="