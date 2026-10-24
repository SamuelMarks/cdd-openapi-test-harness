"""Unit tests for `run_cdd_c_sdk.py`."""

import os
import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

import run_cdd_c_sdk
from harness.errors import CommandExecutionError


def test_run_c_sdk_suite_success_with_existing_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_c_sdk_suite` cleans existing client_dir, converts spec, builds, and runs ctest."""
    c_dir = tmp_path / "cdd-c"
    c_dir.mkdir()
    client_dir = tmp_path / "cdd-c-client"
    client_dir.mkdir()
    (client_dir / "stale.txt").write_text("stale", encoding="utf-8")
    spec_yaml = tmp_path / "petstore.yaml"
    spec_yaml.write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    commands: List[List[str]] = []

    def fake_run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        """Simulate subprocess execution and create client_dir when from_openapi is called."""
        commands.append(cmd)
        if "from_openapi" in cmd:
            out_idx = cmd.index("-o") + 1
            os.makedirs(cmd[out_idx], exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_cdd_c_sdk.run_c_sdk_suite(str(c_dir), str(client_dir), str(spec_yaml))
    assert not (client_dir / "stale.txt").exists()
    assert any("ctest" in c[0] for c in commands)


def test_run_c_sdk_suite_failure_without_existing_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_c_sdk_suite` raises `CommandExecutionError` when `ctest` returns non-zero."""
    c_dir = tmp_path / "cdd-c"
    c_dir.mkdir()
    client_dir = tmp_path / "cdd-c-client"
    spec_yaml = tmp_path / "petstore.yaml"
    spec_yaml.write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    def fake_run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        """Simulate ctest failure and remove temp_spec_path beforehand to cover both branches."""
        if "from_openapi" in cmd:
            in_idx = cmd.index("-i") + 1
            if os.path.exists(cmd[in_idx]):
                os.remove(cmd[in_idx])
            out_idx = cmd.index("-o") + 1
            os.makedirs(cmd[out_idx], exist_ok=True)
        if cmd[0] == "ctest":
            return subprocess.CompletedProcess(cmd, 2)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandExecutionError) as exc_info:
        run_cdd_c_sdk.run_c_sdk_suite(str(c_dir), str(client_dir), str(spec_yaml))
    assert exc_info.value.code == 2


def test_run_cdd_c_sdk_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_cdd_c_sdk.main` handles both normal completion and `CommandExecutionError`."""
    monkeypatch.setattr(run_cdd_c_sdk, "run_c_sdk_suite", lambda: None)
    run_cdd_c_sdk.main()

    def raise_err() -> None:
        """Raise CommandExecutionError."""
        raise CommandExecutionError(["ctest"], 3)

    monkeypatch.setattr(run_cdd_c_sdk, "run_c_sdk_suite", raise_err)
    with mock.patch("sys.exit") as mock_exit:
        run_cdd_c_sdk.main()
        mock_exit.assert_called_once_with(3)
