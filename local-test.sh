#!/bin/sh
set -e

# ==========================================
# Script: local-test.sh
# Description: Orchestrates local execution of native tests, WASM builds, and roundtrip tests
#              across all CDD toolchains.
# Usage: ./local-test.sh [roundtrip|all|only-test]
# Configuration Variables:
#   IGNORE_TESTS: Comma-separated list of toolchains to skip.
#   ONLY_TEST: Comma-separated list of toolchains to exclusively run.
#   TARGET_TYPE: Filter by target type ('client', 'server', 'all'). Defaults to 'all'.
# ==========================================

IGNORE_TESTS="${IGNORE_TESTS:-}"
ONLY_TEST="${ONLY_TEST:-}"
TARGET_TYPE="${TARGET_TYPE:-all}"

# ==========================================
# Function: is_client
# Description: Determines if a given module is a client toolchain.
# Parameters:
#   $1 - Module name (e.g., cdd-c)
# Returns: 0 if client, 1 otherwise.
# ==========================================
is_client() {
    case "$1" in
        cdd-c|cdd-cpp|cdd-csharp|cdd-go|cdd-java|cdd-kotlin|cdd-php|cdd-python-all|cdd-ruby|cdd-rust|cdd-sh|cdd-swift|cdd-ts) return 0 ;;
        *) return 1 ;;
    esac
}

# ==========================================
# Function: is_server
# Description: Determines if a given module is a server toolchain.
# Parameters:
#   $1 - Module name (e.g., cdd-rust)
# Returns: 0 if server, 1 otherwise.
# ==========================================
is_server() {
    case "$1" in
        cdd-rust) return 0 ;;
        *) return 1 ;;
    esac
}

# ==========================================
# Function: should_run
# Description: Determines if a given module should be executed based on configuration variables.
# Parameters:
#   $1 - Module name (e.g., cdd-rust)
# Returns: 0 if it should run, 1 otherwise.
# ==========================================
should_run() {
    local module=$1

    if [ -n "$ONLY_TEST" ]; then
        if echo "$ONLY_TEST" | tr ',' '\n' | grep -q "^${module}$"; then
            return 0
        else
            return 1
        fi
    fi

    if [ -n "$IGNORE_TESTS" ] && echo "$IGNORE_TESTS" | tr ',' '\n' | grep -q "^${module}$"; then
        echo "Skipping $module (in IGNORE_TESTS)"
        return 1
    fi
    
    if [ "$TARGET_TYPE" = "client" ] && ! is_client "$module"; then
        echo "Skipping $module (not a client)"
        return 1
    fi

    if [ "$TARGET_TYPE" = "server" ] && ! is_server "$module"; then
        echo "Skipping $module (not a server)"
        return 1
    fi

    return 0
}

# ==========================================
# Function: cleanup
# Description: Stops the petstore_server Docker container upon exit.
# ==========================================
cleanup() {
    if command -v docker >/dev/null 2>&1; then
        if docker ps -q --filter "name=petstore_server" | grep -q .; then
            echo "Stopping petstore_server..."
            docker rm -f petstore_server >/dev/null 2>&1 || true
        fi
    fi
}
trap cleanup EXIT

# ==========================================
# Function: start_petstore
# Description: Starts the petstore_server via Docker for integration tests.
# ==========================================
start_petstore() {
    if command -v docker >/dev/null 2>&1; then
        echo "Starting petstore server via docker..."
        docker rm -f petstore_server >/dev/null 2>&1 || true
        docker run -d -p 8080:8080 -e SWAGGER_HOST="http://localhost:8080" -e SWAGGER_BASE_PATH="/v2" --name petstore_server swaggerapi/petstore >/dev/null
        sleep 3
    else
        echo "Warning: docker is not installed or available. Integration tests relying on localhost:8080 may fail."
    fi
}

# ==========================================
# Function: setup_emsdk
# Description: Sets up the Emscripten SDK required for WASM builds.
# ==========================================
setup_emsdk() {
    if [ ! -d "emsdk" ]; then
        echo "Setting up emsdk..."
        git clone https://github.com/emscripten-core/emsdk.git
        cd emsdk
        ./emsdk install latest
        ./emsdk activate latest
        cd ..
    fi
}

# ==========================================
# Function: run_wasm_builds
# Description: Triggers WebAssembly builds across applicable toolchains.
# ==========================================
run_wasm_builds() {
    echo "==================================="
    echo "Running WASM Builds"
    echo "==================================="
    setup_emsdk
    
    if should_run "cdd-c"; then
        echo "Building WASM for cdd-c..."
        (cd cdd-c && make build_wasm)
    fi
    
    if should_run "cdd-cpp"; then
        echo "Building WASM for cdd-cpp..."
        (cd cdd-cpp && make build_wasm)
    fi
    
    if should_run "cdd-csharp"; then
        echo "Building WASM for cdd-csharp..."
        (cd cdd-csharp && make build_wasm)
    fi
    
    if should_run "cdd-go"; then
        echo "Building WASM for cdd-go..."
        (cd cdd-go && make build_wasm)
    fi
    
    if should_run "cdd-php"; then
        echo "Building WASM for cdd-php..."
        (cd cdd-php && make build_wasm)
    fi
    
    if should_run "cdd-python-all"; then
        echo "Building WASM for cdd-python-all..."
        (cd cdd-python-all && make build_wasm)
    fi
    
    if should_run "cdd-ruby"; then
        echo "Building WASM for cdd-ruby..."
        (cd cdd-ruby && make build_wasm)
    fi
}

