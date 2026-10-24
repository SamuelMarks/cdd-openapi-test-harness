"""Unit tests for `saboteur_server.py`."""

import io
import sys
import unittest.mock as mock
from typing import List, Tuple

import pytest

import saboteur_server


class DummySaboteurHandler(saboteur_server.SaboteurServer):
    """In-memory test harness subclass of `SaboteurServer` avoiding real sockets."""

    def __init__(self, mode: str) -> None:
        """Initialize in-memory response capture buffers.

        Args:
            mode: Sabotage mode to test ('500', 'invalid_schema', or unknown).
        """
        self.mode = mode
        self.buffer: io.BytesIO = io.BytesIO()
        self.wfile = self.buffer
        self.status_codes: List[int] = []
        self.headers_sent: List[Tuple[str, str]] = []
        self.headers_ended: bool = False

    def send_response(self, code: int, message: object = None) -> None:
        """Record the HTTP response status code.

        Args:
            code: HTTP status code.
            message: Optional reason phrase.
        """
        self.status_codes.append(code)

    def send_header(self, keyword: str, value: str) -> None:
        """Record an HTTP response header.

        Args:
            keyword: Header name.
            value: Header value.
        """
        self.headers_sent.append((keyword, value))

    def end_headers(self) -> None:
        """Record completion of HTTP headers."""
        self.headers_ended = True


def test_saboteur_server_modes_and_methods(tmp_path: pytest.TempPathFactory) -> None:
    """Verify `SaboteurServer` handles 'happy_path', '500', 'invalid_schema', unknown mode, and all HTTP verbs."""
    assert b"KtorIntegrationDog" in saboteur_server.build_petstore_payload("GET", "/v2/pet/findByStatus?status=sold")
    assert b"available" in saboteur_server.build_petstore_payload("GET", "/v2/store/inventory")
    assert b"placed" in saboteur_server.build_petstore_payload("GET", "/v2/store/order/1")
    assert b"logged_in_session" in saboteur_server.build_petstore_payload("GET", "/v2/user/login")
    assert b"user1" in saboteur_server.build_petstore_payload("GET", "/v2/user/user1")
    assert b"KtorIntegrationDog" in saboteur_server.build_petstore_payload("GET", "/v2/pet/1")
    assert b"unknown" in saboteur_server.build_petstore_payload("POST", "/v2/pet/1/uploadImage")

    h_happy = DummySaboteurHandler("happy_path")
    log_file = tmp_path / "access.log"  # type: ignore[operator]
    h_happy.access_log_path = str(log_file)
    h_happy.command = "POST"
    h_happy.path = "/v2/pet"
    h_happy.headers = {"Content-Length": "4"}  # type: ignore[assignment]
    h_happy.rfile = io.BytesIO(b"{}\r\n")
    h_happy.handle_request()
    assert h_happy.status_codes == [200]
    assert log_file.exists()

    h_happy_no_log = DummySaboteurHandler("happy_path")
    h_happy_no_log.access_log_path = None
    h_happy_no_log.headers = {"Content-Length": "0"}  # type: ignore[assignment]
    h_happy_no_log.rfile = io.BytesIO(b"")
    h_happy_no_log.handle_request()
    assert h_happy_no_log.status_codes == [200]

    h_happy_empty_hdr = DummySaboteurHandler("happy_path")
    h_happy_empty_hdr.access_log_path = None
    h_happy_empty_hdr.headers = {}  # type: ignore[assignment]
    h_happy_empty_hdr.rfile = io.BytesIO(b"")
    h_happy_empty_hdr.handle_request()
    assert h_happy_empty_hdr.status_codes == [200]

    h500 = DummySaboteurHandler("500")
    h500.do_GET()
    h500.do_POST()
    h500.do_PUT()
    h500.do_DELETE()
    h500.do_PATCH()
    h500.do_OPTIONS()
    h500.do_HEAD()
    assert h500.status_codes == [500] * 7
    assert b"Internal Sabotage" in h500.buffer.getvalue()
    h500.log_message("%s", "ignored")

    h_schema = DummySaboteurHandler("invalid_schema")
    h_schema.handle_request()
    assert h_schema.status_codes == [200]
    assert b"unexpected_type" in h_schema.buffer.getvalue()

    h_unknown = DummySaboteurHandler("unknown_mode")
    h_unknown.handle_request()
    assert h_unknown.status_codes == [400]
    assert b"Unknown Saboteur Mode" in h_unknown.buffer.getvalue()


def test_create_handler_class_and_parse_config() -> None:
    """Verify `create_handler_class` and `parse_config` work without mutating base state."""
    cls = saboteur_server.create_handler_class("invalid_schema")
    assert cls.mode == "invalid_schema"
    assert saboteur_server.SaboteurServer.mode == "500"

    cfg_default = saboteur_server.parse_config([])
    assert cfg_default.mode == "500"
    assert cfg_default.port == 8080

    cfg_custom = saboteur_server.parse_config(["invalid_schema", "9090"])
    assert cfg_custom.mode == "invalid_schema"
    assert cfg_custom.port == 9090


def test_run_server_and_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `run_server` and `main` handle normal execution and `KeyboardInterrupt`."""
    closed: List[bool] = []

    class FakeServer:
        """Mock ThreadedHTTPServer."""

        def __init__(self, addr: Tuple[str, int], handler: object) -> None:
            """Initialize FakeServer."""
            self.addr = addr
            self.handler = handler

        def serve_forever(self) -> None:
            """Raise KeyboardInterrupt to simulate Ctrl+C shutdown."""
            raise KeyboardInterrupt()

        def server_close(self) -> None:
            """Record server_close call."""
            closed.append(True)

    monkeypatch.setattr(saboteur_server, "ThreadedHTTPServer", FakeServer)
    rc = saboteur_server.main(["500", "8081"])
    assert rc == 0
    assert closed == [True]

    class FakeServerNormal(FakeServer):
        """Mock ThreadedHTTPServer that returns normally from serve_forever."""

        def serve_forever(self) -> None:
            """Return immediately."""
            return None

    monkeypatch.setattr(saboteur_server, "ThreadedHTTPServer", FakeServerNormal)
    with mock.patch.object(sys, "argv", ["saboteur_server.py"]):
        assert saboteur_server.main() == 0
