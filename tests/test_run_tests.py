"""Unit tests for `run_tests.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

import run_tests
from harness.errors import DirectoryMissingError


def test_run_cdd_ts_tests_missing_dir(tmp_path: Path) -> None:
    """Verify `run_cdd_ts_tests` raises `DirectoryMissingError` when directory is absent."""
    missing = tmp_path / "missing-cdd-ts"
    with pytest.raises(DirectoryMissingError):
        run_tests.run_cdd_ts_tests(str(missing))


def test_run_cdd_ts_tests_success(tmp_path: Path) -> None:
    """Verify `run_cdd_ts_tests` runs `npm run test --run` in the target directory."""
    target = tmp_path / "cdd-ts"
    target.mkdir()

    calls: List[List[str]] = []

    def fake_run(cmd: List[str], cwd: str = "", check: bool = False) -> subprocess.CompletedProcess[str]:
        """Record subprocess calls."""
        assert cwd == str(target)
        assert check is True
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        run_tests.run_cdd_ts_tests(str(target))

    assert calls == [["npm", "run", "test", "--run"]]


def test_main_success_and_error() -> None:
    """Verify `main` executes `run_cdd_ts_tests` and exits with code 1 on `DirectoryMissingError`."""
    called: List[str] = []

    with mock.patch("run_tests.run_cdd_ts_tests", side_effect=lambda d: called.append(d)):
        run_tests.main()
    assert called == ["cdd-ts"]

    def raise_missing(d: str) -> None:
        """Raise DirectoryMissingError."""
        raise DirectoryMissingError(d)

    with (
        mock.patch("run_tests.run_cdd_ts_tests", side_effect=raise_missing),
        mock.patch("sys.exit") as mock_exit,
    ):
        run_tests.main()
        mock_exit.assert_called_once_with(1)
