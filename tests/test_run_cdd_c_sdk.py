"""Unit tests for `run_cdd_c_sdk.py`."""

import os
import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List, Optional

import pytest

import run_cdd_c_sdk
from harness.errors import CommandExecutionError


def test_run_c_sdk_suite_success_and_failure(tmp_path: Path) -> None:
    """Verify `run_c_sdk_suite` executes C tests, generates SDK, and checks `ctest` exit code."""
    c_dir = tmp_path / "cdd-c"
    c_dir.mkdir()
    client_dir = tmp_path / "cdd-c-client"
    client_dir.mkdir()
    (client_dir / "stale.txt").write_text("stale", encoding="utf-8")

    spec_yaml = tmp_path / "petstore.yaml"
    spec_yaml.write_text('{"openapi": "3.0.0", "info": {"title": "Petstore", "version": "1.0.0"}}', encoding="utf-8")

    calls: List[List[str]] = []

    def fake_run_ok(
        cmd: List[str],
        cwd: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Simulate successful command execution and re-create client_dir on SDK generation."""
        assert check in (True, False)
        assert cwd is None or os.path.isabs(cwd)
        calls.append(cmd)
        if "from_openapi" in cmd:
            client_dir.mkdir(exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run_ok):
        run_cdd_c_sdk.run_c_sdk_suite(
            c_dir=str(c_dir),
            client_dir=str(client_dir),
            spec_yaml=str(spec_yaml),
        )
    assert len(calls) == 6
    assert calls[0] == ["make", "test"]
    assert calls[1] == ["make", "build"]
    assert calls[-1] == ["ctest", "--output-on-failure", "--no-tests=ignore"]

    def fake_run_fail_ctest(
        cmd: List[str],
        cwd: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Simulate ctest failure."""
        assert check in (True, False)
        assert cwd is None or os.path.isabs(cwd)
        if "from_openapi" in cmd:
            client_dir.mkdir(exist_ok=True)
        if cmd[0] == "ctest":
            return subprocess.CompletedProcess(cmd, 2)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run_fail_ctest):
        with pytest.raises(CommandExecutionError) as exc_info:
            run_cdd_c_sdk.run_c_sdk_suite(
                c_dir=str(c_dir),
                client_dir=str(client_dir),
                spec_yaml=str(spec_yaml),
            )
        assert exc_info.value.code == 2

    def fake_run_pre_removed_tmp(
        cmd: List[str],
        cwd: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Remove the temporary JSON file during from_openapi to exercise cleanup branch."""
        assert check in (True, False)
        assert cwd is None or os.path.isabs(cwd)
        if "from_openapi" in cmd:
            tmp_file = cmd[cmd.index("-i") + 1]
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run_pre_removed_tmp):
        run_cdd_c_sdk.run_c_sdk_suite(
            c_dir=str(c_dir),
            client_dir=str(client_dir / "nonexistent_sub"),
            spec_yaml=str(spec_yaml),
        )


def test_main_success_and_error() -> None:
    """Verify `main` runs `run_c_sdk_suite` and exits with `exc.code` on failure."""
    with mock.patch("run_cdd_c_sdk.run_c_sdk_suite", side_effect=lambda: None):
        run_cdd_c_sdk.main()

    def raise_err() -> None:
        """Raise CommandExecutionError."""
        raise CommandExecutionError(["ctest"], 3)

    with (
        mock.patch("run_cdd_c_sdk.run_c_sdk_suite", side_effect=raise_err),
        mock.patch("sys.exit") as mock_exit,
    ):
        run_cdd_c_sdk.main()
        mock_exit.assert_called_once_with(3)
