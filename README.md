cdd-openapi-test-harness
========================

[![Cross-Language Test Suite](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/test.yml/badge.svg)](https://github.com/SamuelMarks/cdd-openapi-test-harness/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This repository orchestrates end-to-end integration tests for code generators built with Codegen-Driven Development (CDD). 

It validates that client SDKs generated for multiple target languages (e.g., Angular, Kotlin, Rust, C) adhere to a 100% test coverage contract, maintain semantic equivalency, and perfectly integrate with a real backend.

## Architecture

This project ties together independent Git repositories (submodules) containing language-specific code generators, running them against a standard OpenAPI definition (`petstore.json`) and testing the emitted code against a real containerized backend.

### Submodules

- **cdd-web-ng**: The Angular (TypeScript) generator.
- **cdd-kotlin**: The Kotlin Multiplatform generator.

*(More generators like `cdd-rust` and `cdd-c` will be added in the future).*

### Standardized Lifecycle Spec

Every generated SDK must pass a strict sequence of CRUD operations to ensure absolute functional parity across languages:

0. **Create**: `POST /pet` with a randomized ID and state.
1. **Read**: `GET /pet/{id}` and assert properties.
2. **Update**: `PUT /pet` with modified state.
3. **Read**: `GET /pet/{id}` to verify state mutations.
4. **Delete**: `DELETE /pet/{id}`.
5. **Verify 404**: `GET /pet/{id}` to assert backend rejection/not-found logic.

## Setup & CI

GitHub actions are implemented in `.github/workflows/test.yml` to automatically initialize the submodules, boot up a `swaggerapi/petstore` local backend via Docker, and execute the test suites across each language.

See [USAGE.md](USAGE.md) for local development instructions.

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
