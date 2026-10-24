"""Unit tests for `run_tests.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

import run_tests
from harness.errors import DirectoryMissingError


def test_run_cdd_ts_tests_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_cdd_ts_tests` changes directory, runs `npm run test --run`, and restores cwd."""
    target = tmp_path / "cdd-ts"
    target.mkdir()
    calls: List[List[str]] = []

    def fake_run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        """Record subprocess calls."""
        assert check is True
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    orig_cwd = Path.cwd()
    run_tests.run_cdd_ts_tests(str(target))
    assert Path.cwd() == orig_cwd
    assert calls == [["npm", "run", "test", "--run"]]


def test_run_cdd_ts_tests_missing_dir(tmp_path: Path) -> None:
    """Verify `run_cdd_ts_tests` raises `DirectoryMissingError` when directory is absent."""
    with pytest.raises(DirectoryMissingError):
        run_tests.run_cdd_ts_tests(str(tmp_path / "missing"))


def test_run_tests_main_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_tests.main` invokes `run_cdd_ts_tests('cdd-ts')`."""
    called: List[str] = []
    monkeypatch.setattr(run_tests, "run_cdd_ts_tests", lambda d: called.append(d))
    run_tests.main()
    assert called == ["cdd-ts"]


def test_run_tests_main_missing_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_tests.main` exits with code 1 when `DirectoryMissingError` is raised."""

    def raise_missing(d: str) -> None:
        """Raise DirectoryMissingError."""
        raise DirectoryMissingError(d)

    monkeypatch.setattr(run_tests, "run_cdd_ts_tests", raise_missing)
    with mock.patch("sys.exit") as mock_exit:
        run_tests.main()
        mock_exit.assert_called_once_with(1)
