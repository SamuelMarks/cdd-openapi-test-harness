#!/usr/bin/env python3
"""Endpoint coverage verification tool (`verify_coverage.py`).

Parses an OpenAPI specification to determine all expected HTTP methods and paths
(including OAS 3.0 `trace` and OAS 3.2.0 `query` and `additionalOperations`).
Reads an HTTP access log to verify 100% of defined endpoints were successfully
exercised (HTTP status < 400) during integration tests.

Usage: python3 verify_coverage.py <spec_path> [base_path] < access.log
"""

import json
import re
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Pattern, Sequence, Set, Tuple
from urllib.parse import urlparse

import yaml

from harness.errors import CoverageValidationError, JSONDict, SpecificationError

HTTP_METHODS: Tuple[str, ...] = (
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "trace",
    "query",
)


@dataclass(frozen=True)
class EndpointSpec:
    """Structured representation of an expected OpenAPI endpoint.

    Attributes:
        method: Uppercase HTTP verb (e.g., `'GET'`, `'POST'`, `'QUERY'`).
        path_template: Full normalized path template (e.g., `'/v2/pet/{petId}'`).
        regex_pattern: Anchored regular expression string matching concrete request paths.
    """

    method: str
    path_template: str
    regex_pattern: str

    @property
    def compiled_regex(self) -> Pattern[str]:
        """Compile and return the regular expression pattern for this endpoint.

        Returns:
            Pattern[str]: Compiled regular expression matching concrete URL paths.
        """
        return re.compile(self.regex_pattern)


def _resolve_base_path(spec: JSONDict, explicit_base_path: str) -> str:
    """Determine the API base path from an explicit override or specification metadata.

    Args:
        spec: Parsed OpenAPI/Swagger specification dictionary.
        explicit_base_path: Explicit base path passed via CLI, or empty string.

    Returns:
        str: Normalized base path without trailing slash (e.g., '/v2' or '/api/v3').
    """
    if explicit_base_path:
        return explicit_base_path.rstrip("/")

    base_path_val = spec.get("basePath")
    if isinstance(base_path_val, str) and base_path_val:
        return base_path_val.rstrip("/")

    servers_val = spec.get("servers")
    if isinstance(servers_val, list) and len(servers_val) > 0:
        first_server = servers_val[0]
        if isinstance(first_server, dict):
            server_url = first_server.get("url")
            if isinstance(server_url, str) and server_url:
                parsed = urlparse(server_url)
                if parsed.path and parsed.path != "/":
                    return parsed.path.rstrip("/")
    return ""


def _build_endpoint_spec(method: str, base_path: str, raw_path: str) -> EndpointSpec:
    """Construct an `EndpointSpec` from an HTTP method, base path, and OpenAPI path template.

    Args:
        method: HTTP method name.
        base_path: Resolved base path prefix.
        raw_path: Raw path template from the OpenAPI specification.

    Returns:
        EndpointSpec: Structured endpoint specification with regex matcher.
    """
    clean_path = raw_path if raw_path.startswith("/") else "/" + raw_path
    full_path = f"{base_path}{clean_path}"
    regex_str = re.sub(r"\{[^}/]+\}", "[^/?#]+", full_path)
    regex_str = f"^{regex_str}(?:[?].*)?$"
    return EndpointSpec(
        method=method.upper(),
        path_template=full_path,
        regex_pattern=regex_str,
    )


def extract_endpoints_from_spec(
    spec_path: str,
    explicit_base_path: str = "",
) -> Set[EndpointSpec]:
    """Extract a set of `EndpointSpec` items from an OpenAPI/Swagger specification.

    Converts OpenAPI path templates like `/pet/{petId}` into regex patterns like
    `^/v2/pet/[^/?#]+(?:[?].*)?$`, including OAS 3.2.0 `query` and `additionalOperations`.

    Args:
        spec_path: Filesystem path to the JSON or YAML specification.
        explicit_base_path: Optional base path prefix override.

    Returns:
        Set[EndpointSpec]: Set of expected endpoint specifications.

    Raises:
        SpecificationError: If the file cannot be read or is not a valid mapping.
    """
    try:
        with open(spec_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f) if spec_path.endswith((".yaml", ".yml")) else json.load(f)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SpecificationError(spec_path, str(exc)) from exc

    if not isinstance(spec, dict):
        raise SpecificationError(spec_path, "Top-level specification must be a JSON/YAML object.")

    base_path = _resolve_base_path(spec, explicit_base_path)
    endpoints: Set[EndpointSpec] = set()
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return endpoints

    for raw_path, operations in paths.items():
        if not isinstance(raw_path, str) or not isinstance(operations, dict):
            continue
        for method in operations:
            if isinstance(method, str) and method.lower() in HTTP_METHODS:
                endpoints.add(_build_endpoint_spec(method, base_path, raw_path))
        additional_ops = operations.get("additionalOperations")
        if isinstance(additional_ops, dict):
            for custom_method in additional_ops:
                if isinstance(custom_method, str) and custom_method.strip():
                    endpoints.add(_build_endpoint_spec(custom_method, base_path, raw_path))

    return endpoints


