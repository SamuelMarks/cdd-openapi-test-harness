"""Unit tests for `local_test.py`."""

import http.client
import io
import os
import subprocess
import unittest.mock as mock
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type

import pytest

import local_test
from harness.errors import AuditFailureError
from harness.registry import ToolchainSpec, get_toolchain, get_toolchains


def test_cleanup_variants() -> None:
    """Verify `cleanup` handles missing docker, running container, and no running container."""
    with mock.patch("shutil.which", side_effect=lambda _: None):
        local_test.cleanup()

    calls: List[List[str]] = []

    def fake_run(
        cmd: List[str],
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Simulate docker ps and docker rm."""
        assert capture_output is True
        assert text in (True, False)
        assert check is False
        calls.append(cmd)
        if "ps" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="container123", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with (
        mock.patch("shutil.which", side_effect=lambda _: "/usr/bin/docker"),
        mock.patch("subprocess.run", side_effect=fake_run),
    ):
        local_test.cleanup()
    assert len(calls) == 2

    with (
        mock.patch("shutil.which", side_effect=lambda _: "/usr/bin/docker"),
        mock.patch(
            "subprocess.run",
            side_effect=lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        ),
    ):
        local_test.cleanup()


def test_chdir_and_xcmd(tmp_path: Path) -> None:
    """Verify `chdir` restores working directory and `xcmd` normalizes Windows paths."""
    orig = Path.cwd()
    with local_test.chdir(str(tmp_path)):
        assert Path.cwd() == tmp_path.resolve()
    assert Path.cwd() == orig

    with mock.patch("os.name", "posix"):
        assert local_test.xcmd(["./gradlew", "run"]) == ["./gradlew", "run"]

    with mock.patch("os.name", "nt"):
        assert local_test.xcmd([]) == []
        assert local_test.xcmd(["cargo", "test"]) == ["cargo", "test"]
        res_grad = local_test.xcmd(["./gradlew", "run"])
        assert res_grad[0].endswith("gradlew.bat")
        res_rel = local_test.xcmd(["../bin/cdd-c"])
        assert res_rel[0] == os.path.normpath("../bin/cdd-c")


def test_run_cmd_variants(tmp_path: Path) -> None:
    """Verify `run_cmd` handles `cwd` relative executables, `which` resolution, and error modes."""
    bin_dir = tmp_path / "cdd-c" / "bin"
    bin_dir.mkdir(parents=True)
    c_exe = bin_dir / "cdd-c"
    c_exe.write_text("exe", encoding="utf-8")

    recorded: List[List[str]] = []

    def fake_sub_run(
        cmd: List[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Record subprocess calls."""
        assert check in (True, False)
        assert cwd is None or isinstance(cwd, str)
        assert env is not None
        assert capture_output in (True, False)
        assert text is True
        recorded.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    with (
        mock.patch("shutil.which", side_effect=lambda x, **_kw: f"/bin/{x}" if x == "echo" else None),
        mock.patch("subprocess.run", side_effect=fake_sub_run),
    ):
        orig_cmd = ["echo", "hello"]
        res = local_test.run_cmd(orig_cmd, env={"FOO": "BAR"})
        assert res.returncode == 0
        assert orig_cmd[0] == "echo"
        assert recorded[-1][0] == "/bin/echo"

        res_rel = local_test.run_cmd(["./bin/cdd-c", "--help"], cwd=str(tmp_path / "cdd-c"))
        assert res_rel.returncode == 0
        assert recorded[-1][0] == str(c_exe.resolve())

        res_rel_missing = local_test.run_cmd(["./bin/missing", "--help"], cwd=str(tmp_path / "cdd-c"))
        assert res_rel_missing.returncode == 0
        assert recorded[-1][0] == "./bin/missing"

        res_empty = local_test.run_cmd([])
        assert res_empty.returncode == 0

    def raise_cpe(
        cmd: List[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Raise CalledProcessError."""
        assert (check, cwd, env, capture_output, text) is not None
        raise subprocess.CalledProcessError(2, cmd, output="out", stderr="err")

    with (
        mock.patch("shutil.which", return_value=None),
        mock.patch("subprocess.run", side_effect=raise_cpe),
    ):
        with pytest.raises(subprocess.CalledProcessError):
            local_test.run_cmd(["custom_cmd"], check=True, ignore_errors=False)

        res_false = local_test.run_cmd(["custom_cmd"], check=False, ignore_errors=True)
        assert res_false.returncode == 2

    def raise_os_err(
        cmd: List[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Raise OSError."""
        assert (cmd, check, cwd, env, capture_output, text) is not None
        raise OSError("spawn failed")

    with (
        mock.patch("shutil.which", return_value=None),
        mock.patch("subprocess.run", side_effect=raise_os_err),
    ):
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


def test_wait_for_server_and_saboteur_and_petstore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `wait_for_server`, `running_saboteur`, `start_petstore`, `setup_emsdk`, and `run_wasm_builds`."""
    monkeypatch.chdir(tmp_path)

    class DummyConn:
        """Dummy context manager for socket.create_connection."""

        def __enter__(self) -> "DummyConn":
            """Enter context."""
            return self

        def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[str],
        ) -> None:
            """Exit context."""
            assert (exc_type, exc_val, exc_tb) is not None
            return None

    with mock.patch("socket.create_connection", return_value=DummyConn()):
        assert local_test.wait_for_server("127.0.0.1", 8080, timeout_s=0.5) is True

    clock = [0.0]

    def fake_monotonic() -> float:
        """Advance simulated monotonic clock."""
        clock[0] += 0.2
        return clock[0]

    def raise_conn_err(addr: Tuple[str, int], timeout: float = 0.1) -> DummyConn:
        """Raise OSError on connection attempt."""
        assert (addr, timeout) is not None
        raise OSError("refused")

    with (
        mock.patch("time.monotonic", side_effect=fake_monotonic),
        mock.patch("time.sleep", side_effect=lambda _: None),
        mock.patch("socket.create_connection", side_effect=raise_conn_err),
    ):
        assert local_test.wait_for_server("127.0.0.1", 8080, timeout_s=0.3) is False

    killed: List[bool] = []

    class FakePopen:
        """Mock Popen for saboteur server."""

        def __init__(self, cmd: List[str]) -> None:
            """Initialize FakePopen.

            Args:
                cmd: Command list.
            """
            self.args = cmd

        def kill(self) -> None:
            """Record kill."""
            killed.append(True)

        def wait(self) -> None:
            """No-op wait."""
            return None

    with (
        mock.patch("subprocess.Popen", FakePopen),
        mock.patch("local_test.wait_for_server", return_value=True),
        local_test.running_saboteur("happy_path", 8080, "custom.log") as proc,
    ):
        assert isinstance(proc.args, list) and "--access-log" in proc.args
    assert killed == [True]

    with mock.patch("shutil.which", side_effect=lambda _: None):
        (tmp_path / "java_petstore_access.log").write_text("old", encoding="utf-8")
        local_test.start_petstore("/v2")
        assert not (tmp_path / "java_petstore_access.log").exists()

    with (
        mock.patch("shutil.which", side_effect=lambda _: "/usr/bin/docker"),
        mock.patch(
            "subprocess.run",
            side_effect=lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        ),
        mock.patch("local_test.wait_for_server", return_value=True),
    ):
        local_test.start_petstore("/v2")

    cmds: List[List[str]] = []

    def fake_run_cmd(
        cmd: Sequence[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        ignore_errors: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Record commands and create emsdk directory on git clone."""
        assert (check, cwd, env, capture_output, ignore_errors) is not None
        c = list(cmd)
        cmds.append(c)
        if c[:2] == ["git", "clone"]:
            (tmp_path / "emsdk").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

    with mock.patch("local_test.run_cmd", side_effect=fake_run_cmd):
        local_test.setup_emsdk()
        assert (tmp_path / "emsdk").is_dir()
        local_test.setup_emsdk()

        for spec in get_toolchains():
            (tmp_path / spec.name).mkdir(exist_ok=True)

        monkeypatch.setenv("ONLY_TEST", "cdd-go")
        local_test.run_wasm_builds()
        monkeypatch.delenv("ONLY_TEST")
    assert any("build_wasm" in c for c in cmds)

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


def test_audit_toolchain_and_run_test_with_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `audit_toolchain` and `run_test_with_audit` across all 3 phases and failure modes."""
    monkeypatch.chdir(tmp_path)

    class FakePopen:
        """Mock Popen for saboteur server."""

        def __init__(self, cmd: List[str]) -> None:
            """Initialize FakePopen.

            Args:
                cmd: Command list.
            """
            self.cmd = cmd

        def kill(self) -> None:
            """No-op kill."""
            return None

        def wait(self) -> None:
            """No-op wait."""
            return None

    spec_file = tmp_path / "petstore.json"
    spec_file.write_text('{"openapi": "3.0.0", "paths": {"/pet": {"get": {}}}}', encoding="utf-8")

    with (
        mock.patch("subprocess.Popen", FakePopen),
        mock.patch("local_test.wait_for_server", return_value=True),
    ):
        monkeypatch.setenv("ONLY_TEST", "cdd-other")
        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", lambda: None) is True
        monkeypatch.delenv("ONLY_TEST")

        def fail_action() -> None:
            """Raise RuntimeError."""
            raise RuntimeError("boom")

        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", fail_action) is False

        (tmp_path / "java_petstore_access.log").write_text("stale", encoding="utf-8")
        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", lambda: None) is False

        def write_hit_log() -> None:
            """Write valid hit log during Phase 1."""
            (tmp_path / "java_petstore_access.log").write_text(
                '127.0.0.1 - - [24/Oct/2026:00:00:00 +0000] "GET /v2/pet HTTP/1.1" 200 10',
                encoding="utf-8",
            )

        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", write_hit_log) is False

        calls = [0]

        def pass_twice_then_fail() -> None:
            """Pass in Phase 1 and fail in Phase 2, then pass in Phase 3."""
            calls[0] += 1
            if calls[0] == 1:
                write_hit_log()
            elif calls[0] == 2:
                raise RuntimeError("expected 500 failure")

        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", pass_twice_then_fail) is False

        calls_ok = [0]

        def pass_once_then_fail_on_saboteur() -> None:
            """Pass in Phase 1 with hit log, then fail in Phase 2 and Phase 3."""
            calls_ok[0] += 1
            if calls_ok[0] == 1:
                write_hit_log()
            else:
                raise RuntimeError("saboteur caught")

        assert local_test.run_test_with_audit("cdd-ts", "petstore.json", "/v2", pass_once_then_fail_on_saboteur) is True

        empty_spec = tmp_path / "empty_paths.json"
        empty_spec.write_text('{"openapi": "3.0.0", "paths": {}}', encoding="utf-8")
        calls_empty = [0]

        def pass_empty_then_fail() -> None:
            """Pass Phase 1 on empty spec, fail Phase 2 & 3."""
            calls_empty[0] += 1
            if calls_empty[0] >= 2:
                raise RuntimeError("saboteur caught")

        assert local_test.run_test_with_audit("cdd-ts", "empty_paths.json", "/v2", pass_empty_then_fail) is True


def test_exercise_sdk_endpoints_all_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `exercise_sdk_endpoints` across missing file, invalid shapes, success, HTTP error, and sabotage."""
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
            """Initialize FakeResp.

            Args:
                status: HTTP status code.
                body: Response payload bytes.
            """
            self.status = status
            self.body = body

        def read(self) -> bytes:
            """Return response bytes."""
            return self.body

        def __enter__(self) -> "FakeResp":
            """Enter context manager."""
            return self

        def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[str],
        ) -> None:
            """Exit context manager."""
            assert (exc_type, exc_val, exc_tb) is not None
            return None

    with mock.patch("urllib.request.urlopen", side_effect=lambda _req, **_kw: FakeResp(200, b'{"id": 1}')):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    with mock.patch("urllib.request.urlopen", side_effect=lambda _req, **_kw: FakeResp(204, b"")):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    with (
        mock.patch("urllib.request.urlopen", side_effect=lambda _req, **_kw: FakeResp(500, b"{}")),
        pytest.raises(AuditFailureError, match="Unexpected status 500"),
    ):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    def raise_http_err(req: urllib.request.Request, timeout: int = 5) -> FakeResp:
        """Raise HTTPError with a typed HTTPMessage."""
        assert (req, timeout) is not None
        hdrs = http.client.HTTPMessage()
        raise urllib.error.HTTPError("http://localhost", 500, "Internal", hdrs, io.BytesIO(b""))

    with (
        mock.patch("urllib.request.urlopen", side_effect=raise_http_err),
        pytest.raises(AuditFailureError, match="HTTP error 500"),
    ):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")

    with (
        mock.patch("urllib.request.urlopen", side_effect=lambda _req, **_kw: FakeResp(200, b'{"sabotage": true}')),
        pytest.raises(AuditFailureError, match="Invalid schema"),
    ):
        local_test.exercise_sdk_endpoints("petstore_oas3.json")


def test_individual_toolchain_runners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all 13 `test_cdd_*` functions execute their exact build, SDK generation, and test steps."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "petstore.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    (tmp_path / "kotlin-integration.kt").write_text("// kotlin test", encoding="utf-8")

    for spec in get_toolchains():
        (tmp_path / spec.name).mkdir(exist_ok=True)

    recorded_cmds: List[Tuple[List[str], Optional[str]]] = []
    create_clients = [True]

    def fake_run_cmd(
        cmd: Sequence[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        ignore_errors: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Record commands and materialize generated client directories when `from_openapi` runs."""
        assert (check, env, capture_output, ignore_errors) is not None
        c = list(cmd)
        recorded_cmds.append((c, cwd))
        if create_clients[0]:
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
            if "node-client" in c:
                (tmp_path / "cdd-ts" / "node-client").mkdir(parents=True, exist_ok=True)
            if cwd == "cdd-sh" and "from_openapi" in c:
                routes_dir = tmp_path / "sh-client" / "tests"
                routes_dir.mkdir(parents=True, exist_ok=True)
                (routes_dir / "test_routes.sh").write_text("#!/bin/sh", encoding="utf-8")
        return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

    with (
        mock.patch("local_test.run_cmd", side_effect=fake_run_cmd),
        mock.patch("local_test.build_typescript_toolchain", return_value=None),
        mock.patch("local_test.run_typescript_toolchain_tests", return_value=None),
        mock.patch("local_test.run_c_sdk_test_suite", return_value=None),
    ):
        local_test.test_cdd_ts("petstore.json")
        assert any(c == ["npx", "vitest", "run", "src/integration.spec.ts"] for c, _ in recorded_cmds)

        local_test.test_cdd_kotlin("petstore.json")
        assert (tmp_path / "kotlin-client" / "src" / "commonTest" / "kotlin" / "IntegrationTest.kt").exists()
        assert any(c == ["./gradlew", "test"] and cwd == "kotlin-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_go("petstore.json")
        assert any(c == ["go", "test", "./..."] and cwd == "cdd-go-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_csharp("petstore.json")
        assert any(
            c == ["dotnet", "test", "GeneratedProject.sln"] and cwd == "cdd-csharp-client" for c, cwd in recorded_cmds
        )

        local_test.test_cdd_python_all("petstore.json")
        assert any(c == ["pytest", "test/"] and cwd == "cdd-python-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_rust("petstore.json")
        assert any(c == ["cargo", "test"] and cwd == "cdd-rust-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_swift("petstore.json")
        assert any(c == ["swift", "test"] and cwd == "cdd-swift-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_c("petstore.json")

        local_test.test_cdd_cpp("petstore.json")
        assert any(
            c == ["ctest", "--test-dir", "build", "--output-on-failure"] and cwd == "cdd-cpp-client"
            for c, cwd in recorded_cmds
        )

        local_test.test_cdd_java("petstore.json")
        assert any(c == ["mvn", "test"] and cwd == "cdd-java-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_php("petstore.json")
        assert any(c == ["vendor/bin/phpunit"] and cwd == "php-client" for c, cwd in recorded_cmds)

        local_test.test_cdd_ruby("petstore.json")
        assert any(c == ["bundle", "exec", "rake", "test"] and cwd == "cdd-ruby-client" for c, cwd in recorded_cmds)

        src_sub = tmp_path / "cdd-sh" / "src" / "sub"
        src_sub.mkdir(parents=True, exist_ok=True)
        (src_sub / "helper.sh").write_text("#!/bin/sh", encoding="utf-8")
        (tmp_path / "cdd-sh" / "src" / "file.txt").write_text("txt", encoding="utf-8")

        with mock.patch("shutil.which", side_effect=lambda x: "/usr/bin/shellcheck" if x == "shellcheck" else None):
            local_test.test_cdd_sh("petstore.json")
        assert any(c == ["./tests/test_routes.sh"] and cwd == "sh-client" for c, cwd in recorded_cmds)

        create_clients[0] = False
        (tmp_path / "kotlin-integration.kt").unlink()
        for c_dir in (
            "angular-client",
            "kotlin-client",
            "cdd-go-client",
            "cdd-csharp-client",
            "cdd-python-client",
            "cdd-rust-client",
            "cdd-swift-client",
            "cdd-cpp-client",
            "cdd-java-client",
            "php-client",
            "cdd-ruby-client",
            "sh-client",
        ):
            if (tmp_path / c_dir).exists():
                (tmp_path / c_dir).rmdir() if not list((tmp_path / c_dir).iterdir()) else None

        import shutil as _shutil

        for c_dir in (
            "angular-client",
            "kotlin-client",
            "cdd-go-client",
            "cdd-csharp-client",
            "cdd-python-client",
            "cdd-rust-client",
            "cdd-swift-client",
            "cdd-cpp-client",
            "cdd-java-client",
            "php-client",
            "cdd-ruby-client",
            "sh-client",
        ):
            _shutil.rmtree(tmp_path / c_dir, ignore_errors=True)
        _shutil.rmtree(tmp_path / "cdd-ts" / "node-client", ignore_errors=True)

        local_test.test_cdd_ts("petstore.json")
        local_test.test_cdd_kotlin("petstore.json")
        local_test.test_cdd_go("petstore.json")
        local_test.test_cdd_csharp("petstore.json")
        local_test.test_cdd_python_all("petstore.json")
        local_test.test_cdd_rust("petstore.json")
        local_test.test_cdd_swift("petstore.json")

        def fake_run_cmd_no_cpp_client(
            cmd: Sequence[str],
            check: bool = True,
            cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None,
            capture_output: bool = False,
            ignore_errors: bool = False,
        ) -> subprocess.CompletedProcess[str]:
            """Remove cdd-cpp-client when from_openapi runs to test false branch."""
            assert (check, cwd, env, capture_output, ignore_errors) is not None
            if "from_openapi" in cmd:
                _shutil.rmtree(tmp_path / "cdd-cpp-client", ignore_errors=True)
            return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

        with mock.patch("local_test.run_cmd", side_effect=fake_run_cmd_no_cpp_client):
            local_test.test_cdd_cpp("petstore.json")

        local_test.test_cdd_java("petstore.json")
        local_test.test_cdd_php("petstore.json")
        local_test.test_cdd_ruby("petstore.json")

        with mock.patch("shutil.which", side_effect=lambda _: None):
            local_test.test_cdd_sh("petstore.json")

        def fake_run_cmd_sh_empty(
            cmd: Sequence[str],
            check: bool = True,
            cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None,
            capture_output: bool = False,
            ignore_errors: bool = False,
        ) -> subprocess.CompletedProcess[str]:
            """Create empty sh-client without test_routes.sh and remove temp spec."""
            assert (check, cwd, env, capture_output, ignore_errors) is not None
            c = list(cmd)
            if "from_openapi" in c:
                (tmp_path / "sh-client").mkdir(exist_ok=True)
                in_idx = c.index("-i") + 1
                if os.path.exists(c[in_idx]):
                    os.remove(c[in_idx])
            return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

        with (
            mock.patch("shutil.which", side_effect=lambda _: None),
            mock.patch("local_test.run_cmd", side_effect=fake_run_cmd_sh_empty),
        ):
            local_test.test_cdd_sh("petstore.json")


def test_run_test_and_run_roundtrip_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_test`, `run_roundtrip`, and `main` across all CLI modes and branches."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "petstore.json").write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    for spec in get_toolchains():
        (tmp_path / spec.name).mkdir(exist_ok=True)

    rt_cmds: List[List[str]] = []

    def fake_run_cmd_rt(
        cmd: Sequence[str],
        check: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        ignore_errors: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Materialize SDK subpaths and roundtrip output specs."""
        assert (check, cwd, env, capture_output, ignore_errors) is not None
        c = list(cmd)
        rt_cmds.append(c)
        cmd_str = " ".join(c)
        if "-o" in c:
            out_target = c[c.index("-o") + 1]
            if out_target.endswith(".json"):
                Path(out_target).write_text('{"openapi": "3.2.0"}', encoding="utf-8")
            elif "swift" in str(cwd):
                swift_dir = Path(out_target) / "Sources" / "GeneratedSDK"
                swift_dir.mkdir(parents=True, exist_ok=True)
                (swift_dir / "models.swift").write_text("// swift", encoding="utf-8")
        elif "--args=to_openapi" in cmd_str:
            out_file = c[-1].split("-o ")[-1]
            Path(out_file).write_text('{"openapi": "3.2.0"}', encoding="utf-8")
        return subprocess.CompletedProcess(c, 0, stdout="", stderr="")

    with mock.patch("local_test.run_cmd", side_effect=fake_run_cmd_rt):
        local_test.run_roundtrip()
    assert len(rt_cmds) >= 13 * 3

    no_build_spec = get_toolchain("cdd-c")
    custom_spec = ToolchainSpec(
        name=no_build_spec.name,
        language=no_build_spec.language,
        target_type=no_build_spec.target_type,
        build_cmd=(),
        check_cmd=no_build_spec.check_cmd,
        wasm_cmd=no_build_spec.wasm_cmd,
        roundtrip_from_cmd=no_build_spec.roundtrip_from_cmd,
        roundtrip_to_cmd=no_build_spec.roundtrip_to_cmd,
        roundtrip_input_subpath="nonexistent_subpath",
    )
    with mock.patch(
        "local_test.run_cmd",
        side_effect=lambda cmd, **_kw: subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr=""),
    ):
        local_test.run_toolchain_roundtrip(custom_spec, "petstore.json")

    monkeypatch.setenv("IGNORE_TESTS", ",".join(s.name for s in get_toolchains()))
    local_test.run_roundtrip()
    monkeypatch.delenv("IGNORE_TESTS")

    audited_langs: List[str] = []

    def fake_audit_pass(lang: str, spec: str, base: str, action: Callable[[], None]) -> bool:
        """Record audited language and return True."""
        assert spec in ("petstore.json", "petstore_oas3.json")
        assert base in ("/v2", "/api/v3")
        assert callable(action)
        audited_langs.append(lang)
        return True

    with mock.patch("local_test.run_test_with_audit", side_effect=fake_audit_pass):
        local_test.run_test()
    assert len(audited_langs) == 26

    with (
        mock.patch("local_test.run_test_with_audit", return_value=False),
        pytest.raises(AuditFailureError),
    ):
        local_test.run_test()

    with (
        mock.patch("atexit.register", side_effect=lambda _: None),
        mock.patch("local_test.run_test", side_effect=lambda: None),
        mock.patch("local_test.run_wasm_builds", side_effect=lambda: None),
        mock.patch("local_test.run_roundtrip", side_effect=lambda: None),
    ):
        local_test.main(["roundtrip"])
        local_test.main(["all"])
        local_test.main(["only-test"])
        local_test.main([])

    def raise_audit_fail() -> None:
        """Raise AuditFailureError."""
        raise AuditFailureError("cdd-ts", "happy_path", "failed")

    with (
        mock.patch("atexit.register", side_effect=lambda _: None),
        mock.patch("local_test.run_test", side_effect=raise_audit_fail),
        mock.patch("sys.exit") as mock_exit,
    ):
        local_test.main(["only-test"])
        mock_exit.assert_called_once_with(1)
