"""Unit tests for `scripts/check_all_conformance.py` and `scripts/check_conformance_project.py`."""

import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List

import pytest

from scripts import check_all_conformance, check_conformance_project


def test_check_all_conformance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `check_all_conformance.run_check` and `main` across missing/existing directories."""
    assert check_all_conformance.main(root_dir=tmp_path) == 1

    (tmp_path / "OAI-OpenAPI-Specification").mkdir()
    (tmp_path / "cdd-c").mkdir()
    (tmp_path / "cdd-java").mkdir()

    calls: List[List[str]] = []

    def fake_run(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Record subprocess calls."""
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert check_all_conformance.run_check("cdd-c", ["make"], ["./bin/cdd-c"], root_dir=tmp_path) is True
    assert check_all_conformance.run_check("cdd-java", [], ["./gradlew"], root_dir=tmp_path) is True
    assert check_all_conformance.run_check("cdd-missing", ["make"], ["./bin"], root_dir=tmp_path) is False
    assert check_all_conformance.run_check("cdd-missing", [], ["./bin"]) is False

    assert check_all_conformance.main(root_dir=tmp_path) == 0


def test_check_conformance_project_all_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `check_conformance_project` covers invalid YAML, CLI fallback, snapshot, Swift, and cleanup."""
    assert check_conformance_project.main([]) == 1

    examples_dir = tmp_path / "OAI-OpenAPI-Specification" / "examples" / "v3.0"
    examples_dir.mkdir(parents=True)
    (examples_dir / "good.yaml").write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    (examples_dir / "bad.yaml").write_text("::: [unclosed", encoding="utf-8")
    (tmp_path / "petstore_oas3.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    proj_dir = tmp_path / "cdd-swift"
    proj_dir.mkdir()
    md_file = tmp_path / "client-sdk.md"
    md_file.write_text("# Conformance", encoding="utf-8")

    scenario = ["snapshot"]

    def fake_run(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Simulate CLI invocations across snapshot, swift, fallback, and failure scenarios."""
        cmd_str = " ".join(cmd)
        if "detect_conformance.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0)

        if scenario[0] == "fail_both_from":
            return subprocess.CompletedProcess(cmd, 1)

        if scenario[0] == "fallback_from_and_fail_to":
            if "to_sdk" in cmd_str:
                return subprocess.CompletedProcess(cmd, 1)
            if "to_openapi" in cmd_str:
                return subprocess.CompletedProcess(cmd, 1)
            return subprocess.CompletedProcess(cmd, 0)

        if scenario[0] == "snapshot":
            for idx, arg in enumerate(cmd):
                if arg == "-o" and idx + 1 < len(cmd):
                    out_dir = Path(cmd[idx + 1])
                    if out_dir.is_dir():
                        (out_dir / "openapi.snapshot.json").write_text('{"openapi":"3.2.0"}', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        if scenario[0] == "swift_to_openapi":
            for arg in cmd:
                if "cdd_conf_" in arg:
                    tokens = [t for t in arg.split() if "cdd_conf_" in t]
                    target_dir = Path(tokens[-1] if tokens else arg)
                    if target_dir.is_dir():
                        sdk_dir = target_dir / "Sources" / "GeneratedSDK"
                        sdk_dir.mkdir(parents=True, exist_ok=True)
                        if not arg.startswith("--args="):
                            (sdk_dir / "models.swift").write_text("// swift", encoding="utf-8")
                if arg.startswith("--args=to_openapi"):
                    out_f = arg.split("-o ")[-1]
                    Path(out_f).write_text('{"openapi":"3.2.0"}', encoding="utf-8")
                elif arg.endswith(".json") and "to_openapi" in cmd_str:
                    Path(arg).write_text('{"openapi":"3.2.0"}', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 0

    scenario[0] = "swift_to_openapi"
    assert (
        check_conformance_project.main([str(proj_dir), str(md_file), "./gradlew", "run", "--args="], root_dir=tmp_path)
        == 0
    )
    assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 0

    scenario[0] = "fail_both_from"
    assert (
        check_conformance_project.main([str(proj_dir), str(md_file), "./gradlew", "run", "--args="], root_dir=tmp_path)
        == 0
    )

    scenario[0] = "fallback_from_and_fail_to"
    assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 0

    with (
        mock.patch("yaml.safe_load", side_effect=RuntimeError("yaml error")),
        mock.patch("os.path.exists", return_value=False),
    ):
        check_conformance_project.check_project(str(proj_dir), str(md_file), ["./bin/cdd-swift"], root_dir=tmp_path)

    def fake_run_unlinks(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Remove temp files during run to cover false branches of os.path.exists cleanup."""
        for arg in cmd:
            if arg.endswith(".json") and os.path.exists(arg):
                os.remove(arg)
        return subprocess.CompletedProcess(cmd, 1 if scenario[0] != "ok_unlink" else 0)

    import os

    monkeypatch.setattr(subprocess, "run", fake_run_unlinks)
    (tmp_path / "petstore_oas3.json").unlink()
    (examples_dir / "bad.yaml").unlink()

    scenario[0] = "fail_from_unlink"
    check_conformance_project.check_project(str(proj_dir), str(md_file), ["./bin/cdd-swift"], root_dir=tmp_path)

    def fake_run_fail_to_unlink(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Pass from_openapi, then unlink temp files and fail on to_openapi."""
        if "to_openapi" in " ".join(cmd):
            for arg in cmd:
                if arg.endswith(".json") and os.path.exists(arg):
                    os.remove(arg)
            return subprocess.CompletedProcess(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run_fail_to_unlink)
    check_conformance_project.check_project(str(proj_dir), str(md_file), ["./bin/cdd-swift"], root_dir=tmp_path)

    def fake_run_ok_unlink(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Pass both commands while unlinking temp files before final cleanup."""
        if "to_openapi" in " ".join(cmd):
            for arg in cmd:
                if arg.endswith(".json") and os.path.exists(arg):
                    os.remove(arg)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run_ok_unlink)
    check_conformance_project.check_project(str(proj_dir), str(md_file), ["./bin/cdd-swift"], root_dir=tmp_path)
