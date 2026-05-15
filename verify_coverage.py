#!/usr/bin/env python3
"""
verify_coverage.py

Parses an OpenAPI specification to determine all expected HTTP methods and paths.
Then reads an Nginx/Tomcat/Docker access log via stdin to verify that every 
expected endpoint was successfully hit during a test run.

Usage:
  docker logs petstore_server 2>&1 | python3 verify_coverage.py path/to/openapi.json /v2
"""

import sys
import json
import re
from typing import Dict, Set, List, Tuple

def extract_endpoints_from_spec(spec_path: str, base_path: str = "") -> Set[Tuple[str, str]]:
    """
    Reads an OpenAPI JSON file and returns a set of (METHOD, regex_pattern) tuples.
    
    Args:
        spec_path (str): The file path to the OpenAPI JSON specification.
        base_path (str): An optional base path prefix (e.g., '/v2') to prepend to all routes.
        
    Returns:
        Set[Tuple[str, str]]: A set where each item is a tuple containing the uppercase
                              HTTP method and a compiled regex string representing the path.
    """
    try:
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
    except Exception as e:
        print(f"Error reading specification {spec_path}: {e}")
        sys.exit(1)
        
    endpoints: Set[Tuple[str, str]] = set()
    paths = spec.get('paths', {})
    
    for path, operations in paths.items():
        # Convert OpenAPI path parameters /{petId}/ to Regex /[^/]+/
        # Example: /pet/{petId} -> /pet/[^/]+
        regex_path = re.sub(r'\{[^}]+\}', r'[^/]+', path)
        
        # Ensure regex strictly matches the string from start to finish
        # Allow trailing slashes and optional query parameters
        full_regex = f"^{base_path}{regex_path}/?(?:\\?.*)?$"
        
        for method in operations.keys():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                continue
            endpoints.add((method.upper(), full_regex))
            
    return endpoints

def parse_logs_and_verify(endpoints: Set[Tuple[str, str]]) -> bool:
    """
    Reads web server access logs from standard input and marks endpoints as hit.
    
    Args:
        endpoints (Set[Tuple[str, str]]): The expected endpoints extracted from the spec.
        
    Returns:
        bool: True if all endpoints were hit, False otherwise.
    """
    unhit_endpoints: Dict[Tuple[str, str], str] = {ep: ep[1] for ep in endpoints}
    
    # Common log format regex: Extracts Method and Path from standard web logs
    # E.g.: 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /v2/pet/1 HTTP/1.0" 200 2326
    # Or simple docker output logs: "GET /v2/pet/1"
    log_pattern = re.compile(r'"([A-Z]+)\s+([^"\s]+)\s*(?:HTTP/[0-9.]+)?(?!")')

    for line in sys.stdin:
        match = log_pattern.search(line)
        if not match:
            continue
            
        log_method = match.group(1).upper()
        log_path = match.group(2)
        
        # Check if this log entry fulfills any of our unhit endpoints
        hit_keys: List[Tuple[str, str]] = []
        for ep_key, regex_str in unhit_endpoints.items():
            ep_method = ep_key[0]
            if log_method == ep_method and re.match(regex_str, log_path):
                hit_keys.append(ep_key)
                
        # Remove hit endpoints from the unhit dictionary
        for k in hit_keys:
            del unhit_endpoints[k]
            
        if not unhit_endpoints:
            # We've hit everything! No need to parse the rest of the logs.
            break

    if unhit_endpoints:
        print("Coverage Validation Failed. The following endpoints were not tested:")
        for method, regex in unhit_endpoints.keys():
            # Strip the ^ and $ from the regex for cleaner display
            clean_path = regex.replace('^', '').replace('$','').replace('/?(?:\\?.*)?', '').replace('[^/]+', '{param}')
            print(f"  - {method} {clean_path}")
        return False
        
    print("Coverage Validation Passed: 100% of endpoints were tested.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 verify_coverage.py <openapi.json> [base_path]")
        sys.exit(1)
        
    spec_file = sys.argv[1]
    base_route = sys.argv[2] if len(sys.argv) > 2 else ""
    
    expected_endpoints = extract_endpoints_from_spec(spec_file, base_route)
    if not expected_endpoints:
        print("No valid endpoints found in specification.")
        sys.exit(1)
        
    success = parse_logs_and_verify(expected_endpoints)
    sys.exit(0 if success else 1)
