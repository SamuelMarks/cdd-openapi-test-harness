"""Unit tests for `harness/errors.py` and `harness/registry.py`."""

import pytest

from harness import (
    TOOLCHAINS,
    AuditFailureError,
    CommandExecutionError,
    ConformanceError,
    CoverageValidationError,
    DashboardError,
    DirectoryMissingError,
    HarnessError,
    SpecificationError,
    get_toolchain,
    get_toolchains,
)


def test_error_hierarchy() -> None:
    """Verify all custom error classes in `harness.errors` initialize attributes and codes properly."""
    base_err = HarnessError("base error", code=2)
    assert base_err.message == "base error"
    assert base_err.code == 2

    cmd_err = CommandExecutionError(["npm", "test"], returncode=127, stdout="out", stderr="err")
    assert cmd_err.code == 127
    assert cmd_err.cmd == ["npm", "test"]
    assert cmd_err.stdout == "out"
    assert cmd_err.stderr == "err"

    cmd_err_zero = CommandExecutionError(["npm", "test"], returncode=0)
    assert cmd_err_zero.code == 1

    dir_err = DirectoryMissingError("missing-dir")
    assert dir_err.path == "missing-dir"
    assert "missing-dir" in dir_err.message

    spec_err = SpecificationError("petstore.json", "bad json")
    assert spec_err.spec_path == "petstore.json"
    assert spec_err.reason == "bad json"

    cov_err = CoverageValidationError(["GET /pet", "POST /pet"])
    assert cov_err.unhit_endpoints == ["GET /pet", "POST /pet"]
    assert "GET /pet" in cov_err.message

    audit_err = AuditFailureError("cdd-ts", "status_500", "passed on 500")
    assert audit_err.toolchain == "cdd-ts"
    assert audit_err.phase == "status_500"
    assert audit_err.details == "passed on 500"

    conf_err = ConformanceError("conformance failed")
    assert conf_err.code == 1

    dash_err = DashboardError("dashboard failed")
    assert dash_err.code == 1


def test_registry_lookup() -> None:
    """Verify `get_toolchains` and `get_toolchain` return all 13 registered specs."""
    all_specs = get_toolchains()
    assert len(all_specs) == 13
    assert len(TOOLCHAINS) == 13

    rust_spec = get_toolchain("cdd-rust")
    assert rust_spec.language == "Rust"
    assert rust_spec.is_client_role is True
    assert rust_spec.is_server_role is True

    with pytest.raises(KeyError):
        get_toolchain("cdd-nonexistent")
