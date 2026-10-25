"""Unit tests for `scripts/check_all_conformance.py` and `scripts/check_conformance_project.py`."""

import os
import subprocess
import unittest.mock as mock
from pathlib import Path
from typing import List, Optional

from scripts import check_all_conformance, check_conformance_project


def test_check_all_conformance(tmp_path: Path) -> None:
    """Verify `check_all_conformance.run_check` and `main` across missing/existing directories."""
    assert check_all_conformance.main(root_dir=tmp_path) == 1

    (tmp_path / "OAI-OpenAPI-Specification").mkdir()
    (tmp_path / "cdd-c").mkdir()
    (tmp_path / "cdd-java").mkdir()

    calls: List[List[str]] = []

    def fake_run(
        cmd: List[str],
        cwd: Optional[str] = None,
        stdout: Optional[int] = None,
        stderr: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Record subprocess calls and verify working directory is explicitly supplied."""
        assert cwd is not None
        assert check is False
        assert stdout in (None, subprocess.DEVNULL)
        assert stderr in (None, subprocess.DEVNULL)
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        assert check_all_conformance.run_check("cdd-c", ["make"], ["./bin/cdd-c"], root_dir=tmp_path) is True
        assert check_all_conformance.run_check("cdd-java", [], ["./gradlew"], root_dir=tmp_path) is True
        assert check_all_conformance.run_check("cdd-missing", ["make"], ["./bin"], root_dir=tmp_path) is False
        assert check_all_conformance.run_check("cdd-missing", [], ["./bin"]) is False
        assert check_all_conformance.main(root_dir=tmp_path) == 0

    assert len(calls) >= 5
    assert calls[0] == ["make"]


def test_check_conformance_project_all_branches(tmp_path: Path) -> None:
    """Verify `check_conformance_project` covers invalid YAML, CLI fallback, Swift, Rust, and cleanup."""
    assert check_conformance_project.main([]) == 1

    proj_dir = tmp_path / "cdd-swift"
    md_file = tmp_path / "client-sdk.md"

    assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 1
    proj_dir.mkdir()
    assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 1
    md_file.write_text("# Conformance", encoding="utf-8")

    examples_dir = tmp_path / "OAI-OpenAPI-Specification" / "examples" / "v3.0"
    examples_dir.mkdir(parents=True)
    (examples_dir / "good.yaml").write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    (examples_dir / "bad.yaml").write_text("::: [unclosed", encoding="utf-8")
    (tmp_path / "petstore_oas3.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    scenario = ["swift_to_openapi"]
    executed_cmds: List[List[str]] = []

    def fake_run(
        cmd: List[str],
        cwd: Optional[str] = None,
        stdout: Optional[int] = None,
        stderr: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Simulate CLI invocations across Swift, Rust, Gradle, fallback, and failure scenarios."""
        assert cwd is not None
        assert check is False
        assert stdout == subprocess.DEVNULL
        assert stderr == subprocess.DEVNULL
        executed_cmds.append(cmd)
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

        if scenario[0] == "rust_to_openapi":
            for arg in cmd:
                if "cdd_conf_" in arg and Path(arg).is_dir():
                    (Path(arg) / "src").mkdir(exist_ok=True)
                elif arg.endswith(".json") and "to_openapi" in cmd_str:
                    Path(arg).write_text('{"openapi":"3.2.0"}', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        return subprocess.CompletedProcess(cmd, 0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        assert (
            check_conformance_project.main(
                [str(proj_dir), str(md_file), "./gradlew", "run", "--args="],
                root_dir=tmp_path,
            )
            == 0
        )
        assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 0
        assert any("models.swift" in " ".join(c) for c in executed_cmds)

        rust_dir = tmp_path / "cdd-rust"
        rust_dir.mkdir()
        scenario[0] = "rust_to_openapi"
        assert check_conformance_project.main([str(rust_dir), str(md_file), "./bin/cdd-cli"], root_dir=tmp_path) == 0
        assert any(os.path.join("src") in " ".join(c) for c in executed_cmds)

        other_dir = tmp_path / "cdd-c"
        other_dir.mkdir()
        assert check_conformance_project.main([str(other_dir), str(md_file), "./bin/cdd-c"], root_dir=tmp_path) == 0

        scenario[0] = "fail_both_from"
        assert (
            check_conformance_project.main(
                [str(proj_dir), str(md_file), "./gradlew", "run", "--args="],
                root_dir=tmp_path,
            )
            == 0
        )

        scenario[0] = "fallback_from_and_fail_to"
        assert check_conformance_project.main([str(proj_dir), str(md_file), "./bin/cdd-swift"], root_dir=tmp_path) == 0

    (tmp_path / "petstore_oas3.json").unlink()
    (examples_dir / "bad.yaml").unlink()

    def fake_run_unlinks(
        cmd: List[str],
        cwd: Optional[str] = None,
        stdout: Optional[int] = None,
        stderr: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Remove temp files during run to cover false branches of os.path.exists cleanup."""
        assert cwd is not None
        assert check is False
        assert stdout == subprocess.DEVNULL
        assert stderr == subprocess.DEVNULL
        for arg in cmd:
            if arg.endswith(".json") and os.path.exists(arg):
                os.remove(arg)
        return subprocess.CompletedProcess(cmd, 1)

    with mock.patch("subprocess.run", side_effect=fake_run_unlinks):
        res_code = check_conformance_project.check_project(
            str(proj_dir),
            str(md_file),
            ["./bin/cdd-swift"],
            root_dir=tmp_path,
        )
        assert res_code == 0

    temp_d = tmp_path / "manual_tmp"
    temp_d.mkdir()
    check_conformance_project._cleanup_temp(
        str(temp_d),
        str(tmp_path / "nonexistent_in.json"),
        str(tmp_path / "nonexistent_out.json"),
    )
    assert not temp_d.exists()
