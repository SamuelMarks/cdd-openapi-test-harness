#!/usr/bin/env python3
"""Generates the `ECOSYSTEM_COMPLIANCE_OAS_3_2_0.md` dashboard (`scripts/generate_dashboard.py`).

Parses the `COMPLIANCE.md` files in each CDD toolchain submodule to evaluate
OpenAPI 3.2.0 feature support, and generates a consolidated Markdown compliance
matrix without executing file writes at module import time.
"""

import os
import sys
from typing import Dict, List, Optional, Tuple

TOOLCHAINS: Dict[str, str] = {
    "cdd-c": "C (C89)",
    "cdd-cpp": "C++",
    "cdd-csharp": "C#",
    "cdd-go": "Go",
    "cdd-java": "Java",
    "cdd-kotlin": "Kotlin (Multiplatform)",
    "cdd-php": "PHP",
    "cdd-python-all": "Python",
    "cdd-ruby": "Ruby",
    "cdd-rust": "Rust",
    "cdd-sh": "Shell (`/bin/sh`)",
    "cdd-swift": "Swift",
    "cdd-ts": "TypeScript",
}

FEATURES: Dict[str, List[str]] = {
    "Root (`$self`, `jsonSchemaDialect`, `webhooks`)": [
        "$self",
        "jsonschemadialect",
        "webhooks",
    ],
    "Info (`summary`, `license.identifier`)": ["summary", "identifier"],
    "Server (`name`, `variables`)": ["server", "variables"],
    "Paths (`QUERY` method, `additionalOperations`)": [
        "query",
        "additionaloperations",
    ],
    "Schema (JSON Schema 2020-12 / Dynamic Refs / `discriminator.defaultMapping`)": [
        "2020-12",
        "defaultmapping",
        "discriminator",
        "schema",
    ],
    "Media Type (`itemSchema`, `prefixEncoding`, `itemEncoding`)": [
        "itemschema",
        "prefixencoding",
        "itemencoding",
    ],
    "Parameter (`example` / `examples` / `content`)": [
        "parameter",
        "examples",
    ],
    "Response (`summary`, `headers`, `links`)": ["response", "links"],
    "Security (`oauth2MetadataUrl`, `deviceAuthorization`, `deprecated`)": [
        "oauth2metadataurl",
        "deviceauthorization",
        "security",
    ],
    "Tags (`summary`, `parent`, `kind`)": ["parent", "kind", "tag"],
    "XML (`nodeType` replaces `attribute`/`wrapped`)": ["nodetype", "xml"],
    "Example (`dataValue`, `serializedValue`)": [
        "datavalue",
        "serializedvalue",
    ],
    "Links / Callbacks (`$ref`, expressions)": ["callback", "link"],
    "Webhooks (Top-level `webhooks` map)": ["webhook"],
}


