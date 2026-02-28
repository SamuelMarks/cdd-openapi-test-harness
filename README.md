cdd-openapi-test-harness
========================

[![Roundtrip Test Suite](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/roundtrip.yml/badge.svg)](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/roundtrip.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This repository orchestrates end-to-end integration and roundtrip tests for code generators built with Contract-Driven Development (CDD). 

It validates that toolchains built for multiple target languages (e.g., Angular, Kotlin, Rust, Python, Swift) can correctly parse OpenAPI 3.0/3.2.0 specifications, generate idiomatic code (SDKs, handlers, models), and crucially, extract the exact same OpenAPI document back out of the generated code (AST).

## Architecture

This project ties together independent Git repositories (submodules) containing language-specific CDD toolchains. It tests them against the official OpenAPI specification examples pulled directly from the `OAI/OpenAPI-Specification` repository.

### Submodules

- **cdd-web-ng**: The Angular (TypeScript) client and admin UI generator.
- **cdd-kotlin**: The Kotlin Multiplatform (KMP) client generator.
- **cdd-rust**: The Rust Actix-Web server scaffolding and integration test generator.
- **cdd-python-client**: The Python bidirectional client, mock server, and Pytest generator utilizing `libcst`.
- **cdd-swift**: The Swift bidirectional URLSession client and Codable model generator.
- **cdd-csharp**: The C# code generator and parser for ASP.NET and models.
- **cdd-go**: The Go toolchain for scaffolding routing structures and structs.
- **cdd-sh**: The Shell script code generator and OpenAPI compiler for Bash.
- **OAI-OpenAPI-Specification**: The official OpenAPI repository used for sourcing raw, versioned test YAML files (`api-with-examples.yaml`, `callback-example.yaml`, `petstore.yaml`, etc.).

### Standardized Roundtrip Lifecycle

Every CDD toolchain must support bidirectional synchronization. The test harness verifies this through a strict sequence:

1. **from_openapi (Generation)**: The toolchain parses an official OpenAPI YAML file and emits idiomatic code (e.g., Swift structs, Python FastAPI routes, Angular services).
2. **to_openapi (Extraction)**: The toolchain parses the Abstract Syntax Tree (AST) of the code it just generated and reconstructs a valid OpenAPI document.
3. **Compilation/Validation**: The generated code must compile cleanly (e.g., `swift build`, `cargo check`, `tsc`), and the extracted OpenAPI must be structurally compliant.

## Setup & CI

GitHub actions are implemented in `.github/workflows/roundtrip.yml` to automatically initialize the submodules, configure the language environments (Node, Java, Rust, Python, Swift, Go, .NET, Bash), and execute the roundtrip test suites across each language.

See [USAGE.md](USAGE.md) for local development and testing instructions.

---

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.