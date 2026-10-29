"""Unit tests for `harness/errors.py` and `harness/registry.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

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
    ToolchainSpec,
    __version__,
    build_typescript_toolchain,
    get_toolchain,
    get_toolchains,
    run_c_sdk_test_suite,
    run_typescript_toolchain_tests,
)


def test_harness_error_hierarchy() -> None:
    """Verify all custom exception classes in `harness.errors` initialize attributes and codes."""
    assert __version__ == "0.0.4"
    base_err = HarnessError("base failure", code=2)
    assert base_err.message == "base failure"
    assert base_err.code == 2
    assert str(base_err) == "base failure"

    cmd_err = CommandExecutionError(["npm", "test"], 127, stdout="out", stderr="err")
    assert cmd_err.cmd == ["npm", "test"]
    assert cmd_err.returncode == 127
    assert cmd_err.code == 127
    assert cmd_err.stdout == "out"
    assert cmd_err.stderr == "err"
    assert "npm test" in cmd_err.message

    cmd_err_zero = CommandExecutionError(["echo"], 0)
    assert cmd_err_zero.code == 1

    dir_err = DirectoryMissingError("missing-dir")
    assert dir_err.path == "missing-dir"
    assert dir_err.code == 1
    assert "missing-dir" in dir_err.message

    spec_err = SpecificationError("petstore.json", "invalid json")
    assert spec_err.spec_path == "petstore.json"
    assert spec_err.reason == "invalid json"
    assert spec_err.code == 1

    cov_err = CoverageValidationError(["GET /pet", "POST /pet"])
    assert cov_err.unhit_endpoints == ["GET /pet", "POST /pet"]
    assert "GET /pet, POST /pet" in cov_err.message

    audit_err = AuditFailureError("cdd-ts", "status_500", "passed on 500")
    assert audit_err.toolchain == "cdd-ts"
    assert audit_err.phase == "status_500"
    assert audit_err.details == "passed on 500"
    assert "[cdd-ts]" in audit_err.message

    conf_err = ConformanceError("matrix missing")
    assert conf_err.message == "matrix missing"
    assert conf_err.code == 1

    dash_err = DashboardError("readme missing")
    assert dash_err.message == "readme missing"
    assert dash_err.code == 1


def test_toolchain_registry() -> None:
    """Verify `TOOLCHAINS`, `get_toolchains`, and `get_toolchain` lookup behavior."""
    all_specs = get_toolchains()
    assert len(all_specs) == 13
    assert len(TOOLCHAINS) == 13
    assert all(isinstance(spec, ToolchainSpec) for spec in all_specs)
    assert all(bool(spec.client_output_dir) for spec in all_specs)
    assert all(len(spec.roundtrip_from_cmd) > 0 for spec in all_specs)
    assert all(len(spec.roundtrip_to_cmd) > 0 for spec in all_specs)

    rust_spec = get_toolchain("cdd-rust")
    assert rust_spec.language == "Rust"
    assert rust_spec.is_client_role is True
    assert rust_spec.is_server_role is True
    assert rust_spec.client_output_dir == "cdd-rust-client"

    swift_spec = get_toolchain("cdd-swift")
    assert swift_spec.roundtrip_input_subpath == "Sources/GeneratedSDK/models.swift"

    with pytest.raises(KeyError):
        get_toolchain("cdd-nonexistent")


def test_registry_runner_helpers(tmp_path: Path) -> None:
    """Verify `build_typescript_toolchain`, `run_typescript_toolchain_tests`, and `run_c_sdk_test_suite`."""
    missing_dir = str(tmp_path / "missing")
    with pytest.raises(DirectoryMissingError):
        build_typescript_toolchain(missing_dir)
    with pytest.raises(DirectoryMissingError):
        run_typescript_toolchain_tests(missing_dir)
    with pytest.raises(DirectoryMissingError):
        run_c_sdk_test_suite(c_dir=missing_dir)

    ts_dir = tmp_path / "cdd-ts"
    ts_dir.mkdir()
    recorded_cmds: List[List[str]] = []

    def fake_run_ok(
        cmd: List[str],
        cwd: str = "",
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Record command invocations."""
        assert isinstance(cwd, str)
        assert check in (True, False)
        recorded_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run_ok):
        build_typescript_toolchain(str(ts_dir))
        run_typescript_toolchain_tests(str(ts_dir))

    assert recorded_cmds == [
        ["npm", "i"],
        ["npm", "run", "build"],
        ["npm", "run", "test", "--run"],
    ]

    c_dir = tmp_path / "cdd-c"
    c_dir.mkdir()
    client_dir = tmp_path / "cdd-c-client"
    client_dir.mkdir()
    spec_yaml = tmp_path / "petstore.yaml"
    spec_yaml.write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    recorded_cmds.clear()
    with mock.patch("subprocess.run", side_effect=fake_run_ok):
        run_c_sdk_test_suite(str(c_dir), str(client_dir), str(spec_yaml))
    assert recorded_cmds[0] == ["make", "test"]
    assert recorded_cmds[1] == ["make", "build"]
    assert recorded_cmds[-1] == ["ctest", "--output-on-failure", "--no-tests=ignore"]