def analyze_compliance(file_path: str) -> Dict[str, str]:
    """Analyze a toolchain's `COMPLIANCE.md` file to determine OAS 3.2.0 support.

    Args:
        file_path: Path to the `COMPLIANCE.md` file for a specific toolchain.

    Returns:
        Dict[str, str]: Mapping from feature category name to status string.
    """
    if not os.path.exists(file_path):
        return dict.fromkeys(FEATURES, "❓ Missing Docs")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    lower_content = content.lower()
    results: Dict[str, str] = {}

    full_compliance_claims: Tuple[str, ...] = (
        "100% compliant with the openapi 3.2.0",
        "supports the entire openapi 3.2.0 specification",
        "fully supports openapi 3.2.0",
    )
    if any(claim in lower_content for claim in full_compliance_claims):
        return dict.fromkeys(FEATURES, "✅ Supported")

    nl = chr(10)
    lines = content.splitlines()
    in_table = False
    table_rows: List[Tuple[str, str]] = []

    for line in lines:
        if "|" in line and ("Feature" in line or "Object" in line or "Component" in line or "Status" in line):
            in_table = True
            continue
        if in_table and "|" in line and "---" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                table_rows.append((parts[0].lower(), parts[-1].lower()))

    supported_section = ""
    pending_section = ""
    current_section = ""
    for line in lines:
        if line.startswith("##") or line.startswith("###"):
            header = line.lower()
            if (
                "supported" in header
                or "implemented" in header
                or "1." in header
                or "2." in header
                or "3." in header
                or "4." in header
            ):
                current_section = "supported"
            elif (
                "unimplemented" in header
                or "pending" in header
                or "unsupported" in header
                or "missing" in header
                or "partial" in header
                or "limitations" in header
                or "out of scope" in header
            ):
                current_section = "pending"
            else:
                current_section = "other"

        if current_section == "supported":
            supported_section += line.lower() + nl
        elif current_section == "pending":
            pending_section += line.lower() + nl

    for feat_name, keywords in FEATURES.items():
        status = "❓ Unknown"

        if table_rows:
            for row_feat, row_stat in table_rows:
                if any(kw in row_feat for kw in keywords):
                    if "✅" in row_stat or "full" in row_stat or "supported" in row_stat or "yes" in row_stat:
                        status = "✅ Supported"
                        break
                    if (
                        "🚧" in row_stat
                        or "⏳" in row_stat
                        or "partial" in row_stat
                        or "progress" in row_stat
                        or "planned" in row_stat
                    ):
                        status = "🚧 Partial"
                        break
                    if (
                        "❌" in row_stat
                        or "no" in row_stat
                        or "unsupported" in row_stat
                        or "missing" in row_stat
                        or "n/a" in row_stat
                    ):
                        status = "❌ Missing"
                        break

        if status == "❓ Unknown":
            in_supp = any(kw in supported_section for kw in keywords)
            in_pend = any(kw in pending_section for kw in keywords)

            if in_supp and not in_pend:
                status = "✅ Supported"
            elif in_supp and in_pend:
                status = "🚧 Partial"
            elif in_pend and not in_supp:
                status = "❌ Missing"
            elif any(kw in lower_content for kw in keywords):
                status = "🚧 Partial / Mentioned"
            else:
                status = "❌ Unmentioned"

        results[feat_name] = status

    return results


