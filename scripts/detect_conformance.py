"""Detects OpenAPI 3.2.0 conformance by comparing input and output specs.

This script loads an original OpenAPI specification and a roundtripped output
specification, then walks through the documents to record which OpenAPI objects
and properties have been successfully preserved. It can output the results to
the console or update a markdown conformance table.
"""

import json
import yaml
import sys
import argparse
import re
from pathlib import Path

supported_features = set()


def record(obj_name, prop=None):
    """Records a supported feature or property.

    Args:
        obj_name (str): The name of the OpenAPI object (e.g., 'Info Object').
        prop (str, optional): The name of the property within the object. Defaults to None.
    """
    supported_features.add(obj_name)
    if prop:
        supported_features.add(f"{obj_name} (`{prop}`)")


def is_ref(node):
    """Checks if a given node is a Reference Object.

    Args:
        node (dict or any): The node to check.

    Returns:
        bool: True if the node is a dictionary containing a '$ref' key, False otherwise.
    """
    return isinstance(node, dict) and "$ref" in node


def walk_list(in_list, out_list, walk_fn):
    """Walks through lists of OpenAPI objects and applies a given function to matched pairs.

    Args:
        in_list (list): The list of input objects.
        out_list (list): The list of output objects.
        walk_fn (function): The function to apply to matching (input, output) object pairs.
    """
    if not isinstance(in_list, list) or not isinstance(out_list, list):
        return
    for in_item in in_list:
        # Try to find a matching item in out_list (heuristic: by $ref or name, or just try all)
        # For simplicity, we just walk pairwise if ordered, or try to find a match.
        # To be safe, we just compare zip
        for out_item in out_list:
            if isinstance(in_item, dict) and isinstance(out_item, dict):
                walk_fn(in_item, out_item)


def walk_dict(in_dict, out_dict, walk_fn):
    """Walks through dictionaries of OpenAPI objects and applies a given function to matched pairs.

    Args:
        in_dict (dict): The dictionary of input objects.
        out_dict (dict): The dictionary of output objects.
        walk_fn (function): The function to apply to matching (input, output) object pairs.
    """
    if not isinstance(in_dict, dict) or not isinstance(out_dict, dict):
        return
    for k, in_val in in_dict.items():
        if k in out_dict:
            walk_fn(in_val, out_dict[k])


# --- Specific Walkers ---


