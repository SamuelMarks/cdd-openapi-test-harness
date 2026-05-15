#!/usr/bin/env python3
import os
import re

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_FILE = os.path.join(ROOT_DIR, "ECOSYSTEM_COMPLIANCE_OAS_3_2_0.md")

TOOLCHAINS = [
    "cdd-c", "cdd-cpp", "cdd-csharp", "cdd-go", "cdd-java", "cdd-kotlin",
    "cdd-php", "cdd-python-all", "cdd-ruby", "cdd-rust", "cdd-sh",
    "cdd-swift", "cdd-ts"
]

FEATURES = [
    "Info Object",
    "Server Object",
    "Components Object",
    "Paths Object",
    "Path Item Object",
    "Operation Object",
    "Parameter Object",
    "Request Body Object",
    "Responses Object",
    "Responses / Schema Object",
    "Reference Object",
    "OAuth Flows",
    "Security Requirement Object",
    "Links / Callbacks",
    "Webhooks"
]

def analyze_compliance(file_path):
    if not os.path.exists(file_path):
        return {f: "❌" for f in FEATURES}
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    text_lower = content.lower()
    status = {f: "❌" for f in FEATURES}
    
    # Check for broad full compliance claims
    if "full spec compliance achieved for all major openapi 3.2.0 concepts" in text_lower or \
       "100% compliance achieved" in text_lower or \
       ("fully compliant" in text_lower and "full support" in text_lower):
        status = {f: "✅" for f in FEATURES}
        # Still parse specific ❌ if they exist just in case
        
    # We can split by section to know if we are in a "supported" or "pending" block
    in_supported = False
    in_pending = False
    
    for line in content.split("\n"):
        line_lower = line.lower()
        if re.match(r"^#*\s*(Currently )?[Ss]upported.*", line, re.IGNORECASE) or re.match(r"^#*\s*Status.*", line, re.IGNORECASE) or re.match(r"^#*\s*Support Coverage", line, re.IGNORECASE) or re.match(r"^Currently supported features:", line):
            in_supported = True
            in_pending = False
        elif re.match(r"^#*\s*(To Be Implemented|Features pending|Work in Progress|Next Steps|Pending).*", line, re.IGNORECASE) or re.match(r"^Features pending:", line):
            in_supported = False
            in_pending = True
            
        # Parse table row: | Feature | ✅ |
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                feature_name = parts[1].lower()
                value = parts[2]
                for f in FEATURES:
                    if f.lower() in feature_name:
                        if "✅" in value:
                            status[f] = "✅"
                        elif "❌" in value:
                            status[f] = "❌"
                            
        # Parse lists
        # We map feature names to keywords
        keywords = {
            "Info Object": ["info object", "metadata", "descriptions, summaries"],
            "Server Object": ["server object", "server definition", "server definitions"],
            "Components Object": ["components object", "components", "core models"],
            "Paths Object": ["paths object", "paths", "routes", "routing", "path definitions", "operations & paths"],
            "Path Item Object": ["path item object", "path item"],
            "Operation Object": ["operation object", "operations", "methods"],
            "Parameter Object": ["parameter object", "parameters"],
            "Request Body Object": ["request body object", "request bodies", "request body"],
            "Responses Object": ["responses object", "responses"],
            "Responses / Schema Object": ["schema object", "schemas", "models"],
            "Reference Object": ["reference object", "references", "$ref"],
            "OAuth Flows": ["oauth flows", "oauth2"],
            "Security Requirement Object": ["security requirement", "security scheme", "security definitions", "security requirements"],
            "Links / Callbacks": ["links", "callbacks"],
            "Webhooks": ["webhooks"]
        }
        
        for f, kws in keywords.items():
            for kw in kws:
                if kw in line_lower:
                    if "✅" in line:
                        status[f] = "✅"
                    elif "❌" in line:
                        status[f] = "❌"
                    elif (line.strip().startswith("-") or line.strip().startswith("*")) and in_supported:
                        status[f] = "✅"
                    elif "fully supported" in line_lower or "fully implemented" in line_lower:
                        status[f] = "✅"
                    elif "supported" in line_lower and not "not supported" in line_lower:
                        # Be careful, could just be "Supported" header
                        if line.strip().startswith("-") or line.strip().startswith("*") or ":" in line:
                            status[f] = "✅"
                        
    # Additional manual overrides for specific wording:
    if "cdd-php" in file_path and "majority of openapi features" in text_lower:
        for f in ["Paths Object", "Operation Object", "Components Object", "Responses Object", "Request Body Object", "Parameter Object", "Server Object", "Info Object"]:
            status[f] = "✅"
    
    if "cdd-java" in file_path and "parsing core models, routes, responses" in text_lower:
        status["Components Object"] = "✅"
        status["Responses / Schema Object"] = "✅"
        status["Paths Object"] = "✅"
        status["Operation Object"] = "✅"
        status["Responses Object"] = "✅"

    if "cdd-cpp" in file_path and "100% compliant with basic structures" in text_lower:
        for f in ["Paths Object", "Operation Object", "Components Object", "Responses Object", "Request Body Object", "Parameter Object", "Server Object", "Info Object", "Responses / Schema Object", "Security Requirement Object"]:
            status[f] = "✅"
            
    # Make Path Item Object checked if Paths and Operations are checked
    if status["Paths Object"] == "✅" and status["Operation Object"] == "✅":
        status["Path Item Object"] = "✅"
        
    return status

dashboard_md = """# CDD OpenAPI Feature Support Dashboard

This dashboard automatically tracks the implementation status of key OpenAPI 3.2.0 features across the various CDD toolchains.

It is generated by parsing the `COMPLIANCE.md` files within each language-specific submodule.

## Support Matrix

| Feature | cdd-c | cdd-cpp | cdd-csharp | cdd-go | cdd-java | cdd-kotlin | cdd-php | cdd-python-all | cdd-ruby | cdd-rust | cdd-sh | cdd-swift | cdd-ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""

matrix = {f: [] for f in FEATURES}

for t in TOOLCHAINS:
    st = analyze_compliance(os.path.join(ROOT_DIR, t, "COMPLIANCE.md"))
    for f in FEATURES:
        matrix[f].append(st[f])

for f in FEATURES:
    row = f"| {f} | " + " | ".join(matrix[f]) + " |"
    dashboard_md += row + "\n"

dashboard_md += """
## Feature Definitions

*   **Info Object:** Parsing and emitting metadata about the API (title, version, description).
*   **Server Object:** Extracting server URLs and variable substitutions.
*   **Components Object:** Reusable schemas, responses, parameters, etc.
*   **Paths Object:** Routing definitions and endpoints.
*   **Path Item Object:** Operations available on a single path.
*   **Operation Object:** HTTP methods (GET, POST, etc.) and their specific details.
*   **Parameter Object:** Query, header, path, or cookie parameters.
*   **Request Body Object:** Request payloads.
*   **Responses Object:** Expected responses from an operation.
*   **Responses / Schema Object:** The data model of a response.
*   **Reference Object:** Resolving `$ref` pointers (internal and external).
*   **OAuth Flows:** Extracting OAuth2 security scheme definitions.
*   **Security Requirement Object:** Applying security schemes to operations.
*   **Links / Callbacks:** Advanced operation workflows.
*   **Webhooks:** Out-of-band callbacks.
"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(dashboard_md)

print("COMPLIANCE.md dashboard generated successfully.")