def render_dashboard(root_dir: str = ".") -> str:
    """Render the consolidated OpenAPI 3.2.0 compliance dashboard Markdown string.

    Args:
        root_dir: Root directory containing the `cdd-*` toolchain folders.

    Returns:
        str: Generated Markdown content for `ECOSYSTEM_COMPLIANCE_OAS_3_2_0.md`.
    """
    matrix: Dict[str, Dict[str, str]] = {}
    for tc in TOOLCHAINS:
        comp_path = os.path.join(root_dir, tc, "COMPLIANCE.md")
        matrix[tc] = analyze_compliance(comp_path)

    nl = chr(10)
    lines: List[str] = [
        "# CDD Ecosystem: OpenAPI 3.2.0 Compliance Dashboard",
        "",
        "This document provides an ecosystem-wide view of **OpenAPI Specification (OAS) 3.2.0** support across all 13 Compiler Driven Development (`cdd-*`) language toolchains.",
        "",
        "It is automatically synthesized from the individual `COMPLIANCE.md` trackers maintained within each submodule.",
        "",
        "## Legend",
        "- ✅ **Supported**: Fully parsed, represented in the AST, and emitted during code/spec generation.",
        "- 🚧 **Partial**: Partially supported (e.g., parsed into AST or preserved in metadata, but not fully utilized in idiomatic code generation).",
        "- ❌ **Missing / Unmentioned**: Not yet implemented or not tracked in the toolchain's compliance documentation.",
        "",
        "## Compliance Matrix",
        "",
    ]

    tc_keys = list(TOOLCHAINS.keys())
    header_row = "| OAS 3.2.0 Feature Area | " + " | ".join([f"`{tc}`" for tc in tc_keys]) + " |"
    sep_row = "| :--- | " + " | ".join([":---:" for _ in tc_keys]) + " |"
    lines.append(header_row)
    lines.append(sep_row)

    for feat in FEATURES:
        row = f"| **{feat}** |"
        for tc in tc_keys:
            val = matrix[tc].get(feat, "❓")
            if "✅" in val:
                short_val = "✅"
            elif "🚧" in val:
                short_val = "🚧"
            elif "❌" in val:
                short_val = "❌"
            else:
                short_val = "❓"
            row += f" {short_val} |"
        lines.append(row)

    lines.extend(
        [
            "",
            "## Toolchain Compliance Summaries",
            "",
        ]
    )

    for tc, lang in TOOLCHAINS.items():
        comp_path = os.path.join(root_dir, tc, "COMPLIANCE.md")
        supp_count = sum(1 for v in matrix[tc].values() if "✅" in v)
        part_count = sum(1 for v in matrix[tc].values() if "🚧" in v)
        miss_count = sum(1 for v in matrix[tc].values() if "❌" in v)
        total = len(FEATURES)

        lines.append(f"### [`{tc}`](./{tc}/COMPLIANCE.md) — {lang}")
        lines.append(
            f"- **Scorecard**: {supp_count}/{total} Supported (✅), {part_count}/{total} Partial (🚧), {miss_count}/{total} Missing/Unmentioned (❌)"
        )

        if os.path.exists(comp_path):
            with open(comp_path, encoding="utf-8") as f:
                first_para = ""
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#") and not s.startswith("|") and not s.startswith("-"):
                        first_para = s
                        break
                if first_para:
                    lines.append(f"- **Overview**: {first_para}")
        lines.append("")

    lines.extend(
        [
            "## Key OpenAPI 3.2.0 Advancements Tracked",
            "",
            "1. **Root Self-Identification & Dialect**: `$self` URI resolution and `jsonSchemaDialect` (defaulting to JSON Schema Draft 2020-12).",
            "2. **HTTP `QUERY` Method & `additionalOperations`**: First-class support for `query` operations on Path Items alongside arbitrary custom HTTP methods via `additionalOperations`.",
            "3. **Streaming & Multipart Media Types**: `itemSchema` for sequential/streaming payloads (e.g., `application/jsonl`, `text/event-stream`) and positional `prefixEncoding` / `itemEncoding`.",
            "4. **Hierarchical & Typed Tags**: Enhanced Tag Objects featuring `summary`, `parent` (nested tag hierarchies), and `kind` (e.g., `nav`, `badge`, `audience`).",
            "5. **Modernized Security Schemes**: OAuth 2.0 Device Authorization Flow (`deviceAuthorization`), `oauth2MetadataUrl` (RFC 8414), and `deprecated` security scheme flags.",
            "6. **Structured Examples & XML `nodeType`**: Separation of `dataValue` and `serializedValue` in Example Objects, and unified `nodeType` (`element`, `attribute`, `text`, `cdata`, `none`) in XML Objects.",
            "7. **Discriminator `defaultMapping`**: Fallback schema mapping when a payload's discriminator property value does not match an explicit mapping.",
            "",
        ]
    )

    return nl.join(lines)


def generate_dashboard(
    root_dir: str = ".",
    output_file: Optional[str] = None,
) -> str:
    """Generate and write the compliance dashboard Markdown file.

    Args:
        root_dir: Root directory containing the `cdd-*` submodules.
        output_file: Destination path. Defaults to `<root_dir>/ECOSYSTEM_COMPLIANCE_OAS_3_2_0.md`.

    Returns:
        str: The rendered Markdown content written to `output_file`.
    """
    target_path = (
        output_file if output_file is not None else os.path.join(root_dir, "ECOSYSTEM_COMPLIANCE_OAS_3_2_0.md")
    )
    dashboard_md = render_dashboard(root_dir)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(dashboard_md)
    print("COMPLIANCE.md dashboard generated successfully.")
    return dashboard_md


def main(root_dir: Optional[str] = None, output_file: Optional[str] = None) -> int:
    """CLI entrypoint for `generate_dashboard.py`.

    Args:
        root_dir: Optional root directory override.
        output_file: Optional output file path override.

    Returns:
        int: Exit status code (0 on success).
    """
    resolved_root = root_dir if root_dir is not None else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    generate_dashboard(resolved_root, output_file=output_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
