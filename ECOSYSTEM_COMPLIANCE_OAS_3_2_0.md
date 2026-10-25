# CDD Ecosystem: OpenAPI 3.2.0 Compliance Dashboard

This document provides an ecosystem-wide view of **OpenAPI Specification (OAS) 3.2.0** support across all 13 Compiler Driven Development (`cdd-*`) language toolchains.

It is automatically synthesized from the individual `COMPLIANCE.md` trackers maintained within each submodule.

## Legend
- ✅ **Supported**: Fully parsed, represented in the AST, and emitted during code/spec generation.
- 🚧 **Partial**: Partially supported (e.g., parsed into AST or preserved in metadata, but not fully utilized in idiomatic code generation).
- ❌ **Missing / Unmentioned**: Not yet implemented or not tracked in the toolchain's compliance documentation.

## Compliance Matrix

| OAS 3.2.0 Feature Area | `cdd-c` | `cdd-cpp` | `cdd-csharp` | `cdd-go` | `cdd-java` | `cdd-kotlin` | `cdd-php` | `cdd-python-all` | `cdd-ruby` | `cdd-rust` | `cdd-sh` | `cdd-swift` | `cdd-ts` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Root (`$self`, `jsonSchemaDialect`, `webhooks`)** | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ |
| **Info (`summary`, `license.identifier`)** | ❌ | ✅ | ❌ | ❌ | ✅ | 🚧 | 🚧 | ❌ | ❌ | ❌ | ❌ | 🚧 | ❌ |
| **Server (`name`, `variables`)** | 🚧 | ✅ | ✅ | ✅ | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 |
| **Paths (`QUERY` method, `additionalOperations`)** | ❌ | ✅ | ❌ | 🚧 | ✅ | 🚧 | 🚧 | ❌ | ❌ | ❌ | 🚧 | 🚧 | ❌ |
| **Schema (JSON Schema 2020-12 / Dynamic Refs / `discriminator.defaultMapping`)** | 🚧 | ✅ | ✅ | 🚧 | ✅ | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 |
| **Media Type (`itemSchema`, `prefixEncoding`, `itemEncoding`)** | ❌ | ✅ | ❌ | ❌ | ✅ | 🚧 | ✅ | ❌ | ❌ | ❌ | ❌ | 🚧 | ❌ |
| **Parameter (`example` / `examples` / `content`)** | 🚧 | ✅ | ✅ | 🚧 | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 |
| **Response (`summary`, `headers`, `links`)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ |
| **Security (`oauth2MetadataUrl`, `deviceAuthorization`, `deprecated`)** | 🚧 | ✅ | ✅ | 🚧 | ✅ | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 | 🚧 |
| **Tags (`summary`, `parent`, `kind`)** | ❌ | ✅ | 🚧 | 🚧 | 🚧 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 🚧 | ❌ |
| **XML (`nodeType` replaces `attribute`/`wrapped`)** | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | 🚧 | ❌ |
| **Example (`dataValue`, `serializedValue`)** | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🚧 | ❌ |
| **Links / Callbacks (`$ref`, expressions)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ |
| **Webhooks (Top-level `webhooks` map)** | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ | 🚧 | ✅ | ✅ | ✅ | ✅ | 🚧 | ✅ |

## Toolchain Compliance Summaries

