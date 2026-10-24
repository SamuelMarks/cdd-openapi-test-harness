"""Unit tests for `verify_coverage.py`."""

import json
from pathlib import Path

import pytest

import verify_coverage
from harness.errors import SpecificationError


def test_resolve_base_path_variants() -> None:
    """Verify `_resolve_base_path` handles explicit, `basePath`, `servers`, and empty cases."""
    assert verify_coverage._resolve_base_path({}, "/v2/") == "/v2"
    assert verify_coverage._resolve_base_path({"basePath": "/v2/"}, "") == "/v2"
    assert (
        verify_coverage._resolve_base_path({"servers": [{"url": "https://petstore3.swagger.io/api/v3/"}]}, "")
        == "/api/v3"
    )
    assert verify_coverage._resolve_base_path({"servers": [{"url": "https://example.com/"}]}, "") == ""
    assert verify_coverage._resolve_base_path({"servers": ["not-a-dict"]}, "") == ""
    assert verify_coverage._resolve_base_path({"servers": [{"url": ""}]}, "") == ""
    assert verify_coverage._resolve_base_path({}, "") == ""


def test_extract_endpoints_from_spec(tmp_path: Path) -> None:
    """Verify `extract_endpoints_from_spec` parses valid specs and rejects invalid ones."""
    missing = tmp_path / "missing.json"
    with pytest.raises(SpecificationError):
        verify_coverage.extract_endpoints_from_spec(str(missing))

    non_dict = tmp_path / "list.json"
    non_dict.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(SpecificationError):
        verify_coverage.extract_endpoints_from_spec(str(non_dict))

    bad_paths = tmp_path / "bad_paths.json"
    bad_paths.write_text('{"paths": []}', encoding="utf-8")
    assert verify_coverage.extract_endpoints_from_spec(str(bad_paths)) == set()

    spec_data = {
        "openapi": "3.0.0",
        "paths": {
            "/pet/{petId}": {
                "get": {"responses": {"200": {"description": "ok"}}},
                "delete": {"responses": {"200": {"description": "ok"}}},
                "parameters": [{"name": "petId", "in": "path"}],
            },
            "/invalid": "not-a-dict",
        },
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec_data), encoding="utf-8")

    endpoints = verify_coverage.extract_endpoints_from_spec(str(spec_file), "/v2")
    assert len(endpoints) == 2
    methods = {m for m, _ in endpoints}
    assert methods == {"GET", "DELETE"}


def test_parse_logs_and_verify_and_main(tmp_path: Path) -> None:
    """Verify `parse_logs_and_verify` and `main` cover 100% hit, partial hit, and error branches."""
    assert verify_coverage.main([]) == 1

    missing_spec = tmp_path / "nope.json"
    assert verify_coverage.main([str(missing_spec)]) == 1

    empty_spec = tmp_path / "empty.json"
    empty_spec.write_text('{"paths": {}}', encoding="utf-8")
    assert verify_coverage.main([str(empty_spec)]) == 1

    spec_file = tmp_path / "pet.json"
    spec_file.write_text(
        json.dumps(
            {
                "paths": {
                    "/pet/{petId}": {"get": {}, "delete": {}},
                }
            }
        ),
        encoding="utf-8",
    )

    hit_logs = [
        "some random noise line",
        '127.0.0.1 - - [23/Oct/2026:12:00:00 +0000] "GET /v2/pet/123 HTTP/1.1" 200 42',
        '127.0.0.1 - - [23/Oct/2026:12:00:01 +0000] "POST /v2/other HTTP/1.1" 200 42',
        '127.0.0.1 - - [23/Oct/2026:12:00:02 +0000] "DELETE /v2/pet/123?force=1 HTTP/1.1" 200 0',
        '127.0.0.1 - - [23/Oct/2026:12:00:03 +0000] "GET /v2/pet/999 HTTP/1.1" 200 42',
    ]
    assert verify_coverage.main([str(spec_file), "/v2"], log_lines=hit_logs) == 0

    partial_logs = [
        '127.0.0.1 - - [23/Oct/2026:12:00:00 +0000] "GET /v2/pet/123 HTTP/1.1" 200 42',
    ]
    assert verify_coverage.main([str(spec_file), "/v2"], log_lines=partial_logs) == 1
