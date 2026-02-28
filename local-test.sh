#!/bin/sh
set -e

cleanup() {
    if command -v docker >/dev/null 2>&1; then
        if docker ps -q --filter "name=petstore_server" | grep -q .; then
            echo "Stopping petstore_server..."
            docker rm -f petstore_server >/dev/null 2>&1 || true
        fi
    fi
}
trap cleanup EXIT

# Start petstore server if docker is available
start_petstore() {
    if command -v docker >/dev/null 2>&1; then
        echo "Starting petstore server via docker..."
        docker run -d -p 8080:8080 -e SWAGGER_HOST="http://localhost:8080" -e SWAGGER_BASE_PATH="/v2" --name petstore_server swaggerapi/petstore >/dev/null
        sleep 3
    else
        echo "Warning: docker is not installed or available. Integration tests relying on localhost:8080 may fail."
    fi
}

run_test() {
    echo "==================================="
    echo "Running cdd-web-ng (Angular Integration) tests"
    echo "==================================="
    (
        cd cdd-web-ng
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
        cd ../cdd-web-ng
        node dist/cli.js from_openapi -i ../petstore.json --output ../angular-client/src/app/api
        
        cd ../angular-client
        if [ -f package-lock.json ]; then
            npm ci
        else
            npm i
        fi
        npm run test -- --watch=false
    )

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

    echo "==================================="
    echo "Running cdd-go tests"
    echo "==================================="
    (
        cd cdd-go
        go test -v -coverprofile=coverage.out ./...
    )

    echo "==================================="
    echo "Running cdd-csharp tests"
    echo "==================================="
    (
        cd cdd-csharp
        dotnet restore
        dotnet build --no-restore
        dotnet test tests/Cdd.OpenApi.Tests --no-build
    )

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
}

run_roundtrip() {
    echo "==================================="
    echo "Running Roundtrip Tests"
    echo "==================================="
    # cdd-web-ng roundtrip
    (
        cd cdd-web-ng
        if [ -f package-lock.json ]; then npm ci; else npm i; fi
        npm run build
    )
    for file in OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/*.yaml; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            echo "Testing $filename with cdd-web-ng..."
            node cdd-web-ng/dist/cli.js from_openapi -i "$file" --output temp-ng
            node cdd-web-ng/dist/cli.js to_openapi -f temp-ng --format yaml > temp-ng-spec.yaml
            rm -rf temp-ng temp-ng-spec.yaml
            
            echo "Testing $filename with cdd-kotlin..."
            (
                cd cdd-kotlin
                ./gradlew run --args="from_openapi -i ../$file --clientName TestClient --output ../temp-kt"
                ./gradlew run --args="to_openapi -f ../temp-kt --format yaml" > ../temp-kt-spec.yaml
            )
            rm -rf temp-kt temp-kt-spec.yaml
            
            echo "Testing $filename with cdd-rust..."
            (
                cd cdd-rust
                cargo run -p cdd-cli -- scaffold --openapi-path "../$file" --output-dir "../temp-rs/src/handlers"
                cargo run -p cdd-cli -- test-gen --openapi-path "../$file" --output-path "../temp-rs/tests/api_contracts.rs" --app-factory "crate::create_app"
            )
            rm -rf temp-rs
        fi
    done

    echo "Testing with cdd-python-client..."
    (
        cd cdd-python-client
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
}

if [ "$1" = "roundtrip" ]; then
    run_roundtrip
    echo "==================================="
    echo "All roundtrip tests completed successfully!"
    echo "==================================="
elif [ "$1" = "all" ]; then
    start_petstore
    run_test
    run_roundtrip
    echo "==================================="
    echo "All local tests completed successfully!"
    echo "==================================="
else
    # default to test
    start_petstore
    run_test
    echo "==================================="
    echo "All test.yml local tests completed successfully!"
    echo "==================================="
    echo "Run '$0 roundtrip' to execute roundtrip tests."
fi
