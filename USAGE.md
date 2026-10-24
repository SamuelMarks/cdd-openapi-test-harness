# CDD OpenAPI Test Harness Usage

## 1. Initial Setup

Since this suite tests isolated generation engines and uses official OpenAPI examples, you must pull down all git submodules:

```sh
git submodule update --init --recursive
```

This will download:
- `cdd-c`
- `cdd-cpp`
- `cdd-csharp`
- `cdd-go`
- `cdd-java`
- `cdd-kotlin`
- `cdd-php`
- `cdd-python-all`
- `cdd-ruby`
- `cdd-rust`
- `cdd-sh`
- `cdd-swift`
- `cdd-ts`
- `OAI-OpenAPI-Specification`

## 2. Generate and Run Tests Locally

The primary test mechanism is the **Roundtrip Test**. This ensures a toolchain can generate code from an OpenAPI document, and then successfully parse that generated code back into an OpenAPI document.

You can find the official OpenAPI v3.0 test fixtures in `OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/`.

### Running the TypeScript Roundtrip Tests (`cdd-ts`)

First, ensure dependencies are installed and the CLI is built:
```sh
cd cdd-ts
npm install
npm run build
cd ..
```

Run the roundtrip:
```sh
node cdd-ts/dist/cli.js from_openapi to_sdk -i OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml --output temp-ng
node cdd-ts/dist/cli.js to_openapi -i temp-ng --format yaml -o temp-ng-spec.yaml
```

### Running the Kotlin Roundtrip Tests (`cdd-kotlin`)

```sh
cd cdd-kotlin
./gradlew run --args="from_openapi to_sdk -i ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml --output ../temp-kt"
./gradlew run --args="to_openapi -i ../temp-kt --format yaml -o ../temp-kt-spec.yaml"
```

### Running the Rust Scaffolding Tests (`cdd-rust`)

The Rust toolchain generates client and server-side Actix-Web scaffolding and integration contracts.

```sh
cd cdd-rust
cargo run -p cdd-cli -- from_openapi to_sdk -i "../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml" -o "../temp-rs"
cargo run -p cdd-cli -- to_openapi -i "../temp-rs/src" -o "../temp-rs/spec.yaml"
```

### Running the Python Roundtrip Tests (`cdd-python-all`)

The Python toolchain requires a virtual environment and `libcst`. It also natively synchronizes directories.

```sh
cd cdd-python-all
python3 -m venv venv
source venv/bin/activate
pip install pyyaml
pip install -e .
cd ..

mkdir -p temp-py
# Convert YAML to JSON for the Python CLI
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-py-spec.json

# Generate the Python code and extract back to OpenAPI
cdd-python from_openapi to_sdk -i temp-py-spec.json -o temp-py
cdd-python to_openapi -i temp-py -o temp-py-out.json
```

### Running the Swift Roundtrip Tests (`cdd-swift`)

The Swift toolchain uses SwiftSyntax to parse Swift structs back into OpenAPI schemas.

```sh
cd cdd-swift
swift build -c release
cd ..

# Convert YAML to JSON
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-swift-spec.json

# Generate the Swift Code
cdd-swift/.build/release/cdd-swift from_openapi to_sdk -i temp-swift-spec.json -o temp-swift
# Extract OpenAPI from the generated Swift code
cdd-swift/.build/release/cdd-swift to_openapi -i temp-swift/Sources/GeneratedSDK/models.swift -o temp-swift-out.json
```

### Running the Shell Roundtrip Tests (`cdd-sh`)

The shell script compiler supports loading specs and emitting POSIX shell scripts containing curl routes, or vice versa.

```sh
cd cdd-sh
# Convert YAML to JSON
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-sh-spec.json

# Generate shell SDK and re-emit OpenAPI JSON spec
./cdd.sh from_openapi -i temp-sh-spec.json -o temp-sh-dir
./cdd.sh to_openapi -i temp-sh-dir -o temp-sh-out.json
```

### Running the Go Roundtrip Tests (`cdd-go`)

The `cdd-go` CLI leverages Go `ast` to parse struct nodes and standard interface functions.

