# CDD OpenAPI Test Harness Usage

## 1. Initial Setup

Since this suite tests isolated generation engines and uses official OpenAPI examples, you must pull down all git submodules:

```sh
git submodule update --init --recursive
```

This will download:
- `cdd-web-ng`
- `cdd-kotlin`
- `cdd-rust`
- `cdd-python-client`
- `cdd-swift`
- `cdd-csharp`
- `cdd-go`
- `cdd-sh`
- `OAI-OpenAPI-Specification`

## 2. Generate and Run Tests Locally

The primary test mechanism is the **Roundtrip Test**. This ensures a toolchain can generate code from an OpenAPI document, and then successfully parse that generated code back into an OpenAPI document.

You can find the official OpenAPI v3.0 test fixtures in `OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/`.

### Running the Angular Roundtrip Tests (`cdd-web-ng`)

First, ensure dependencies are installed and the CLI is built:
```sh
cd cdd-web-ng
npm install
npm run build
cd ..
```

Run the roundtrip:
```sh
node cdd-web-ng/dist/cli.js from_openapi -i OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml --output temp-ng
node cdd-web-ng/dist/cli.js to_openapi -f temp-ng --format yaml > temp-ng-spec.yaml
```

### Running the Kotlin Roundtrip Tests (`cdd-kotlin`)

```sh
cd cdd-kotlin
./gradlew run --args="from_openapi -i ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml --clientName TestClient --output ../temp-kt"
./gradlew run --args="to_openapi -f ../temp-kt --format yaml" > ../temp-kt-spec.yaml
```

### Running the Rust Scaffolding Tests (`cdd-rust`)

The Rust toolchain generates server-side Actix-Web scaffolding and integration contracts.

```sh
cd cdd-rust
cargo run -p cdd-cli -- scaffold --openapi-path "../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml" --output-dir "../temp-rs/src/handlers"
cargo run -p cdd-cli -- test-gen --openapi-path "../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml" --output-path "../temp-rs/tests/api_contracts.rs" --app-factory "crate::create_app"
```

### Running the Python Roundtrip Tests (`cdd-python-client`)

The Python toolchain requires a virtual environment and `libcst`. It also natively synchronizes directories. Note that the Python CLI currently expects JSON input.

```sh
cd cdd-python-client
python3 -m venv venv
source venv/bin/activate
pip install pyyaml
pip install -e .
cd ..

mkdir -p temp-py
# Convert YAML to JSON for the Python CLI
python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-py/spec.json

# Generate the Python code
cdd sync --from-openapi temp-py/spec.json --to-python temp-py/
# Sync the directory (extracts the AST back to openapi.json and regenerates)
cdd sync --dir temp-py/
```

### Running the Swift Roundtrip Tests (`cdd-swift`)

The Swift toolchain uses SwiftSyntax to parse Swift structs back into OpenAPI schemas. It also natively expects JSON input.

```sh
cd cdd-swift
swift build -c release
cd ..

# Convert YAML to JSON
python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-swift-spec.json

# Generate the Swift Code
cdd-swift/.build/release/cdd-swift generate-swift temp-swift-spec.json -o temp-swift.swift
# Extract OpenAPI from the generated Swift code
cdd-swift/.build/release/cdd-swift parse-swift temp-swift.swift -o temp-swift-out.json
```

### Running the Shell Roundtrip Tests (`cdd-sh`)

The shell script compiler supports loading specs and emitting bash scripts containing curl routes, or vice versa.

```sh
cd cdd-sh
# Convert YAML to JSON
python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-sh-spec.json

# Parse into ast.json
./cdd.sh parse openapi temp-sh-spec.json

# Emit bash routes script
./cdd.sh emit routes temp-routes.sh

# Re-parse routes script to ast.json
./cdd.sh parse routes temp-routes.sh

# Re-emit OpenAPI JSON spec
./cdd.sh emit openapi temp-sh-out.json
```

### Running the Go Roundtrip Tests (`cdd-go`)

The `cdd-go` cli leverages Go `ast` to parse the struct nodes and standard interface functions.

```sh
cd cdd-go
# Convert YAML to JSON
python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-go-spec.json

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
python -c "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)" < ../OAI-OpenAPI-Specification/_archive_/schemas/v3.0/pass/petstore.yaml > temp-cs-spec.json

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
   * `from_openapi` (e.g. `cdd-lang from_openapi -i spec.json`)
   * `to_openapi` (e.g. `cdd-lang to_openapi -f path/to/code`)
4. Add the submodule: `git submodule add <remote-url> cdd-<language>`
5. Integrate it into the CI loop in `.github/workflows/roundtrip.yml`.