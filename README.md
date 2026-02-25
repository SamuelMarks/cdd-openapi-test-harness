# Joint Cross-Language Test Suite for OpenAPI

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

1. **Create**: `POST /pet` with a randomized ID and state.
2. **Read**: `GET /pet/{id}` and assert properties.
3. **Update**: `PUT /pet` with modified state.
4. **Read**: `GET /pet/{id}` to verify state mutations.
5. **Delete**: `DELETE /pet/{id}`.
6. **Verify 404**: `GET /pet/{id}` to assert backend rejection/not-found logic.

## Setup & CI

GitHub actions are implemented in `.github/workflows/test.yml` to automatically initialize the submodules, boot up a `swaggerapi/petstore` local backend via Docker, and execute the test suites across each language.

See [USAGE.md](USAGE.md) for local development instructions.