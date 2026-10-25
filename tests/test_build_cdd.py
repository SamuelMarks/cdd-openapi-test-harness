"""Unit tests for `build_cdd.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

import build_cdd
from harness.errors import DirectoryMissingError


def test_build_cdd_ts_missing_dir(tmp_path: Path) -> None:
    """Verify `build_cdd_ts` raises `DirectoryMissingError` when directory does not exist."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(DirectoryMissingError):
        build_cdd.build_cdd_ts(str(missing))


def test_build_cdd_ts_success(tmp_path: Path) -> None:
    """Verify `build_cdd_ts` runs `npm i` and `npm run build` in the target directory."""
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
        build_cdd.build_cdd_ts(str(target))

    assert calls == [["npm", "i"], ["npm", "run", "build"]]


def test_main_success_and_error() -> None:
    """Verify `main` handles both success and `DirectoryMissingError` exit code."""
    called: List[str] = []

    with mock.patch("build_cdd.build_cdd_ts", side_effect=lambda d: called.append(d)):
        build_cdd.main()
    assert called == ["cdd-ts"]

    def raise_missing(d: str) -> None:
        """Raise DirectoryMissingError."""
        raise DirectoryMissingError(d)

    with (
        mock.patch("build_cdd.build_cdd_ts", side_effect=raise_missing),
        mock.patch("sys.exit") as mock_exit,
    ):
        build_cdd.main()
        mock_exit.assert_called_once_with(1)
