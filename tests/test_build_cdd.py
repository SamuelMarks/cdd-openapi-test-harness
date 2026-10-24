"""Unit tests for `build_cdd.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

import build_cdd
from harness.errors import DirectoryMissingError


def test_build_cdd_ts_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `build_cdd_ts` changes directory, runs `npm i` and `npm run build`, and restores cwd."""
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
    build_cdd.build_cdd_ts(str(target))
    assert Path.cwd() == orig_cwd
    assert calls == [["npm", "i"], ["npm", "run", "build"]]


def test_build_cdd_ts_missing_dir(tmp_path: Path) -> None:
    """Verify `build_cdd_ts` raises `DirectoryMissingError` when directory does not exist."""
    missing = tmp_path / "does-not-exist"
    with pytest.raises(DirectoryMissingError):
        build_cdd.build_cdd_ts(str(missing))


def test_build_cdd_main_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `build_cdd.main` invokes `build_cdd_ts('cdd-ts')` cleanly."""
    called: List[str] = []
    monkeypatch.setattr(build_cdd, "build_cdd_ts", lambda d: called.append(d))
    build_cdd.main()
    assert called == ["cdd-ts"]


def test_build_cdd_main_missing_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `build_cdd.main` exits with code 1 when `DirectoryMissingError` is raised."""

    def raise_missing(d: str) -> None:
        """Raise DirectoryMissingError."""
        raise DirectoryMissingError(d)

    monkeypatch.setattr(build_cdd, "build_cdd_ts", raise_missing)
    with mock.patch("sys.exit") as mock_exit:
        build_cdd.main()
        mock_exit.assert_called_once_with(1)
