# CDD OpenAPI Test Harness Tickets

This document tracks the work required to convert all non-WASM cross marks (❌) into passing tickets (✅) across the CDD toolchains.

## 1. Improved Adherence to the Interface
Ensure all `cdd-*` toolchains support the standard subcommands (`from_openapi`, `to_openapi`) and arguments (`-i, --input <path>`, `-o, --output <path>`).

- [x] **Ticket 1: Standardize `cdd-python-all` CLI**
  - **Action**: Deprecate `cdd sync --from-openapi` / `--to-python`. Implement `from_openapi -i <spec> -o <dir>` and `to_openapi -i <dir> -o <spec>`.
- [x] **Ticket 2: Standardize `cdd-swift` CLI**
  - **Action**: Alias or rename `generate-swift` and `parse-swift` to `from_openapi` and `to_openapi` with `-i` and `-o` flags.
- [x] **Ticket 3: Standardize `cdd-sh` CLI**
  - **Action**: Migrate `./cdd.sh parse/emit` syntax to standard `from_openapi` and `to_openapi`.
- [x] **Ticket 4: Standardize `cdd-rust` CLI**
  - **Action**: Map the server `scaffold` and `test-gen` verbs behind `from_openapi` and `to_openapi` subcommands for harmonization in `local-test.sh`. Ensure `-i` and `-o` are respected.
- [x] **Ticket 5: Standardize `cdd-ts` and `cdd-kotlin` CLI arguments**
  - **Action**: Change the extraction flag from `-f <dir>` to `-i, --input <dir>` and `--format yaml > stdout` to `-o, --output <file>`.
- [x] **Ticket 6: Update Test Harness Orchestration**
  - **Action**: Update `run_roundtrip()` in `local-test.sh` to uniformly invoke `[binary] from_openapi -i ... -o ...` and `[binary] to_openapi -i ... -o ...` across all projects. Remove hardcoded stdout redirections and bespoke flags.

## 2. Improved Implementation
Resolve the `❌ Failed (Not Impl)` and `❌ Failed` states under the **Roundtrip Petstore JSON** column.

- [x] **Ticket 7: Implement AST-to-OpenAPI for `cdd-c`**
  - **Action**: Build the `to_openapi` extraction logic to reconstruct the OpenAPI spec from the generated C AST. Wire it to the CLI.
- [x] **Ticket 8: Implement AST-to-OpenAPI for `cdd-cpp`**
  - **Action**: Build the `to_openapi` extraction logic for C++. Wire it to the CLI.
- [x] **Ticket 9: Implement AST-to-OpenAPI for `cdd-php`**
  - **Action**: Build both `from_openapi` and `to_openapi` extraction modules for PHP. Add standard CLI interface.
- [x] **Ticket 10: Implement AST-to-OpenAPI for `cdd-ruby`**
  - **Action**: Build `from_openapi` and `to_openapi` logic for Ruby. Add standard CLI interface.
- [x] **Ticket 11: Fix `cdd-go` Roundtrip Logic**
  - **Action**: Debug `to_openapi`. The Go extraction currently fails to correctly output structurally valid `petstore.json` matching the input.
- [x] **Ticket 12: Fix `cdd-python-all` Roundtrip Logic**
  - **Action**: Investigate diffs between the input Python JSON/YAML spec and the emitted output to fulfill the roundtrip check constraints.
- [x] **Ticket 13: Fix `cdd-swift` Roundtrip Logic**
  - **Action**: Fix the AST extraction logic in Swift so the parsed models correctly reflect the `petstore.json` input attributes.

## 3. Improved Testing
Target the toolchains showing `❌ Failed` under **Local Test Status**, which block local workflow stability.

- [x] **Ticket 14: Fix `cdd-kotlin` local tests**
  - **Action**: Investigate why `./gradlew test` in `local-test.sh` fails. Fix integration test paths or broken assertions in the generated `IntegrationTest.kt`.
- [x] **Ticket 15: Fix `cdd-php` local tests**
  - **Action**: Resolve `make test` failures in `cdd-php`. Update coverage dependencies and assertions.
- [x] **Ticket 16: Fix `cdd-python-all` local tests**
  - **Action**: Diagnose the failing `make test`. Likely AST mismatches or missing PyPI dependencies that need locking.
- [x] **Ticket 17: Fix `cdd-ruby` local tests**
  - **Action**: Resolve the exceptions thrown during `make test` in the Ruby environment.
- [x] **Ticket 18: Fix `cdd-swift` local tests**
  - **Action**: Resolve build/compilation errors running `swift test`.
- [x] **Ticket 19: Externalize `cdd-java` Roundtrip Test Orchestration**
  - **Action**: While `cdd-java` has a `✅ Passed` roundtrip status, it's missing from `run_roundtrip()` in `local-test.sh`. Extract the roundtrip verification from `make test` and add it to the bash harness utilizing the new standard CLI.