import json
import yaml
import sys
import argparse
import re
from pathlib import Path

supported_features = set()

def record(obj_name, prop=None):
    supported_features.add(obj_name)
    if prop:
        supported_features.add(f"{obj_name} (`{prop}`)")

def is_ref(node):
    return isinstance(node, dict) and '$ref' in node

def walk_list(in_list, out_list, walk_fn):
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
    if not isinstance(in_dict, dict) or not isinstance(out_dict, dict):
        return
    for k, in_val in in_dict.items():
        if k in out_dict:
            walk_fn(in_val, out_dict[k])

# --- Specific Walkers ---

def walk_contact(in_node, out_node):
    record("Contact Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("Contact Object", k)

def walk_license(in_node, out_node):
    record("License Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("License Object", k)

def walk_info(in_node, out_node):
    record("Info Object")
    for k in in_node:
        if k in out_node:
            if in_node[k] == out_node[k]:
                record("Info Object", k)
            if k == 'contact': walk_contact(in_node[k], out_node[k])
            if k == 'license': walk_license(in_node[k], out_node[k])

def walk_server_var(in_node, out_node):
    record("Server Variable Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("Server Variable Object", k)

def walk_server(in_node, out_node):
    record("Server Object")
    for k in in_node:
        if k in out_node:
            if in_node[k] == out_node[k]:
                record("Server Object", k)
            if k == 'variables':
                walk_dict(in_node[k], out_node[k], walk_server_var)

def walk_external_docs(in_node, out_node):
    record("External Documentation Object")
    for k in in_node:
        if k in out_node and in_node[k] == out_node[k]:
            record("External Documentation Object", k)

def walk_schema(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Schema Object")
    for k in in_node:
        if k in out_node:
            # We don't deep equality check schemas completely here due to complexity, but we check if key exists
            record("Schema Object", k)
            if k in ['items', 'additionalProperties'] and isinstance(in_node[k], dict):
                walk_schema(in_node[k], out_node[k])
            if k in ['allOf', 'anyOf', 'oneOf'] and isinstance(in_node[k], list):
                walk_list(in_node[k], out_node[k], walk_schema)
            if k == 'externalDocs':
                walk_external_docs(in_node[k], out_node[k])
            if k == 'discriminator':
                record("Discriminator Object")
                for dk in in_node[k]:
                    if dk in out_node[k]: record("Discriminator Object", dk)
            if k == 'xml':
                record("XML Object")
                for xk in in_node[k]:
                    if xk in out_node[k]: record("XML Object", xk)

def walk_header(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Header Object")
    for k in in_node:
        if k in out_node:
            record("Header Object", k)
            if k == 'schema': walk_schema(in_node[k], out_node[k])

def walk_encoding(in_node, out_node):
    record("Encoding Object")
    for k in in_node:
        if k in out_node:
            record("Encoding Object", k)
            if k == 'headers': walk_dict(in_node[k], out_node[k], walk_header)

def walk_media_type(in_node, out_node):
    record("Media Type Object")
    for k in in_node:
        if k in out_node:
            record("Media Type Object", k)
            if k == 'schema': walk_schema(in_node[k], out_node[k])
            if k == 'encoding': walk_dict(in_node[k], out_node[k], walk_encoding)

def walk_parameter(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Parameter Object")
    for k in in_node:
        if k in out_node:
            record("Parameter Object", k)
            if k == 'schema': walk_schema(in_node[k], out_node[k])
            if k == 'content': walk_dict(in_node[k], out_node[k], walk_media_type)

def walk_request_body(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Request Body Object")
    for k in in_node:
        if k in out_node:
            record("Request Body Object", k)
            if k == 'content': walk_dict(in_node[k], out_node[k], walk_media_type)

def walk_link(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Link Object")
    for k in in_node:
        if k in out_node: record("Link Object", k)

def walk_response(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Response Object")
    for k in in_node:
        if k in out_node:
            record("Response Object", k)
            if k == 'headers': walk_dict(in_node[k], out_node[k], walk_header)
            if k == 'content': walk_dict(in_node[k], out_node[k], walk_media_type)
            if k == 'links': walk_dict(in_node[k], out_node[k], walk_link)

def walk_responses(in_node, out_node):
    record("Responses Object")
    for k in in_node:
        if k in out_node:
            record("Responses Object", k)
            walk_response(in_node[k], out_node[k])

def walk_callback(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Callback Object")
    for k in in_node:
        if k in out_node:
            record("Callback Object", k) # dynamic keys here
            walk_path_item(in_node[k], out_node[k])

def walk_operation(in_node, out_node):
    record("Operation Object")
    for k in in_node:
        if k in out_node:
            record("Operation Object", k)
            if k == 'externalDocs': walk_external_docs(in_node[k], out_node[k])
            if k == 'parameters': walk_list(in_node[k], out_node[k], walk_parameter)
            if k == 'requestBody': walk_request_body(in_node[k], out_node[k])
            if k == 'responses': walk_responses(in_node[k], out_node[k])
            if k == 'callbacks': walk_dict(in_node[k], out_node[k], walk_callback)
            if k == 'security': record("Security Requirement Object")

def walk_path_item(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Path Item Object")
    for k in in_node:
        if k in out_node:
            record("Path Item Object", k)
            if k in ['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']:
                walk_operation(in_node[k], out_node[k])
            if k == 'parameters':
                walk_list(in_node[k], out_node[k], walk_parameter)

def walk_paths(in_node, out_node):
    record("Paths Object")
    for k in in_node:
        if k in out_node:
            record("Paths Object", k) # dynamic path strings
            walk_path_item(in_node[k], out_node[k])

def walk_oauth_flow(in_node, out_node):
    record("OAuth Flow Object")
    for k in in_node:
        if k in out_node: record("OAuth Flow Object", k)

def walk_oauth_flows(in_node, out_node):
    record("OAuth Flows Object")
    for k in in_node:
        if k in out_node:
            record("OAuth Flows Object", k)
            walk_oauth_flow(in_node[k], out_node[k])

def walk_security_scheme(in_node, out_node):
    if is_ref(in_node) and is_ref(out_node):
        record("Reference Object", "$ref")
        return
    record("Security Scheme Object")
    for k in in_node:
        if k in out_node:
            record("Security Scheme Object", k)
            if k == 'flows': walk_oauth_flows(in_node[k], out_node[k])

def walk_components(in_node, out_node):
    record("Components Object")
    for k in in_node:
        if k in out_node:
            record("Components Object", k)
            if k == 'schemas': walk_dict(in_node[k], out_node[k], walk_schema)
            if k == 'responses': walk_dict(in_node[k], out_node[k], walk_response)
            if k == 'parameters': walk_dict(in_node[k], out_node[k], walk_parameter)
            if k == 'requestBodies': walk_dict(in_node[k], out_node[k], walk_request_body)
            if k == 'securitySchemes': walk_dict(in_node[k], out_node[k], walk_security_scheme)
            if k == 'links': walk_dict(in_node[k], out_node[k], walk_link)
            if k == 'callbacks': walk_dict(in_node[k], out_node[k], walk_callback)
            if k == 'headers': walk_dict(in_node[k], out_node[k], walk_header)

def walk_tag(in_node, out_node):
    record("Tag Object")
    for k in in_node:
        if k in out_node:
            record("Tag Object", k)
            if k == 'externalDocs': walk_external_docs(in_node[k], out_node[k])

def walk_openapi_doc(in_node, out_node):
    record("OpenAPI Object")
    for k in in_node:
        if k in out_node:
            record("OpenAPI Object", k)
            if k == 'info': walk_info(in_node[k], out_node[k])
            if k == 'servers': walk_list(in_node[k], out_node[k], walk_server)
            if k == 'paths': walk_paths(in_node[k], out_node[k])
            if k == 'components': walk_components(in_node[k], out_node[k])
            if k == 'security': record("Security Requirement Object")
            if k == 'tags': walk_list(in_node[k], out_node[k], walk_tag)
            if k == 'externalDocs': walk_external_docs(in_node[k], out_node[k])

def load_doc(path):
    with open(path, 'r') as f:
        if path.endswith('.yaml') or path.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return json.load(f)

def main():
    parser = argparse.ArgumentParser(description='Detect OpenAPI 3.2.0 conformance.')
    parser.add_argument('--input', required=True, help='Path to the original input OpenAPI spec')
    parser.add_argument('--output', required=True, help='Path to the roundtripped OpenAPI spec')
    parser.add_argument('--markdown', help='Path to the markdown conformance table to update')
    
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
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Example match: | **Info Object (`title`)** | `[ ]` , `[ ]` |
            m = re.match(r'^\|\s*\*\*(.*?)\*\*\s*\|(.*?)\|(.*?)\|', line)
            if m:
                feature_name = m.group(1).strip()
                if feature_name in supported_features:
                    # Update [ ] to [x] in the Presence column
                    # The presence column is group 2
                    presence_col = m.group(2)
                    new_presence = presence_col.replace('[ ]', '[x]')
                    lines[i] = line.replace(f"|{presence_col}|", f"|{new_presence}|")
                    
        md_path.write_text('\n'.join(lines))
        print(f"Successfully updated {md_path}")
    else:
        for f in sorted(list(supported_features)):
            print(f"- {f}")

if __name__ == '__main__':
    main()