def walk_contact(in_node, out_node):
    """Walks and compares Contact Objects.

    Args:
        in_node (dict): The input Contact Object.
        out_node (dict): The output Contact Object.
    """
    record("Contact Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("Contact Object", k)


def walk_license(in_node, out_node):
    """Walks and compares License Objects.

    Args:
        in_node (dict): The input License Object.
        out_node (dict): The output License Object.
    """
    record("License Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("License Object", k)


def walk_info(in_node, out_node):
    """Walks and compares Info Objects.

    Args:
        in_node (dict): The input Info Object.
        out_node (dict): The output Info Object.
    """
    record("Info Object")
    for k in in_node:
        if k in out_node:
            if in_node[k] == out_node[k]:
                record("Info Object", k)
            if k == "contact":
                walk_contact(in_node[k], out_node[k])
            if k == "license":
                walk_license(in_node[k], out_node[k])


def walk_server_var(in_node, out_node):
    """Walks and compares Server Variable Objects.

    Args:
        in_node (dict): The input Server Variable Object.
        out_node (dict): The output Server Variable Object.
    """
    record("Server Variable Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("Server Variable Object", k)


def walk_server(in_node, out_node):
    """Walks and compares Server Objects.

    Args:
        in_node (dict): The input Server Object.
        out_node (dict): The output Server Object.
    """
    record("Server Object")
    for k in in_node:
        if k in out_node:
            if in_node[k] == out_node[k]:
                record("Server Object", k)
            if k == "variables":
                walk_dict(in_node[k], out_node[k], walk_server_var)


def walk_external_docs(in_node, out_node):
    """Walks and compares External Documentation Objects.

    Args:
        in_node (dict): The input External Documentation Object.
        out_node (dict): The output External Documentation Object.
    """
    record("External Documentation Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("External Documentation Object", k)


def walk_schema(in_node, out_node):
    """Walks and compares Schema Objects or Reference Objects.

    Args:
        in_node (dict): The input Schema Object.
        out_node (dict): The output Schema Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Schema Object")
    for k in in_node:
        if k in out_node:
            # We don't deep equality check schemas completely here due to complexity, but we check if key exists
            record("Schema Object", k)
            if k in ["items", "additionalProperties"] and isinstance(in_node[k], dict):
                walk_schema(in_node[k], out_node[k])
            if k in ["allOf", "anyOf", "oneOf"] and isinstance(in_node[k], list):
                walk_list(in_node[k], out_node[k], walk_schema)
            if k == "externalDocs":
                walk_external_docs(in_node[k], out_node[k])
            if k == "discriminator":
                record("Discriminator Object")
                for dk in in_node[k]:
                    if dk in out_node[k]:
                        record("Discriminator Object", dk)
            if k == "xml":
                record("XML Object")
                for xk in in_node[k]:
                    if xk in out_node[k]:
                        record("XML Object", xk)


def walk_header(in_node, out_node):
    """Walks and compares Header Objects.

    Args:
        in_node (dict): The input Header Object.
        out_node (dict): The output Header Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Header Object")
    for k in in_node:
        if k in out_node:
            record("Header Object", k)
            if k == "schema":
                walk_schema(in_node[k], out_node[k])


def walk_encoding(in_node, out_node):
    """Walks and compares Encoding Objects.

    Args:
        in_node (dict): The input Encoding Object.
        out_node (dict): The output Encoding Object.
    """
    record("Encoding Object")
    for k in in_node:
        if k in out_node:
            record("Encoding Object", k)
            if k == "headers":
                walk_dict(in_node[k], out_node[k], walk_header)


def walk_media_type(in_node, out_node):
    """Walks and compares Media Type Objects.

    Args:
        in_node (dict): The input Media Type Object.
        out_node (dict): The output Media Type Object.
    """
    record("Media Type Object")
    for k in in_node:
        if k in out_node:
            record("Media Type Object", k)
            if k == "schema":
                walk_schema(in_node[k], out_node[k])
            if k == "encoding":
                walk_dict(in_node[k], out_node[k], walk_encoding)


def walk_parameter(in_node, out_node):
    """Walks and compares Parameter Objects.

    Args:
        in_node (dict): The input Parameter Object.
        out_node (dict): The output Parameter Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Parameter Object")
    for k in in_node:
        if k in out_node:
            record("Parameter Object", k)
            if k == "schema":
                walk_schema(in_node[k], out_node[k])
            if k == "content":
                walk_dict(in_node[k], out_node[k], walk_media_type)


def walk_request_body(in_node, out_node):
    """Walks and compares Request Body Objects.

    Args:
        in_node (dict): The input Request Body Object.
        out_node (dict): The output Request Body Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Request Body Object")
    for k in in_node:
        if k in out_node:
            record("Request Body Object", k)
            if k == "content":
                walk_dict(in_node[k], out_node[k], walk_media_type)


def walk_link(in_node, out_node):
    """Walks and compares Link Objects.

    Args:
        in_node (dict): The input Link Object.
        out_node (dict): The output Link Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Link Object")
    for k in in_node:
        if k in out_node:
            record("Link Object", k)


def walk_response(in_node, out_node):
    """Walks and compares Response Objects.

    Args:
        in_node (dict): The input Response Object.
        out_node (dict): The output Response Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Response Object")
    for k in in_node:
        if k in out_node:
            record("Response Object", k)
            if k == "headers":
                walk_dict(in_node[k], out_node[k], walk_header)
            if k == "content":
                walk_dict(in_node[k], out_node[k], walk_media_type)
            if k == "links":
                walk_dict(in_node[k], out_node[k], walk_link)


def walk_responses(in_node, out_node):
    """Walks and compares Responses Objects.

    Args:
        in_node (dict): The input Responses Object.
        out_node (dict): The output Responses Object.
    """
    record("Responses Object")
    for k in in_node:
        if k in out_node:
            record("Responses Object", k)
            walk_response(in_node[k], out_node[k])


def walk_callback(in_node, out_node):
    """Walks and compares Callback Objects.

    Args:
        in_node (dict): The input Callback Object.
        out_node (dict): The output Callback Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Callback Object")
    for k in in_node:
        if k in out_node:
            record("Callback Object", k)  # dynamic keys here
            walk_path_item(in_node[k], out_node[k])


def walk_operation(in_node, out_node):
    """Walks and compares Operation Objects.

    Args:
        in_node (dict): The input Operation Object.
        out_node (dict): The output Operation Object.
    """
    record("Operation Object")
    for k in in_node:
        if k in out_node:
            record("Operation Object", k)
            if k == "externalDocs":
                walk_external_docs(in_node[k], out_node[k])
            if k == "parameters":
                walk_list(in_node[k], out_node[k], walk_parameter)
            if k == "requestBody":
                walk_request_body(in_node[k], out_node[k])
            if k == "responses":
                walk_responses(in_node[k], out_node[k])
            if k == "callbacks":
                walk_dict(in_node[k], out_node[k], walk_callback)
            if k == "security":
                record("Security Requirement Object")


def walk_path_item(in_node, out_node):
    """Walks and compares Path Item Objects.

    Args:
        in_node (dict): The input Path Item Object.
        out_node (dict): The output Path Item Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Path Item Object")
    for k in in_node:
        if k in out_node:
            record("Path Item Object", k)
            if k in [
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
            ]:
                walk_operation(in_node[k], out_node[k])
            if k == "parameters":
                walk_list(in_node[k], out_node[k], walk_parameter)


def walk_paths(in_node, out_node):
    """Walks and compares Paths Objects.

    Args:
        in_node (dict): The input Paths Object.
        out_node (dict): The output Paths Object.
    """
    record("Paths Object")
    for k in in_node:
        if k in out_node:
            record("Paths Object", k)  # dynamic path strings
            walk_path_item(in_node[k], out_node[k])


def walk_oauth_flow(in_node, out_node):
    """Walks and compares OAuth Flow Objects.

    Args:
        in_node (dict): The input OAuth Flow Object.
        out_node (dict): The output OAuth Flow Object.
    """
    record("OAuth Flow Object")
    for k in in_node:
        if k in out_node:
            record("OAuth Flow Object", k)


def walk_oauth_flows(in_node, out_node):
    """Walks and compares OAuth Flows Objects.

    Args:
        in_node (dict): The input OAuth Flows Object.
        out_node (dict): The output OAuth Flows Object.
    """
    record("OAuth Flows Object")
    for k in in_node:
        if k in out_node:
            record("OAuth Flows Object", k)
            walk_oauth_flow(in_node[k], out_node[k])


def walk_security_scheme(in_node, out_node):
    """Walks and compares Security Scheme Objects.

    Args:
        in_node (dict): The input Security Scheme Object.
        out_node (dict): The output Security Scheme Object.
    """
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Security Scheme Object")
    for k in in_node:
        if k in out_node:
            record("Security Scheme Object", k)
            if k == "flows":
                walk_oauth_flows(in_node[k], out_node[k])


def walk_components(in_node, out_node):
    """Walks and compares Components Objects.

    Args:
        in_node (dict): The input Components Object.
        out_node (dict): The output Components Object.
    """
    record("Components Object")
    for k in in_node:
        if k in out_node:
            record("Components Object", k)
            if k == "schemas":
                walk_dict(in_node[k], out_node[k], walk_schema)
            if k == "responses":
                walk_dict(in_node[k], out_node[k], walk_response)
            if k == "parameters":
                walk_dict(in_node[k], out_node[k], walk_parameter)
            if k == "requestBodies":
                walk_dict(in_node[k], out_node[k], walk_request_body)
            if k == "securitySchemes":
                walk_dict(in_node[k], out_node[k], walk_security_scheme)
            if k == "links":
                walk_dict(in_node[k], out_node[k], walk_link)
            if k == "callbacks":
                walk_dict(in_node[k], out_node[k], walk_callback)
            if k == "headers":
                walk_dict(in_node[k], out_node[k], walk_header)


def walk_tag(in_node, out_node):
    """Walks and compares Tag Objects.

    Args:
        in_node (dict): The input Tag Object.
        out_node (dict): The output Tag Object.
    """
    record("Tag Object")
    for k in in_node:
        if k in out_node:
            record("Tag Object", k)
            if k == "externalDocs":
                walk_external_docs(in_node[k], out_node[k])


def walk_openapi_doc(in_node, out_node):
    """Walks and compares the root OpenAPI Objects.

    Args:
        in_node (dict): The input OpenAPI Object.
        out_node (dict): The output OpenAPI Object.
    """
    record("OpenAPI Object")
    for k in in_node:
        if k in out_node:
            record("OpenAPI Object", k)
            if k == "info":
                walk_info(in_node[k], out_node[k])
            if k == "servers":
                walk_list(in_node[k], out_node[k], walk_server)
            if k == "paths":
                walk_paths(in_node[k], out_node[k])
            if k == "components":
                walk_components(in_node[k], out_node[k])
            if k == "security":
                record("Security Requirement Object")
            if k == "tags":
                walk_list(in_node[k], out_node[k], walk_tag)
            if k == "externalDocs":
                walk_external_docs(in_node[k], out_node[k])


def load_doc(path):
    """Loads a JSON or YAML OpenAPI document.

    Args:
        path (str): The file path to load.

    Returns:
        dict: The parsed OpenAPI document.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml.safe_load(content)


def main():
    """Main execution block to run the conformance detection."""
    parser = argparse.ArgumentParser(description="Detect OpenAPI 3.2.0 conformance.")
    parser.add_argument(
        "--input", required=True, help="Path to the original input OpenAPI spec"
    )
    parser.add_argument(
        "--output", required=True, help="Path to the roundtripped OpenAPI spec"
    )
    parser.add_argument(
        "--markdown", help="Path to the markdown conformance table to update"
    )

    args = parser.parse_args()

    in_doc = load_doc(args.input)
    out_doc = load_doc(args.output)

    walk_openapi_doc(in_doc, out_doc)

    if args.markdown:
        md_path = Path(args.markdown)
        if not md_path.exists():
            print(f"Error: Markdown file {md_path} not found.")
            sys.exit(1)

        content = md_path.read_text()

        lines = content.split("\n")
        for i, line in enumerate(lines):
            # Example match: | **Info Object (`title`)** | `[ ]` , `[ ]` |
            m = re.match(r"^\|\s*\*\*(.*?)\*\*\s*\|(.*?)\|(.*?)\|", line)
            if m:
                feature_name = m.group(1).strip()
                if feature_name in supported_features:
                    # Update [ ] to [x] in the Presence column
                    # The presence column is group 2
                    presence_col = m.group(2)
                    new_presence = presence_col.replace("[ ]", "[x]")
                    lines[i] = line.replace(f"|{presence_col}|", f"|{new_presence}|")

        md_path.write_text("\n".join(lines))
        print(f"Successfully updated {md_path}")
    else:
        for f in sorted(list(supported_features)):
            print(f"- {f}")


if __name__ == "__main__":
    main()
