cdd-openapi-test-harness
========================

[![Roundtrip Test Suite](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/roundtrip.yml/badge.svg)](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/roundtrip.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This repository orchestrates end-to-end integration and roundtrip tests for code generators built with Compiler Driven Development (CDD). 

It validates that toolchains built for multiple target languages (e.g., Angular, Kotlin, Rust, Python, Swift) can correctly parse OpenAPI 3.0/3.2.0 specifications, generate idiomatic code (SDKs, handlers, models), and crucially, extract the exact same OpenAPI document back out of the generated code (AST).

## Architecture

This project ties together independent Git repositories (submodules) containing language-specific CDD toolchains. It tests them against the official OpenAPI specification examples pulled directly from the `OAI/OpenAPI-Specification` repository.

### Submodules

| Repository | Language | Client or Server | Extra features | OpenAPI Standard | CI Status |
|---|---|---|---|---|---|
| [`cdd-c`](https://github.com/SamuelMarks/cdd-c) | C (C89) | Client | FFI | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-c/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-c/actions/workflows/ci.yml) |
| [`cdd-cpp`](https://github.com/SamuelMarks/cdd-cpp) | C++ | Client | Upgrades Swagger & Google Discovery to OpenAPI 3.2.0 | Swagger 2.0 until OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-cpp/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-cpp/actions/workflows/ci.yml) |
| [`cdd-csharp`](https://github.com/SamuelMarks/cdd-csharp) | C# | Client | CLR | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-csharp/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-csharp/actions/workflows/ci.yml) |
| [`cdd-go`](https://github.com/SamuelMarks/cdd-go) | Go | Client |  | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-go/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-go/actions/workflows/ci.yml) |
| [`cdd-java`](https://github.com/SamuelMarks/cdd-java) | Java | Client | | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-java/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-java/actions/workflows/ci.yml) |
| [`cdd-kotlin`](https://github.com/offscale/cdd-kotlin) | Kotlin (Multiplatform) | Client | Auto-Admin UI | OpenAPI 3.2.0 | [![CI](https://github.com/offscale/cdd-kotlin/actions/workflows/ci.yml/badge.svg)](https://github.com/offscale/cdd-kotlin/actions/workflows/ci.yml) |
| [`cdd-php`](https://github.com/SamuelMarks/cdd-php) | PHP | Client |  | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-php/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-php/actions/workflows/ci.yml) |
| [`cdd-python-all`](https://github.com/offscale/cdd-python-all) | Python | Client |  | OpenAPI 3.2.0 | [![CI](https://github.com/offscale/cdd-python-all/actions/workflows/ci.yml/badge.svg)](https://github.com/offscale/cdd-python-all/actions/workflows/ci.yml) |
| [`cdd-ruby`](https://github.com/SamuelMarks/cdd-ruby) | Ruby | Client |  | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-ruby/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-ruby/actions/workflows/ci.yml) |
| [`cdd-rust`](https://github.com/SamuelMarks/cdd-rust) | Rust | Client & Server | CLI frontend for SDK | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-rust/actions/workflows/ci-cargo.yml/badge.svg)](https://github.com/SamuelMarks/cdd-rust/actions/workflows/ci-cargo.yml) |
| [`cdd-sh`](https://github.com/SamuelMarks/cdd-sh) | Shell (/bin/sh) | Client |  | OpenAPI 3.2.0 | [![CI](https://github.com/SamuelMarks/cdd-sh/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelMarks/cdd-sh/actions/workflows/ci.yml) |
| [`cdd-swift`](https://github.com/SamuelMarks/cdd-swift) | Swift | Client |  | OpenAPI 3.2.0 | [![Swift](https://github.com/SamuelMarks/cdd-swift/actions/workflows/swift.yml/badge.svg)](https://github.com/SamuelMarks/cdd-swift/actions/workflows/swift.yml) |
| [`cdd-ts`](https://github.com/offscale/cdd-ts) | TypeScript | Client | Auto-Admin UI; Angular; fetch; Axios; Node.js | OpenAPI 3.2.0 & Swagger 2 | [![Tests and coverage](https://github.com/offscale/cdd-ts/actions/workflows/tests_and_coverage.yml/badge.svg)](https://github.com/offscale/cdd-ts/actions/workflows/tests_and_coverage.yml) |

- **OAI-OpenAPI-Specification**: The official OpenAPI repository used for sourcing raw, versioned test YAML files (`api-with-examples.yaml`, `callback-example.yaml`, `petstore.yaml`, etc.).

### Standardized Roundtrip Lifecycle

Every CDD toolchain must support bidirectional synchronization. The test harness verifies this through a strict sequence:

1. **from_openapi (Generation)**: The toolchain parses an official OpenAPI YAML file and emits idiomatic code (e.g., Swift structs, Python FastAPI routes, Angular services).
2. **to_openapi (Extraction)**: The toolchain parses the Abstract Syntax Tree (AST) of the code it just generated and reconstructs a valid OpenAPI document.
3. **Compilation/Validation**: The generated code must compile cleanly (e.g., `swift build`, `cargo check`, `tsc`), and the extracted OpenAPI must be structurally compliant.

### Current Ecosystem Status

This table provides a snapshot of the current local integration capability and the functional status of a full `from_openapi` ↔ `to_openapi` roundtrip against `petstore.json` for each tracked implementation.

| Implementation      | Type         | Local Test Status | Roundtrip Petstore JSON |
|---------------------|--------------|-------------------|-------------------------|
| `cdd-c`             | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-cpp`           | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-csharp`        | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-go`            | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-java`          | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-kotlin`        | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-php`           | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-python-all`    | `client_cli` | ✅ Passed          | ✅ Passed                |
| `cdd-ruby`          | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-rust`          | `server`     | ✅ Passed          | ✅ Passed                |
| `cdd-sh`            | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-swift`         | `client`     | ✅ Passed          | ✅ Passed                |
| `cdd-ts`            | `client`     | ✅ Passed          | ✅ Passed                |

### Testing Coverage

This repository tests both the native builds and WebAssembly (WASM) targets (if supported by the implementation's `WASM.md`).

| Repository | Native Build/Tests | WASM Build/Tests | Reason if Skipped |
|---|---|---|---|
| `cdd-c` | ✅ Yes | ✅ Yes | |
| `cdd-cpp` | ✅ Yes | ✅ Yes | |
| `cdd-csharp` | ✅ Yes | ✅ Yes | |
| `cdd-go` | ✅ Yes | ✅ Yes | |
| `cdd-java` | ✅ Yes | ❌ No | Out of scope as per WASM.md |
| `cdd-kotlin` | ✅ Yes | ❌ No | Unsupported as per WASM.md |
| `cdd-php` | ✅ Yes | ✅ Yes | |
| `cdd-python-all` | ✅ Yes | ✅ Yes | |
| `cdd-ruby` | ✅ Yes | ✅ Yes | |
| `cdd-rust` | ✅ Yes | ❌ No | Missing WASM support / WASM.md |
| `cdd-sh` | ✅ Yes | ❌ No | Missing WASM support / WASM.md |
| `cdd-swift` | ✅ Yes | ❌ No | Missing WASM support / WASM.md |
| `cdd-ts` | ✅ Yes | ❌ No | Missing WASM support / WASM.md |

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