def verify_endpoints_covered(
    expected_endpoints: Set[EndpointSpec],
    log_lines: Optional[Iterable[str]] = None,
) -> Set[EndpointSpec]:
    """Verify that all expected endpoints were exercised with HTTP status < 400.

    Args:
        expected_endpoints: Set of `EndpointSpec` entries to verify.
        log_lines: Optional iterable of log lines; defaults to `sys.stdin`.

    Returns:
        Set[EndpointSpec]: The set of hit endpoints when 100% coverage is achieved.

    Raises:
        CoverageValidationError: If one or more expected endpoints were not hit with status < 400.
    """
    log_pattern = re.compile(r'"([A-Z]+)\s+([^"\s]+)\s+HTTP/[0-9.]+"(?:\s+(\d{3}))?')
    hit_endpoints: Set[EndpointSpec] = set()
    compiled_map: List[Tuple[EndpointSpec, Pattern[str]]] = [(ep, ep.compiled_regex) for ep in expected_endpoints]

    source = log_lines if log_lines is not None else sys.stdin
    for line in source:
        match = log_pattern.search(line)
        if not match:
            continue
        req_method = match.group(1)
        req_url = match.group(2)
        status_str = match.group(3)
        status_code = int(status_str) if status_str is not None else 200
        if status_code >= 400:
            continue

        for ep, compiled_regex in compiled_map:
            if ep in hit_endpoints:
                continue
            if req_method == ep.method and compiled_regex.match(req_url):
                hit_endpoints.add(ep)

    unhit = expected_endpoints - hit_endpoints
    total = len(expected_endpoints)
    hit_count = len(hit_endpoints)

    print(f"Endpoint Coverage: {hit_count}/{total} ({(hit_count / total * 100) if total else 100:.1f}%)")

    if unhit:
        formatted_unhit = sorted(f"{ep.method:6s} {ep.path_template}" for ep in unhit)
        print("❌ Coverage Validation Failed! The following endpoints were NEVER hit during tests:")
        for item in formatted_unhit:
            print(f"  - {item}")
        raise CoverageValidationError(formatted_unhit)

    print("✅ 100% of specification endpoints were successfully exercised!")
    return hit_endpoints


def parse_logs_and_verify(
    expected_endpoints: Set[EndpointSpec],
    log_lines: Optional[Iterable[str]] = None,
) -> bool:
    """Read HTTP access logs and verify whether every expected endpoint was hit.

    Args:
        expected_endpoints: Set of `EndpointSpec` entries to verify.
        log_lines: Optional iterable of log lines; defaults to `sys.stdin`.

    Returns:
        bool: True if 100% of expected endpoints were hit, False otherwise.
    """
    try:
        verify_endpoints_covered(expected_endpoints, log_lines=log_lines)
        return True
    except CoverageValidationError:
        return False


def main(
    argv: Optional[Sequence[str]] = None,
    log_lines: Optional[Iterable[str]] = None,
) -> int:
    """CLI entrypoint for `verify_coverage.py`.

    Args:
        argv: Optional sequence of command-line arguments (excluding program name).
        log_lines: Optional iterable of log lines for testing; defaults to `sys.stdin`.

    Returns:
        int: Exit status code (0 on 100% coverage, 1 on error or incomplete coverage).
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    if len(args) < 1:
        print("Usage: verify_coverage.py <spec_path> [base_path]")
        return 1

    spec_path = args[0]
    base_path = args[1] if len(args) > 1 else ""

    try:
        expected_endpoints = extract_endpoints_from_spec(spec_path, base_path)
    except SpecificationError as exc:
        print(exc.message)
        return exc.code

    if not expected_endpoints:
        print("No valid endpoints found in specification.")
        return 1

    try:
        verify_endpoints_covered(expected_endpoints, log_lines=log_lines)
        return 0
    except CoverageValidationError as exc:
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