# ==========================================
# Function: run_test
# Description: Executes native tests for each enabled toolchain.
# ==========================================
run_test() {
    if should_run "cdd-ts"; then
        echo "==================================="
        echo "Running cdd-ts (Angular Integration) tests"
        echo "==================================="
        (
            cd cdd-ts
            if [ -f package-lock.json ]; then
                npm ci
            else
                npm i
            fi
            npm run build
            cd ..
            rm -rf angular-client
            npx -p @angular/cli ng new angular-client --defaults --skip-git
            cd angular-client
            npx ng add @angular/material --skip-confirmation || true
            cd ../cdd-ts
            node dist/cli.js from_openapi -i ../petstore.json --output ../angular-client/src/app/api
            
            cd ../angular-client
            if [ -f package-lock.json ]; then
                npm ci
            else
                npm i
            fi
            npm run test -- --watch=false
        )
    fi

    if should_run "cdd-kotlin"; then
        echo "==================================="
        echo "Running cdd-kotlin tests"
        echo "==================================="
        (
            cd cdd-kotlin
            rm -rf ../kotlin-client
            ./gradlew run --args="from_openapi -i ../petstore.json --clientName MyGeneratedClient --output ../kotlin-client --dateType string"
            
            mkdir -p ../kotlin-client/composeApp/src/commonTest/kotlin/com/example/auto
            cp tests/integration/kotlin-integration.kt ../kotlin-client/composeApp/src/commonTest/kotlin/com/example/auto/IntegrationTest.kt
            
            cd ../kotlin-client
            ./gradlew test
        )
    fi

    if should_run "cdd-go"; then
        echo "==================================="
        echo "Running cdd-go tests"
        echo "==================================="
        (
            cd cdd-go
            go test -v -coverprofile=coverage.out ./...
        )
    fi

    if should_run "cdd-csharp"; then
        echo "==================================="
        echo "Running cdd-csharp tests"
        echo "==================================="
        (
            cd cdd-csharp
            dotnet restore
            dotnet build --no-restore
            dotnet test tests/Cdd.OpenApi.Tests --no-build
        )
    fi

    if should_run "cdd-python-all"; then
        echo "==================================="
        echo "Running cdd-python-all tests"
        echo "==================================="
        (
            cd cdd-python-all
            make test
        )
    fi

    if should_run "cdd-rust"; then
        echo "==================================="
        echo "Running cdd-rust tests"
        echo "==================================="
        (
            cd cdd-rust
            cargo test
        )
    fi

    if should_run "cdd-swift"; then
        echo "==================================="
        echo "Running cdd-swift tests"
        echo "==================================="
        (
            cd cdd-swift
            swift test
        )
    fi

    if should_run "cdd-c"; then
        echo "==================================="
        echo "Running cdd-c tests"
        echo "==================================="
        (
            cd cdd-c
            make test
        )
    fi 

    if should_run "cdd-cpp"; then
        echo "==================================="
        echo "Running cdd-cpp tests"
        echo "==================================="
        (
            cd cdd-cpp
            make test
        )
    fi 

    if should_run "cdd-java"; then
        echo "==================================="
        echo "Running cdd-java tests"
        echo "==================================="
        (
            cd cdd-java
            make test
        )
    fi
    if should_run "cdd-php"; then
        echo "==================================="
        echo "Running cdd-php tests"
        echo "==================================="
        (
            cd cdd-php
            make test
        )
    fi 

    if should_run "cdd-ruby"; then
        echo "==================================="
        echo "Running cdd-ruby tests"
        echo "==================================="
        (
            cd cdd-ruby
            make test
        )
    fi 

    if should_run "cdd-sh"; then
        echo "==================================="
        echo "Running cdd-sh tests"
        echo "==================================="
        (
            cd cdd-sh
            ./test.sh
            if command -v shellcheck >/dev/null 2>&1; then
                shellcheck cdd.sh src/*/*.sh
            else
                echo "Warning: shellcheck is not installed. Skipping shellcheck."
            fi
        )
    fi
}

# ==========================================
# Function: run_roundtrip
# Description: Executes roundtrip tests against OpenAPI schemas for all enabled toolchains.
# ==========================================
run_roundtrip() {
    echo "==================================="
    echo "Running Roundtrip Tests"
    echo "==================================="
    # cdd-ts roundtrip
    if should_run "cdd-ts"; then
        (
            cd cdd-ts
            if [ -f package-lock.json ]; then npm ci; else npm i; fi
            npm run build
        )
        for file in OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
            if [ -f "$file" ]; then
                filename=$(basename "$file")
                echo "Testing $filename with cdd-ts..."
                node cdd-ts/dist/cli.js from_openapi -i "$file" --output temp-ng
                node cdd-ts/dist/cli.js to_openapi -f temp-ng --format yaml > temp-ng-spec.yaml
                rm -rf temp-ng temp-ng-spec.yaml
            fi
        done
    fi
    for file in OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            
            if should_run "cdd-kotlin"; then
                echo "Testing $filename with cdd-kotlin..."
                (
                    cd cdd-kotlin
                    ./gradlew run --args="from_openapi -i ../$file --clientName TestClient --output ../temp-kt"
                    ./gradlew run --args="to_openapi -f ../temp-kt --format yaml" > ../temp-kt-spec.yaml
                )
                rm -rf temp-kt temp-kt-spec.yaml
            fi
            
            if should_run "cdd-rust"; then
                echo "Testing $filename with cdd-rust..."
                (
                    cd cdd-rust
                    cargo run -p cdd-cli -- scaffold --openapi-path "../$file" --output-dir "../temp-rs/src/handlers"
                    cargo run -p cdd-cli -- test-gen --openapi-path "../$file" --output-path "../temp-rs/tests/api_contracts.rs" --app-factory "crate::create_app"
                )
                rm -rf temp-rs
            fi
        fi
    done

    if should_run "cdd-python-all"; then
        echo "Testing with cdd-python-all..."
        (
            cd cdd-python-all
            pip install pyyaml
            pip install -e .
            for file in ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
                if [ -f "$file" ]; then
                    mkdir -p temp-py
                    python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$file" > temp-py-spec.json
                    cdd sync --from-openapi temp-py-spec.json --to-python temp-py/
                    cdd sync --dir temp-py/
                    rm -rf temp-py temp-py-spec.json
                fi
            done
        )
    fi

    if should_run "cdd-swift"; then
        echo "Testing with cdd-swift..."
        (
            cd cdd-swift
            swift build -c release
            for file in ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
                if [ -f "$file" ]; then
                    python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$file" > temp-swift-spec.json
                    .build/release/cdd-swift generate-swift temp-swift-spec.json -o temp-swift.swift
                    .build/release/cdd-swift parse-swift temp-swift.swift -o temp-swift-out.json
                    rm -f temp-swift-spec.json temp-swift.swift temp-swift-out.json
                fi
            done
        )
    fi

    if should_run "cdd-sh"; then
        echo "Testing with cdd-sh..."
        (
            cd cdd-sh
            for file in ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
                if [ -f "$file" ]; then
                    python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$file" > temp-sh-spec.json
                    ./cdd.sh parse openapi temp-sh-spec.json
                    ./cdd.sh emit routes temp-routes.sh
                    ./cdd.sh parse routes temp-routes.sh
                    ./cdd.sh emit openapi temp-sh-out.json
                    rm -f temp-sh-spec.json temp-routes.sh temp-sh-out.json ast.json
                fi
            done
        )
    fi

    if should_run "cdd-go"; then
        echo "Testing with cdd-go..."
        (
            cd cdd-go
            for file in ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
                if [ -f "$file" ]; then
                    python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$file" > temp-go-spec.json
                    go run ./cmd/cdd_go from_openapi -i temp-go-spec.json -o temp-go
                    go run ./cmd/cdd_go to_openapi -i temp-go -o temp-go-out.json
                    rm -rf temp-go-spec.json temp-go temp-go-out.json
                fi
            done
        )
    fi

    if should_run "cdd-csharp"; then
        echo "Testing with cdd-csharp..."
        (
            cd cdd-csharp
            for file in ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
                if [ -f "$file" ]; then
                    python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < "$file" > temp-cs-spec.json
                    dotnet run --project src/Cdd.OpenApi.Cli -- from_openapi -i temp-cs-spec.json -o temp-cs
                    dotnet run --project src/Cdd.OpenApi.Cli -- to_openapi -i temp-cs -o temp-cs-out.json
                    rm -rf temp-cs-spec.json temp-cs temp-cs-out.json
                fi
            done
        )
    fi
}

# ==========================================
# Script Execution block
# ==========================================
if [ "$__BASH_SOURCED_TEST__" != "1" ]; then
    if [ "$1" = "roundtrip" ]; then
        run_roundtrip
        echo "==================================="
        echo "All roundtrip tests completed successfully!"
        echo "==================================="
    elif [ "$1" = "all" ]; then
        start_petstore
        run_test
        run_wasm_builds
        run_roundtrip
        echo "==================================="
        echo "All local tests completed successfully!"
        echo "==================================="
    elif [ "$1" = "only-test" ]; then
        start_petstore
        run_test
        echo "==================================="
        echo "All local tests completed successfully (WASM skipped)!"
        echo "==================================="
    else
        # default to test
        start_petstore
        run_test
        run_wasm_builds
        echo "==================================="
        echo "All test.yml local tests completed successfully!"
        echo "==================================="
        echo "Run '$0 roundtrip' to execute roundtrip tests."
    fi
fi