```sh
cd cdd-go
# Convert YAML to JSON
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-go-spec.json

# Scaffold the routes/models
go run ./cmd/cdd_go from_openapi -i temp-go-spec.json -o temp-go

# Extract spec from Go package
go run ./cmd/cdd_go to_openapi -i temp-go -o temp-go-out.json
```

### Running the C# Roundtrip Tests (`cdd-csharp`)

C# supports extracting OpenAPI schema data via the .NET Roslyn compiler API.

```sh
cd cdd-csharp
# Convert YAML to JSON
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-cs-spec.json

# Scaffold C# Models/API Interfaces
dotnet run --project src/Cdd.OpenApi.Cli -- from_openapi -i temp-cs-spec.json -o temp-cs

# Parse C# files and output spec
dotnet run --project src/Cdd.OpenApi.Cli -- to_openapi -i temp-cs -o temp-cs-out.json
```

## 3. Creating a new Target Language

To orchestrate a new codegen repository into this suite:

1. Create a `cdd-<language>` repository.
2. Ensure your language repository exposes a CLI executable.
3. Your CLI MUST support bidirectional synchronization (or the conceptual equivalent):
   * `from_openapi` (e.g. `cdd-lang from_openapi -i spec.json -o out_dir`)
   * `to_openapi` (e.g. `cdd-lang to_openapi -i path/to/code -o out_spec.json`)
4. Add the submodule: `git submodule add <remote-url> cdd-<language>`
5. Register it in `harness/registry.py` and integrate it into `.github/workflows/roundtrip.yml`.

## 4. Testing and Filtering

This project includes advanced filtering options via environment variables to target specific builds, environments, or toolchains. These apply to `local_test.py` and the GitHub Actions workflows.

### Generating the Testing Matrix

To programmatically test the entire ecosystem against the `petstore.json` specification, run:

```sh
# Ensure you have petstore_server running, or the docker engine available.
python3 local_test.py all
```

### Filtering Executions

If you want to isolate tests, you can leverage three environment variables:

1. **`ONLY_TEST`** (Whitelist): Targets specific implementations. Ignores all others.
   ```sh
   # Only test the TypeScript client generator and the C# generator
   ONLY_TEST="cdd-ts,cdd-csharp" python3 local_test.py only-test
   ```

2. **`IGNORE_TESTS`** (Blacklist): Skips specific implementations.
   ```sh
   # Skip testing the C and Ruby implementations
   IGNORE_TESTS="cdd-c,cdd-ruby" python3 local_test.py only-test
   ```

3. **`TARGET_TYPE`**: Filters by the target type of the implementation (`client` or `server`).
   ```sh
   # Test only the server generators
   TARGET_TYPE="server" python3 local_test.py roundtrip
   ```

## 5. OpenAPI Conformance Testing

This repository includes a universal Swagger 2.0 and OpenAPI 3.2.0 conformance testing suite that relies on deep AST object extraction. These scripts verify exactly which OpenAPI features (e.g., `Server Object`, `Security Scheme Object`, `Reference Object`) are preserved and supported when a toolchain parses a spec into code and re-extracts it.

The outputs are written directly into tracking markdown tables.

### Running Batch Conformance

To automatically build and test every `cdd-*` submodule for its conformance levels, execute:

```sh
python3 scripts/check_all_conformance.py
```

This will run through a suite of test YAML files from `OAI-OpenAPI-Specification`, attempt the bidirectional `from_openapi` -> `to_openapi` mapping, and tally up the features successfully emitted by the AST extractors.

### Checking a Specific Project

If you want to check a specific project or debug an extraction failure, you can use the project checker script. It requires the project directory, the output markdown file, and the CLI execution sequence for the toolchain:

```sh
# Example: Checking cdd-rust compliance
python3 scripts/check_conformance_project.py cdd-rust cdd-rust/conformance/openapi-3.2.0/client-sdk.md ./target/release/cdd-cli

# Example: Checking cdd-ts compliance
python3 scripts/check_conformance_project.py cdd-ts cdd-ts/conformance/openapi-3.2.0/client-sdk.md node dist/cli.js
```
