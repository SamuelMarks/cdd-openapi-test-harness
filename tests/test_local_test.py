"""Unit tests for `local_test.py`."""

import atexit
import os
import shutil
import subprocess
import time
import unittest.mock as mock
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import pytest

import local_test
from harness.registry import get_toolchains


def test_cleanup_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `cleanup` handles missing docker, running container, and no running container."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    local_test.cleanup()

    calls: List[List[str]] = []

    def fake_run(
        cmd: List[str],
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Simulate docker ps and docker rm."""
        calls.append(cmd)
        if "ps" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="container123", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(subprocess, "run", fake_run)
    local_test.cleanup()
    assert len(calls) == 2

    calls.clear()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )
    local_test.cleanup()


def test_chdir_and_xcmd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `chdir` restores working directory and `xcmd` normalizes Windows paths."""
    orig = Path.cwd()
    with local_test.chdir(str(tmp_path)):
        assert Path.cwd() == tmp_path.resolve()
    assert Path.cwd() == orig

    monkeypatch.setattr(os, "name", "posix")
    assert local_test.xcmd(["./gradlew", "run"]) == ["./gradlew", "run"]

    monkeypatch.setattr(os, "name", "nt")
    assert local_test.xcmd([]) == []
    assert local_test.xcmd(["cargo", "test"]) == ["cargo", "test"]
    res_grad = local_test.xcmd(["./gradlew", "run"])
    assert res_grad[0].endswith("gradlew.bat")
    res_rel = local_test.xcmd(["../bin/cdd-c"])
    assert res_rel[0] == os.path.normpath("../bin/cdd-c")


def test_run_cmd_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_cmd` handles env, which resolution, CalledProcessError, and generic exceptions."""
    monkeypatch.setattr(shutil, "which", lambda x: f"/bin/{x}" if x == "echo" else None)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""),
    )
    orig_cmd = ["echo", "hello"]
    res = local_test.run_cmd(orig_cmd, env={"FOO": "BAR"})
    assert res.returncode == 0
    assert orig_cmd[0] == "echo"

    def raise_cpe(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Raise CalledProcessError."""
        raise subprocess.CalledProcessError(2, cmd, output="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", raise_cpe)
    with pytest.raises(subprocess.CalledProcessError):
        local_test.run_cmd(["custom_cmd"], check=True, ignore_errors=False)

    res_false = local_test.run_cmd(["custom_cmd"], check=False, ignore_errors=True)
    assert isinstance(res_false, subprocess.CompletedProcess)
    assert res_false.returncode == 2

    def raise_os_err(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Raise OSError."""
        raise OSError("spawn failed")

    monkeypatch.setattr(subprocess, "run", raise_os_err)
    with pytest.raises(OSError):
        local_test.run_cmd(["custom_cmd"], check=True, ignore_errors=False)

    res_os_false = local_test.run_cmd(["custom_cmd"], check=False, ignore_errors=True)
    assert res_os_false.returncode == 1
    assert "spawn failed" in res_os_false.stderr


def test_role_and_should_run_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `is_client`, `is_server`, and `should_run` across all filter combinations."""
    assert local_test.is_client("cdd-ts") is True
    assert local_test.is_client("unknown") is False
    assert local_test.is_server("cdd-rust") is True
    assert local_test.is_server("cdd-ts") is False
    assert local_test.is_server("unknown") is False

    monkeypatch.delenv("ONLY_TEST", raising=False)
    monkeypatch.delenv("IGNORE_TESTS", raising=False)
    monkeypatch.delenv("TARGET_TYPE", raising=False)
    assert local_test.should_run("cdd-ts") is True

    monkeypatch.setenv("ONLY_TEST", "cdd-ts, cdd-rust")
    assert local_test.should_run("cdd-ts") is True
    assert local_test.should_run("cdd-go") is False
    monkeypatch.delenv("ONLY_TEST")

    monkeypatch.setenv("IGNORE_TESTS", "cdd-go,cdd-c")
    assert local_test.should_run("cdd-go") is False
    assert local_test.should_run("cdd-ts") is True
    monkeypatch.delenv("IGNORE_TESTS")

    monkeypatch.setenv("TARGET_TYPE", "client")
    assert local_test.should_run("cdd-ts") is True
    assert local_test.should_run("unknown-mod") is False

    monkeypatch.setenv("TARGET_TYPE", "server")
    assert local_test.should_run("cdd-rust") is True
    assert local_test.should_run("cdd-ts") is False


def test_start_petstore_and_emsdk_and_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `start_petstore`, `setup_emsdk`, `run_wasm_builds`, `yaml_to_json`, and `_discover_kotlin_env`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    monkeypatch.setattr(shutil, "which", lambda _: None)
    (tmp_path / "java_petstore_access.log").write_text("old", encoding="utf-8")
    local_test.start_petstore("/v2")
    assert not (tmp_path / "java_petstore_access.log").exists()

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )
    local_test.start_petstore("/v2")

    cmds: List[List[str]] = []

    def fake_run_cmd(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Record commands and create emsdk directory on git clone."""
        c = list(cmd)
        cmds.append(c)
        if c[:2] == ["git", "clone"]:
            (tmp_path / "emsdk").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)
    local_test.setup_emsdk()
    assert (tmp_path / "emsdk").is_dir()
    local_test.setup_emsdk()

    for spec in get_toolchains():
        (tmp_path / spec.name).mkdir(exist_ok=True)

    monkeypatch.setenv("ONLY_TEST", "cdd-go")
    local_test.run_wasm_builds()
    monkeypatch.delenv("ONLY_TEST")

    in_yaml = tmp_path / "in.yaml"
    out_json = tmp_path / "out.json"
    in_yaml.write_text('{"a": 1}', encoding="utf-8")
    local_test.yaml_to_json(str(in_yaml), str(out_json))
    assert '"a": 1' in out_json.read_text(encoding="utf-8")

    monkeypatch.delenv("GRADLE_USER_HOME", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    assert local_test._discover_kotlin_env() == {}

    monkeypatch.setenv("GRADLE_USER_HOME", "/tmp/gradle")
    monkeypatch.setenv("JAVA_HOME", "/tmp/java")
    assert local_test._discover_kotlin_env() == {
        "GRADLE_USER_HOME": "/tmp/gradle",
        "JAVA_HOME": "/tmp/java",
    }


def test_run_test_with_audit_all_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_test_with_audit` across skip, phase 1 failure, coverage failure, phase 2/3, and success."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(local_test, "start_petstore", lambda *a: None)

    class FakePopen:
        """Mock Popen for saboteur server."""

        def __init__(self, cmd: List[str]) -> None:
            """Initialize FakePopen."""
            self.cmd = cmd

        def kill(self) -> None:
            """No-op kill."""
            return None

        def wait(self) -> None:
            """No-op wait."""
            return None

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 1 if "verify_coverage.py" in cmd else 0, stdout="cov out", stderr="cov err"
        ),
    )

    monkeypatch.setenv("ONLY_TEST", "cdd-other")
    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", lambda: None) is True
    monkeypatch.delenv("ONLY_TEST")

    def fail_action() -> None:
        """Raise RuntimeError."""
        raise RuntimeError("boom")

    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", fail_action) is False

    (tmp_path / "java_petstore_access.log").write_text("GET /v2/pet", encoding="utf-8")
    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", lambda: None) is False

    (tmp_path / "java_petstore_access.log").unlink()

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""),
    )

    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", lambda: None) is False

    calls = [0]

    def pass_twice_then_fail() -> None:
        """Pass in Phase 1 and Phase 2, fail in Phase 3."""
        calls[0] += 1
        if calls[0] == 2:
            raise RuntimeError("expected 500 failure")

    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", pass_twice_then_fail) is False

    calls_ok = [0]

    def pass_once_then_fail_on_saboteur() -> None:
        """Pass in Phase 1, fail in Phase 2 and Phase 3."""
        calls_ok[0] += 1
        if calls_ok[0] >= 2:
            raise RuntimeError("saboteur caught")

    assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", pass_once_then_fail_on_saboteur) is True


