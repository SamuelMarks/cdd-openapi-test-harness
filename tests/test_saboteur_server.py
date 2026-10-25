"""Unit tests for `saboteur_server.py`."""

import email.message
import io
import unittest.mock as mock
from pathlib import Path
from typing import List, Optional, Tuple, Type

import saboteur_server


class DummySaboteurHandler(saboteur_server.SaboteurServer):
    """In-memory harness subclass of `SaboteurServer` avoiding real sockets."""

    def __init__(
        self,
        command: str = "GET",
        path: str = "/v2/pet/1",
        body: bytes = b"",
        mode: str = "500",
        access_log_path: Optional[str] = None,
    ) -> None:
        """Initialize an in-memory request handler without invoking `BaseRequestHandler.__init__`.

        Args:
            command: HTTP verb to simulate.
            path: Request path to simulate.
            body: Request body bytes.
            mode: Saboteur mode to test.
            access_log_path: Optional log file path for `happy_path` mode.
        """
        self.command = command
        self.path = path
        self.mode = mode
        self.access_log_path = access_log_path
        msg = email.message.Message()
        if body:
            msg["Content-Length"] = str(len(body))
        self.headers = msg
        self.rfile = io.BytesIO(body)
        self.response_buf: io.BytesIO = io.BytesIO()
        self.wfile = self.response_buf
        self.status_code: int = 0
        self.sent_headers: List[Tuple[str, str]] = []

    def send_response(self, code: int, message: Optional[str] = None) -> None:
        """Record the HTTP status code.

        Args:
            code: HTTP status code.
            message: Optional status message.
        """
        assert message is None or isinstance(message, str)
        self.status_code = code

    def send_header(self, keyword: str, value: str) -> None:
        """Record an HTTP response header.

        Args:
            keyword: Header name.
            value: Header value.
        """
        self.sent_headers.append((keyword, value))

    def end_headers(self) -> None:
        """No-op end of headers."""
        return None


def test_build_petstore_payload_routes() -> None:
    """Verify `build_petstore_payload` returns valid JSON for all Petstore route patterns."""
    assert b"[" in saboteur_server.build_petstore_payload("GET", "/v2/pet/findByStatus?status=available")
    assert b"available" in saboteur_server.build_petstore_payload("GET", "/v2/store/inventory")
    assert b"placed" in saboteur_server.build_petstore_payload("GET", "/v2/store/order/1")
    assert b"logged_in_session" in saboteur_server.build_petstore_payload("GET", "/v2/user/login")
    assert b"user1" in saboteur_server.build_petstore_payload("GET", "/v2/user/john")
    assert b"KtorIntegrationDog" in saboteur_server.build_petstore_payload("GET", "/v2/pet/1")
    assert b"unknown" in saboteur_server.build_petstore_payload("POST", "/v2/pet/1/uploadImage")


def test_saboteur_handler_modes_and_methods(tmp_path: Path) -> None:
    """Verify `SaboteurServer` handles all HTTP verbs and all sabotage modes."""
    log_file = tmp_path / "access.log"
    h_happy = DummySaboteurHandler(
        command="POST",
        path="/v2/pet",
        body=b'{"name":"doggie"}',
        mode="happy_path",
        access_log_path=str(log_file),
    )
    h_happy.do_POST()
    assert h_happy.status_code == 200
    assert log_file.exists()
    assert "POST /v2/pet HTTP/1.1" in log_file.read_text(encoding="utf-8")

    h_happy_no_log = DummySaboteurHandler(
        command="GET",
        path="/v2/pet/1",
        body=b"",
        mode="happy_path",
        access_log_path=None,
    )
    h_happy_no_log.do_GET()
    assert h_happy_no_log.status_code == 200

    h_zero_len = DummySaboteurHandler(command="PUT", path="/v2/pet", mode="500")
    zero_msg = email.message.Message()
    zero_msg["Content-Length"] = "0"
    h_zero_len.headers = zero_msg
    h_zero_len.do_PUT()
    assert h_zero_len.status_code == 500
    assert b"Internal Sabotage" in h_zero_len.response_buf.getvalue()

    h_schema = DummySaboteurHandler(command="DELETE", path="/v2/pet/1", mode="invalid_schema")
    h_schema.do_DELETE()
    assert h_schema.status_code == 200
    assert b"NOT_AN_INTEGER" in h_schema.response_buf.getvalue()

    h_unknown = DummySaboteurHandler(command="PATCH", path="/v2/pet/1", mode="mystery")
    h_unknown.do_PATCH()
    assert h_unknown.status_code == 400
    assert b"Unknown Saboteur Mode" in h_unknown.response_buf.getvalue()

    h_unknown.do_OPTIONS()
    h_unknown.do_HEAD()
    h_unknown.log_message("%s", "ignored")


def test_config_and_server_lifecycle() -> None:
    """Verify `parse_config`, `create_handler_class`, `run_server`, and `main`."""
    cfg_default = saboteur_server.parse_config([])
    assert cfg_default.mode == "500"
    assert cfg_default.port == 8080
    assert cfg_default.access_log == "java_petstore_access.log"

    cfg_custom = saboteur_server.parse_config(["invalid_schema", "9090", "--access-log", "custom.log"])
    assert cfg_custom.mode == "invalid_schema"
    assert cfg_custom.port == 9090
    assert cfg_custom.access_log == "custom.log"

    cls = saboteur_server.create_handler_class("happy_path", access_log_path="custom.log")
    assert cls.mode == "happy_path"
    assert cls.access_log_path == "custom.log"
    assert saboteur_server.SaboteurServer.mode == "500"

    closed: List[bool] = []

    class FakeServer:
        """Mock ThreadedHTTPServer that raises KeyboardInterrupt on serve_forever."""

        def __init__(self, addr: Tuple[str, int], handler: Type[saboteur_server.SaboteurServer]) -> None:
            """Initialize FakeServer.

            Args:
                addr: Host and port tuple.
                handler: Request handler class.
            """
            self.addr = addr
            self.handler = handler

        def serve_forever(self) -> None:
            """Simulate Ctrl-C interrupt."""
            raise KeyboardInterrupt

        def server_close(self) -> None:
            """Record server close."""
            closed.append(True)

    with mock.patch("saboteur_server.ThreadedHTTPServer", FakeServer):
        assert saboteur_server.main(["500", "8081"]) == 0
    assert closed == [True]

    class FakeServerNormal(FakeServer):
        """Mock ThreadedHTTPServer that returns normally from serve_forever."""

        def serve_forever(self) -> None:
            """Return immediately."""
            return None

    with (
        mock.patch("saboteur_server.ThreadedHTTPServer", FakeServerNormal),
        mock.patch("sys.argv", ["saboteur_server.py"]),
    ):
        assert saboteur_server.main() == 0
