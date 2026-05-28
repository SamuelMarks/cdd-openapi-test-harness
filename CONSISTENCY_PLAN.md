# CDD Generators Consistency Analysis & Action Plan

This document outlines the findings from a cross-language analysis of the `cdd-{LANGUAGE}` code generators (C, C++, Go, Rust, TypeScript, Python, and Ruby). The goal is to ensure a unified API, CLI interface, and JSON-RPC interface across all language implementations.

## 1. Subcommand Names (CLI)
**Status:** ✅ **Consistent**

The core set of subcommands is universally supported across all generators. Language-specific extensions (like `sync` in Python, `to_orm` in TS, or `scaffold` in Rust) are allowed, but the common subset is aligned.

**Action Items:**
- [x] Ensure `from_openapi to_sdk` is present.
- [x] Ensure `from_openapi to_sdk_cli` is present.
- [x] Ensure `from_openapi to_server` is present.
- [x] Ensure `to_openapi` is present.
- [x] Ensure `to_docs_json` is present.
- [x] Ensure `serve_json_rpc` is present.

## 2. Command and Subcommand CLI arguments (Flags)
**Status:** ⚠️ **Mostly Consistent**

The core flags (long and short variants) are functionally implemented across all tools. However, there are minor behavioral differences in how parsers handle single-dash vs. double-dash flags.

**Action Items:**
- [x] `-i` and `--input` (Common input path/URL)
- [x] `--input-dir` (Directory for specs)
- [x] `-o` and `--output` (Output path)
- [x] `--no-github-actions` (Disable CI scaffolding)
- [x] `--no-installable-package` (Disable package/build scaffolding)
- [x] `--tests` (Enable integration tests/mocks)
- [x] `--no-imports` and `--no-wrapping` (Specific to `to_docs_json`)
- [ ] **Go CLI Fix:** Remove custom logic in `cdd-go/cmd/cdd-go/main.go` that intercepts and fails single-dash long flags (`-flag`), allowing the native Go `flag` package to handle them gracefully as standard.

## 3. Command and Subcommand CLI Docstrings
**Status:** ✅ **Consistent**

While the exact presentation depends on the native argument parsing library (e.g., `clap`, `commander`, `argparse`), the semantic meaning and intent of the help text are well-aligned across all tools.

**Action Items:**
- [x] `from_openapi`: "Generate code from an OpenAPI specification."
- [x] `to_openapi`: "Generate an OpenAPI specification from source code."
- [x] `to_docs_json`: "Generate JSON documentation with code snippets for an OpenAPI specification."
- [x] `serve_json_rpc`: "Expose CLI interface as a JSON-RPC server."

## 4. JSON-RPC SDK Naming and Parameter Structure (The Interface)
**Status:** ❌ **Highly Inconsistent**

The `serve_json_rpc` endpoints are severely fragmented. They lack a unified schema for method names, parameter objects, and response structures. Additionally, several lower-level languages provide incomplete or stubbed JSON-RPC implementations.

### 4A. JSON-RPC Method Naming (`method` field)
There is a fundamental disagreement on how nested CLI commands (`from_openapi to_sdk`) should map to JSON-RPC methods.

**Current State:**
- **Flattened (TS, Ruby):** Uses `from_openapi_to_sdk`, `from_openapi_to_server`.
- **Nested (Go, Python):** Uses `from_openapi` as the method, passing `"subcommand": "to_sdk"` inside the `params` object.

**Action Items:**
- [ ] Define a standard schema (recommendation: Flattened method names `from_openapi_to_sdk` to match standard JSON-RPC design patterns).
- [ ] Refactor `cdd-go` to support flattened RPC method names.
- [ ] Refactor `cdd-python-all` to support flattened RPC method names.

### 4B. JSON-RPC Parameter Structures (`params` field)
The keys used inside the `params` payload vary drastically, making it impossible to use a single client to communicate with all language servers.

**Current State (`to_openapi`):**
- **TS:** `{ "input": "..." }`
- **Python:** `{ "file": "..." }`
- **Ruby:** `{ "f": "..." }` or `{ "filepath": "..." }`
- **Go:** Expects a raw string array mapped to CLI arguments: `["-i", "foo.go"]`

**Action Items:**
- [ ] Standardize `to_openapi` params to strictly require `{ "input": "...", "output": "..." }` across all languages.
- [ ] Update `cdd-python-all` JSON-RPC handler (`to_openapi`).
- [ ] Update `cdd-ruby` JSON-RPC handler (`to_openapi`).
- [ ] Update `cdd-go` JSON-RPC handler to parse a JSON object for `to_openapi` rather than a string array.

**Current State (`from_openapi_*`):**
- **Go:** Accepts both a mapped JSON object and a raw string array.
- **Python, TS, Ruby:** Accept mapped JSON objects, but internal keys vary slightly.

**Action Items:**
- [ ] Standardize `from_openapi_*` params to strictly require `{ "input": "...", "input_dir": "...", "output": "...", "no_github_actions": bool, "no_installable_package": bool, "tests": bool }`.
- [ ] Deprecate string array argument parsing in `cdd-go` JSON-RPC endpoints.
- [ ] Ensure all boolean flags map correctly to JSON booleans (`true`/`false`), not strings.

### 4C. Stubbed and Incomplete Server Implementations
The systems languages (C, C++, Rust) currently have broken or stubbed JSON-RPC server implementations.

**Current State:**
- **Rust (`cdd-rust`):** Parses JSON-RPC natively and handles `version`, but hardcodes a `-32601 Method not found` error for all code generation endpoints.
- **C++ (`cdd-cpp`):** Starts an HTTP server, but the actual HTTP handler (`cdd_cpp::server::serve_json_rpc`) ignores the request body and returns a hardcoded string: `{"jsonrpc":"2.0","id":null,"error":{"code":-32601,"message":"Method not found"}}`.
- **C (`cdd-c`):** Sets up a raw TCP socket. It completely ignores incoming HTTP requests/headers/bodies and blindly flushes a hardcoded HTTP 200 `{"jsonrpc": "2.0", "result": "ok", "id": 1}` response to any incoming TCP connection.

**Action Items:**
- [ ] **Rust:** Wire up `from_openapi_to_sdk`, `from_openapi_to_sdk_cli`, `from_openapi_to_server`, `to_openapi`, and `to_docs_json` within the `handle_rpc` async router in `serve_json_rpc.rs`.
- [ ] **C++:** Remove the hardcoded error string in `src/server/emit.cpp` and implement proper JSON deserialization (using `simdjson` or `parson`) to route requests to the internal library functions.
- [ ] **C:** Implement a lightweight HTTP parser in `serve_json_rpc.c`, parse the JSON-RPC payload using `parson`, and map it to the underlying `from_openapi_cli_main` and `to_openapi_cli_main` functions.