def test_exercise_sdk_endpoints_all_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `exercise_sdk_endpoints` across missing file, invalid shapes, success, HTTP error, and sabotage."""
    import io
    import urllib.error
    import urllib.request

    monkeypatch.chdir(tmp_path)
    local_test.exercise_sdk_endpoints("nonexistent.json")

    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    local_test.exercise_sdk_endpoints("list.json")

    (tmp_path / "bad_paths.json").write_text('{"paths": []}', encoding="utf-8")
    local_test.exercise_sdk_endpoints("bad_paths.json")

    spec_file = tmp_path / "petstore_oas3.json"
    spec_file.write_text(
        '{"paths": {"/bad": "str", "/pet/{id}": {"parameters": [], "get": {}, "post": {}}}}',
        encoding="utf-8",
    )

    class FakeResp:
        """Mock urllib response."""

        def __init__(self, status: int, body: bytes) -> None:
            """Initialize FakeResp."""
            self.status = status
            self.body = body

        def read(self) -> bytes:
            """Return response bytes."""
            return self.body

        def __enter__(self) -> "FakeResp":
            """Enter context manager."""
            return self

        def __exit__(self, *args: object) -> None:
            """Exit context manager."""
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5: FakeResp(200, b'{"id": 1}'))
    local_test.exercise_sdk_endpoints("petstore_oas3.json")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5: FakeResp(204, b""))
    local_test.exercise_sdk_endpoints("petstore_oas3.json")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5: FakeResp(500, b"{}"))
    with pytest.raises(RuntimeError, match="Unexpected status 500"):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    def raise_http_err(req: object, timeout: int = 5) -> FakeResp:
        """Raise HTTPError."""
        raise urllib.error.HTTPError("http://localhost", 500, "Internal", None, io.BytesIO(b""))  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", raise_http_err)
    with pytest.raises(RuntimeError, match="HTTP error 500"):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5: FakeResp(200, b'{"sabotage": true}'))
    with pytest.raises(RuntimeError, match="Invalid schema"):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")


def test_individual_toolchain_runners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all 13 `test_cdd_*` functions execute their build and test steps cleanly."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "petstore.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")

    for spec in get_toolchains():
        (tmp_path / spec.name).mkdir(exist_ok=True)

    for client_dir in (
        "angular-client",
        "kotlin-client",
        "cdd-go-client",
        "cdd-csharp-client",
        "cdd-python-client",
        "cdd-rust-client",
        "cdd-swift-client",
        "cdd-c-client",
        "cdd-cpp-client",
        "cdd-java-client",
        "php-client",
        "cdd-ruby-client",
        "sh-client",
    ):
        (tmp_path / client_dir).mkdir(exist_ok=True)

    def fake_run_cmd(
        cmd: Sequence[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        ignore_errors: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Re-create target client directories removed by shutil.rmtree."""
        for c_dir in (
            "angular-client",
            "kotlin-client",
            "cdd-go-client",
            "cdd-csharp-client",
            "cdd-python-client",
            "cdd-rust-client",
            "cdd-swift-client",
            "cdd-c-client",
            "cdd-cpp-client",
            "cdd-java-client",
            "php-client",
            "cdd-ruby-client",
            "sh-client",
        ):
            (tmp_path / c_dir).mkdir(exist_ok=True)
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)

    local_test.test_cdd_ts("petstore.json")

    def fake_run_cmd_ts_with_spec(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create node-client/src/integration.spec.ts when cdd-ts generates node SDK."""
        if "node-client" in cmd:
            spec_dir = tmp_path / "cdd-ts" / "node-client" / "src"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "integration.spec.ts").write_text("import {} from 'vitest';\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_ts_with_spec)
    local_test.test_cdd_ts("petstore.json")
    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)

    monkeypatch.setenv("JAVA_HOME", "/tmp/jdk")
    local_test.test_cdd_kotlin("petstore.json")
    monkeypatch.delenv("JAVA_HOME")
    local_test.test_cdd_kotlin("petstore.json")

    local_test.test_cdd_go("petstore.json")

    def fake_run_cmd_go(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create models/components.go in cdd-go-client."""
        go_models = tmp_path / "cdd-go-client" / "models"
        go_models.mkdir(parents=True, exist_ok=True)
        if "from_openapi" in cmd:
            (go_models / "components.go").write_text("package models\nvar X OAuthFlows\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_go)
    local_test.test_cdd_go("petstore.json")

    def fake_run_cmd_go_already(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create models/components.go with type OAuthFlows already present."""
        go_models = tmp_path / "cdd-go-client" / "models"
        go_models.mkdir(parents=True, exist_ok=True)
        if "from_openapi" in cmd:
            (go_models / "components.go").write_text("package models\ntype OAuthFlows struct{}\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_go_already)
    local_test.test_cdd_go("petstore.json")
    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)

    local_test.test_cdd_csharp("petstore.json")
    local_test.test_cdd_python_all("petstore.json")

    def fake_run_cmd_py(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create test/test_api.py and test/test_client.py in cdd-python-client."""
        py_test_dir = tmp_path / "cdd-python-client" / "test"
        py_test_dir.mkdir(parents=True, exist_ok=True)
        (py_test_dir / "test_api.py").write_text("test_operations = [1]\n", encoding="utf-8")
        (py_test_dir / "test_client.py").write_text("client.add_pet(body={})\ndata = json.loads(x)\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_py)
    local_test.test_cdd_python_all("petstore.json")
    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)

    local_test.test_cdd_rust("petstore.json")
    local_test.test_cdd_swift("petstore.json")
    local_test.test_cdd_c("petstore.json")
    (tmp_path / "cdd-c" / "build_cmake").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cdd-c" / "build_cmake" / "cdd-c").write_text("bin", encoding="utf-8")
    local_test.test_cdd_c("petstore.json")
    local_test.test_cdd_cpp("petstore.json")
    local_test.test_cdd_java("petstore.json")
    local_test.test_cdd_php("petstore.json")

    (tmp_path / "cdd-php" / "composer.lock").write_text("lock", encoding="utf-8")

    def fake_run_cmd_php(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create composer.lock and tests/ApiTests.php in php-client."""
        php_dir = tmp_path / "php-client"
        (php_dir / "tests").mkdir(parents=True, exist_ok=True)
        if "from_openapi" in cmd:
            (php_dir / "composer.lock").write_text("lock", encoding="utf-8")
            (php_dir / "tests" / "ApiTests.php").write_text("<?php", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_php)
    local_test.test_cdd_php("petstore.json")
    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)

    def fake_run_cmd_ruby(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Ensure cdd-ruby-client exists."""
        c_dir = tmp_path / "cdd-ruby-client"
        c_dir.mkdir(exist_ok=True)
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_ruby)
    local_test.test_cdd_ruby("petstore.json")
    (tmp_path / "cdd-ruby" / "Gemfile.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "cdd-ruby" / "cdd-ruby.gemspec").write_text("spec.license = 'MIT OR Apache-2.0'\n", encoding="utf-8")
    (tmp_path / "cdd-ruby" / "Gemfile").write_text("gem 'minitest', '~> 6.0'\n", encoding="utf-8")
    local_test.test_cdd_ruby("petstore.json")
    local_test.test_cdd_ruby("petstore.json")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd)
    src_sub = tmp_path / "cdd-sh" / "src" / "sub"
    src_sub.mkdir(parents=True, exist_ok=True)
    (src_sub / "helper.sh").write_text("#!/bin/sh", encoding="utf-8")
    (tmp_path / "cdd-sh" / "src" / "file.txt").write_text("txt", encoding="utf-8")

    def fake_run_cmd_sh(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create sh-client/tests/test_routes.sh when cdd.sh generates SDK."""
        if "from_openapi" in cmd:
            routes_dir = tmp_path / "sh-client" / "tests"
            routes_dir.mkdir(parents=True, exist_ok=True)
            (routes_dir / "test_routes.sh").write_text("#!/bin/sh", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_sh)
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/shellcheck" if x == "shellcheck" else None)
    local_test.test_cdd_sh("petstore.json")

    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(
        local_test,
        "run_cmd",
        lambda cmd, **kw: subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr=""),
    )
    local_test.test_cdd_sh("petstore.json")

    def fake_run_cmd_sh_empty_dir(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create sh-client without test_routes.sh."""
        if "from_openapi" in cmd:
            (tmp_path / "sh-client").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_sh_empty_dir)
    local_test.test_cdd_sh("petstore.json")


def test_run_test_and_run_roundtrip_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_test`, `run_roundtrip`, and `main` across all CLI modes and branches."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "petstore.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    for spec in get_toolchains():
        (tmp_path / spec.name).mkdir(exist_ok=True)
    (tmp_path / "cdd-rust-client").mkdir(exist_ok=True)

    def fake_run_cmd_rt(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create output files expected by roundtrip cleanup branches."""
        c = list(cmd)
        if "cdd-rust" in c:
            (tmp_path / "cdd-rust-client").mkdir(exist_ok=True)
        if "-o" in c:
            out_target = c[c.index("-o") + 1]
            if out_target.endswith((".yaml", ".json")):
                Path(out_target).parent.mkdir(parents=True, exist_ok=True)
                Path(out_target).write_text("{}", encoding="utf-8")
        if "--args=to_openapi -i ../temp-kt --format yaml -o ../temp-kt-spec.yaml" in c:
            (tmp_path / "temp-kt-spec.yaml").write_text("{}", encoding="utf-8")
        if "cdd-sh" in os.getcwd():
            Path("ast.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_rt)
    local_test.run_roundtrip()

    def fake_run_cmd_rust_client(cmd: Sequence[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Create cdd-rust-client and return CompletedProcess."""
        (tmp_path / "cdd-rust-client").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(local_test, "run_cmd", fake_run_cmd_rust_client)
    for f_unlink in (
        "temp-c-spec.json",
        "temp-cpp-spec.json",
        "temp-php-spec.json",
        "temp-rb-spec.json",
        "temp-java-spec.json",
    ):
        if (tmp_path / f_unlink).exists():
            (tmp_path / f_unlink).unlink()
    monkeypatch.setattr(local_test, "yaml_to_json", lambda i, o: None)
    local_test.run_roundtrip()

    monkeypatch.setenv("IGNORE_TESTS", ",".join(s.name for s in get_toolchains()))
    local_test.run_roundtrip()
    monkeypatch.delenv("IGNORE_TESTS")

    def fake_audit_pass(lang: str, spec: str, base: str, action: Callable[[], None]) -> bool:
        """Invoke action and return True."""
        return True

    monkeypatch.setattr(local_test, "run_test_with_audit", fake_audit_pass)
    local_test.run_test()

    monkeypatch.setattr(local_test, "run_test_with_audit", lambda *a: False)
    with mock.patch("sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            local_test.run_test()

    monkeypatch.setattr(atexit, "register", lambda _: None)
    monkeypatch.setattr(local_test, "start_petstore", lambda *a: None)
    monkeypatch.setattr(local_test, "run_test", lambda: None)
    monkeypatch.setattr(local_test, "run_wasm_builds", lambda: None)
    monkeypatch.setattr(local_test, "run_roundtrip", lambda: None)

    local_test.main(["roundtrip"])
    local_test.main(["all"])
    local_test.main(["only-test"])
    local_test.main([])
