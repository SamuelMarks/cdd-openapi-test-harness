#!/usr/bin/env python3
"""Endpoint coverage verification tool (`verify_coverage.py`).

Parses an OpenAPI specification to determine all expected HTTP methods and paths.
Then reads an Nginx/Tomcat/Docker access log via stdin to verify that every
expected endpoint was successfully hit during a test run.

Usage:
  docker logs petstore_server 2>&1 | python3 verify_coverage.py path/to/openapi.json /v2
"""

import json
import re
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from harness.errors import SpecificationError

HTTP_METHODS: Tuple[str, ...] = (
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
)


def _resolve_base_path(spec: Dict[str, object], explicit_base_path: str) -> str:
    """Resolve the API base path from explicit CLI input or OpenAPI servers/basePath.

    Args:
        spec: Parsed OpenAPI/Swagger specification dictionary.
        explicit_base_path: Base path explicitly passed via CLI, if any.

    Returns:
        str: Normalized base path prefix (e.g., '/v2' or '').
    """
    if explicit_base_path:
        return explicit_base_path.rstrip("/")

    base_path_val = spec.get("basePath")
    if isinstance(base_path_val, str) and base_path_val:
        return base_path_val.rstrip("/")

    servers_val = spec.get("servers")
    if isinstance(servers_val, list) and servers_val:
        first_server = servers_val[0]
        if isinstance(first_server, dict):
            url_val = first_server.get("url")
            if isinstance(url_val, str) and url_val:
                parsed = urlparse(url_val)
                if parsed.path and parsed.path != "/":
                    return parsed.path.rstrip("/")
    return ""


def _path_to_regex(path: str, base_path: str) -> str:
    """Convert an OpenAPI path template into a safe, anchored regular expression.

    Escapes literal regex metacharacters while replacing `{param}` segments
    with `[^/]+`.

    Args:
        path: OpenAPI path template (e.g., '/pet/{petId}').
        base_path: Normalized base path prefix (e.g., '/v2').

    Returns:
        str: Anchored regular expression string matching requests to the endpoint.
    """
    parts = re.split(r"(\{[^}]+\})", path)
    escaped_parts: List[str] = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            escaped_parts.append("[^/]+")
        else:
            escaped_parts.append(re.escape(part))
    regex_path = "".join(escaped_parts)
    escaped_base = re.escape(base_path)
    bs = chr(92)
    return f"^{escaped_base}{regex_path}/?(?:{bs}?.*)?$"


def extract_endpoints_from_spec(spec_path: str, base_path: str = "") -> Set[Tuple[str, str]]:
    """Read an OpenAPI JSON file and return a set of `(METHOD, regex_pattern)` tuples.

    Args:
        spec_path: File path to the OpenAPI JSON specification.
        base_path: Optional base path prefix (e.g., '/v2') to prepend to all routes.

    Returns:
        Set[Tuple[str, str]]: Set of `(uppercase_method, regex_pattern)` pairs.

    Raises:
        SpecificationError: If the file cannot be read or contains invalid JSON.
    """
    try:
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as exc:
        raise SpecificationError(spec_path, str(exc)) from exc

    if not isinstance(spec, dict):
        raise SpecificationError(spec_path, "Root document must be a JSON object")

    resolved_base = _resolve_base_path(spec, base_path)
    endpoints: Set[Tuple[str, str]] = set()
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return endpoints

    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            continue
        full_regex = _path_to_regex(path, resolved_base)
        for method in operations:
            if not isinstance(method, str) or method.lower() not in HTTP_METHODS:
                continue
            endpoints.add((method.upper(), full_regex))

    return endpoints


def parse_logs_and_verify(
    endpoints: Set[Tuple[str, str]],
    log_lines: Optional[Iterable[str]] = None,
) -> bool:
    """Read web server access logs and verify that every expected endpoint was hit.

    Args:
        endpoints: Set of `(METHOD, regex_pattern)` tuples extracted from the spec.
        log_lines: Iterable of log lines to inspect. Defaults to `sys.stdin`.

    Returns:
        bool: True if all endpoints were hit at least once, False otherwise.
    """
    lines_source: Iterable[str] = sys.stdin if log_lines is None else log_lines
    unhit_endpoints: Dict[Tuple[str, str], str] = {ep: ep[1] for ep in endpoints}

    log_pattern = re.compile(r'(?:"|^)([A-Z]+)\s+([^"\s]+)\s*(?:HTTP/[0-9.]+)?(?!")')

    for line in lines_source:
        match = log_pattern.search(line)
        if not match:
            continue

        log_method = match.group(1).upper()
        log_path = match.group(2)

        hit_keys: List[Tuple[str, str]] = []
        for ep_key, regex_str in unhit_endpoints.items():
            ep_method = ep_key[0]
            if log_method == ep_method and re.match(regex_str, log_path):
                hit_keys.append(ep_key)

        for k in hit_keys:
            del unhit_endpoints[k]

        if not unhit_endpoints:
            break

    if unhit_endpoints:
        print("Coverage Validation Failed. The following endpoints were not tested:")
        bs = chr(92)
        for method, regex in sorted(unhit_endpoints.keys()):
            clean_path = (
                regex.replace("^", "")
                .replace("$", "")
                .replace(f"/?(?:{bs}?.*)?", "")
                .replace("[^/]+", "{param}")
                .replace(bs, "")
            )
            print(f"  - {method} {clean_path}")
        return False

    print("Coverage Validation Passed: 100% of endpoints were tested.")
    return True


def main(
    argv: Optional[Sequence[str]] = None,
    log_lines: Optional[Iterable[str]] = None,
) -> int:
    """CLI entrypoint for `verify_coverage.py`.

    Args:
        argv: Command-line arguments (excluding script name). Defaults to `sys.argv[1:]`.
        log_lines: Optional iterable of access log lines. Defaults to `sys.stdin`.

    Returns:
        int: Exit status code (0 on 100% coverage, 1 on error or missing coverage).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        print("Usage: python3 verify_coverage.py <openapi.json> [base_path]")
        return 1

    spec_file = args[0]
    base_route = args[1] if len(args) > 1 else ""

    try:
        expected_endpoints = extract_endpoints_from_spec(spec_file, base_route)
    except SpecificationError as exc:
        print(exc.message)
        return exc.code

    if not expected_endpoints:
        print("No valid endpoints found in specification.")
        return 1

    success = parse_logs_and_verify(expected_endpoints, log_lines=log_lines)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