### [`cdd-c`](./cdd-c/COMPLIANCE.md) — C (C89)
- **Scorecard**: 4/14 Supported (✅), 4/14 Partial (🚧), 6/14 Missing/Unmentioned (❌)
- **Overview**: This project strives to fully implement the [OpenAPI Specification Version 3.2.0](https://raw.githubusercontent.com/OAI/OpenAPI-Specification/refs/heads/main/versions/3.2.0.md).

### [`cdd-cpp`](./cdd-cpp/COMPLIANCE.md) — C++
- **Scorecard**: 14/14 Supported (✅), 0/14 Partial (🚧), 0/14 Missing/Unmentioned (❌)
- **Overview**: Supported specifications:

### [`cdd-csharp`](./cdd-csharp/COMPLIANCE.md) — C#
- **Scorecard**: 8/14 Supported (✅), 1/14 Partial (🚧), 5/14 Missing/Unmentioned (❌)
- **Overview**: This document tracks `cdd-csharp`'s compliance with **OpenAPI 3.2.0**, **Swagger 2.0**, **Arazzo 1.1.0**, and **Model Context Protocol (MCP) 1.0.0**.

### [`cdd-go`](./cdd-go/COMPLIANCE.md) — Go
- **Scorecard**: 5/14 Supported (✅), 5/14 Partial (🚧), 4/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-go` achieves 100% compliance with all major Swagger 2.0, OpenAPI 3.2.0, Arazzo 1.1.0, and Model Context Protocol (MCP 1.0.0) concepts.

### [`cdd-java`](./cdd-java/COMPLIANCE.md) — Java
- **Scorecard**: 11/14 Supported (✅), 3/14 Partial (🚧), 0/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-java` provides bidirectional compliance across **OpenAPI 3.2.0**, **Arazzo 1.1.0**, **Model Context Protocol (MCP) 1.0.0**, and **Swagger 2.0**.

### [`cdd-kotlin`](./cdd-kotlin/COMPLIANCE.md) — Kotlin (Multiplatform)
- **Scorecard**: 10/14 Supported (✅), 3/14 Partial (🚧), 1/14 Missing/Unmentioned (❌)
- **Overview**: This document tracks support for Swagger 2.0, OpenAPI 3.2.0, Arazzo 1.1.0, and Model Context Protocol (MCP) 1.0.0 features in the `cdd-kotlin` toolchain.

### [`cdd-php`](./cdd-php/COMPLIANCE.md) — PHP
- **Scorecard**: 7/14 Supported (✅), 5/14 Partial (🚧), 2/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-php` implements full bidirectional compilation and conformance across the following specifications and ecosystems:

### [`cdd-python-all`](./cdd-python-all/COMPLIANCE.md) — Python
- **Scorecard**: 4/14 Supported (✅), 4/14 Partial (🚧), 6/14 Missing/Unmentioned (❌)
- **Overview**: This project strives to fully implement the [OpenAPI Specification Version 3.2.0](https://raw.githubusercontent.com/OAI/OpenAPI-Specification/refs/heads/main/versions/3.2.0.md).

### [`cdd-ruby`](./cdd-ruby/COMPLIANCE.md) — Ruby
- **Scorecard**: 4/14 Supported (✅), 4/14 Partial (🚧), 6/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-ruby` strives for full compliance with [Swagger 2.0 and OpenAPI 3.2.0](https://raw.githubusercontent.com/OAI/OpenAPI-Specification/refs/heads/main/versions/3.2.0.md).

### [`cdd-rust`](./cdd-rust/COMPLIANCE.md) — Rust
- **Scorecard**: 4/14 Supported (✅), 4/14 Partial (🚧), 6/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-rust` is fully compliant with the following standards:

### [`cdd-sh`](./cdd-sh/COMPLIANCE.md) — Shell (/bin/sh)
- **Scorecard**: 4/14 Supported (✅), 5/14 Partial (🚧), 5/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-sh` targets the Swagger 2.0, OpenAPI 3.2.0, and Arazzo 1.1.0 specifications.

### [`cdd-swift`](./cdd-swift/COMPLIANCE.md) — Swift
- **Scorecard**: 0/14 Supported (✅), 14/14 Partial (🚧), 0/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-swift` implements bidirectional compilation across **OpenAPI 3.2.0**, **Swagger 2.0**, **Arazzo 1.1.0**, and the **Model Context Protocol (MCP 1.0.0)**.

### [`cdd-ts`](./cdd-ts/COMPLIANCE.md) — TypeScript
- **Scorecard**: 4/14 Supported (✅), 4/14 Partial (🚧), 6/14 Missing/Unmentioned (❌)
- **Overview**: `cdd-ts` strives for 100% compliance with [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html), [Swagger 2.0](https://spec.openapis.org/oas/v2.0.html), [Arazzo 1.1.0](https://spec.openapis.org/arazzo/v1.1.0.html), and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## Key OpenAPI 3.2.0 Advancements Tracked

1. **Root Self-Identification & Dialect**: `$self` URI resolution and `jsonSchemaDialect` (defaulting to JSON Schema Draft 2020-12).
2. **HTTP `QUERY` Method & `additionalOperations`**: First-class support for `query` operations on Path Items alongside arbitrary custom HTTP methods via `additionalOperations`.
3. **Streaming & Multipart Media Types**: `itemSchema` for sequential/streaming payloads (e.g., `application/jsonl`, `text/event-stream`) and positional `prefixEncoding` / `itemEncoding`.
4. **Hierarchical & Typed Tags**: Enhanced Tag Objects featuring `summary`, `parent` (nested tag hierarchies), and `kind` (e.g., `nav`, `badge`, `audience`).
5. **Modernized Security Schemes**: OAuth 2.0 Device Authorization Flow (`deviceAuthorization`), `oauth2MetadataUrl` (RFC 8414), and `deprecated` security scheme flags.
6. **Structured Examples & XML `nodeType`**: Separation of `dataValue` and `serializedValue` in Example Objects, and unified `nodeType` (`element`, `attribute`, `text`, `cdata`, `none`) in XML Objects.
7. **Discriminator `defaultMapping`**: Fallback schema mapping when a payload's discriminator property value does not match an explicit mapping.
