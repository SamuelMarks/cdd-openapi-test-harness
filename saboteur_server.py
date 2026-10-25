#!/usr/bin/env python3
"""Saboteur chaos-engineering HTTP server (`saboteur_server.py`).

A lightweight HTTP server designed for Chaos Engineering and Mutation Testing.
It acts as a substitute for the real Petstore server to prove that the generated
SDKs' test suites actually validate HTTP status codes and JSON response schemas,
and also provides a deterministic happy-path Petstore mock server.

Modes:
  - `happy_path`: Returns valid Petstore JSON payloads with HTTP 200 and logs requests.
  - `500`: Returns HTTP 500 Internal Server Error with an error JSON payload.
  - `invalid_schema`: Returns HTTP 200 OK with a corrupted JSON payload violating schema types.
"""

import argparse
import email.message
import http.server
import io
import json
import socketserver
import sys
from dataclasses import dataclass
from typing import Optional, Sequence, Type
from urllib.parse import urlparse

from harness.errors import JSONDict


@dataclass(frozen=True)
class SaboteurConfig:
    """Configuration parameters for the Saboteur HTTP server.

    Attributes:
        mode: Sabotage mode ('happy_path', '500', or 'invalid_schema').
        port: TCP port to bind the HTTP server on.
        access_log: Optional filesystem path where `happy_path` requests are logged.
    """

    mode: str = "500"
    port: int = 8080
    access_log: Optional[str] = "java_petstore_access.log"


def build_petstore_payload(method: str, req_path: str) -> bytes:
    """Construct a valid Petstore JSON response payload for happy-path testing.

    Args:
        method: HTTP verb (e.g., 'GET', 'POST', 'DELETE').
        req_path: Full request path including optional query string.

    Returns:
        bytes: UTF-8 encoded JSON response body matching the Petstore schema.
    """
    parsed = urlparse(req_path)
    path = parsed.path

    pet_obj: JSONDict = {
        "id": 1,
        "category": {"id": 1, "name": "Dogs"},
        "name": "KtorIntegrationDog",
        "photoUrls": ["https://example.com/dog.jpg"],
        "tags": [{"id": 1, "name": "tag1"}],
        "status": "available",
    }

    if path.endswith(("/pet/findByStatus", "/pet/findByTags")):
        return json.dumps([pet_obj]).encode("utf-8")
    if path.endswith("/store/inventory"):
        return json.dumps({"available": 1, "sold": 0}).encode("utf-8")
    if "/store/order" in path:
        return json.dumps(
            {
                "id": 1,
                "petId": 1,
                "quantity": 1,
                "shipDate": "2026-10-24T00:00:00Z",
                "status": "placed",
                "complete": True,
            }
        ).encode("utf-8")
    if path.endswith("/user/login"):
        return json.dumps("logged_in_session").encode("utf-8")
    if "/user/" in path and method == "GET":
        return json.dumps(
            {
                "id": 1,
                "username": "user1",
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "password": "secret",
                "phone": "123456",
                "userStatus": 1,
            }
        ).encode("utf-8")
    if "/pet" in path and not path.endswith("/uploadImage"):
        return json.dumps(pet_obj).encode("utf-8")
    return json.dumps({"code": 200, "type": "unknown", "message": "ok"}).encode("utf-8")


class SaboteurServer(http.server.BaseHTTPRequestHandler):
    """HTTP request handler that returns happy-path or sabotaged responses based on `mode`.

    Attributes:
        mode: Active server mode ('happy_path', '500', or 'invalid_schema').
        access_log_path: File path to append Nginx-style access logs in `happy_path` mode.
    """

    mode: str = "500"
    access_log_path: Optional[str] = "java_petstore_access.log"
    command: str = "GET"
    path: str = "/"
    headers: email.message.Message = email.message.Message()
    rfile: io.BufferedIOBase = io.BytesIO(b"")

    def handle_request(self) -> None:
        """Process any incoming HTTP method according to the active sabotage mode."""
        content_length_raw = self.headers.get("Content-Length") if self.headers is not None else None
        if content_length_raw:
            length = int(content_length_raw)
            if length > 0 and self.rfile is not None:
                self.rfile.read(length)

        method = self.command or "GET"
        req_path = self.path or "/"

        if self.mode == "happy_path":
            payload = build_petstore_payload(method, req_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            if self.access_log_path:
                log_line = (
                    f'127.0.0.1 - - [24/Oct/2026:00:00:00 +0000] "{method} {req_path} HTTP/1.1" 200 {len(payload)}'
                )
                with open(self.access_log_path, "a", encoding="utf-8") as log_file:
                    print(log_line, file=log_file)

        elif self.mode == "500":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code": 500, "type": "error", "message": "Internal Sabotage"}')

        elif self.mode == "invalid_schema":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = (
                b'{"id": "NOT_AN_INTEGER", "name": 12345, "photoUrls": "NOT_AN_ARRAY", '
                b'"status": {"unexpected_type": true}, "sabotage": true}'
            )
            self.wfile.write(payload)

        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Unknown Saboteur Mode")

    def do_GET(self) -> None:
        """Handle HTTP GET requests."""
        self.handle_request()

    def do_POST(self) -> None:
        """Handle HTTP POST requests."""
        self.handle_request()

    def do_PUT(self) -> None:
        """Handle HTTP PUT requests."""
        self.handle_request()

    def do_DELETE(self) -> None:
        """Handle HTTP DELETE requests."""
        self.handle_request()

    def do_PATCH(self) -> None:
        """Handle HTTP PATCH requests."""
        self.handle_request()

    def do_OPTIONS(self) -> None:
        """Handle HTTP OPTIONS requests."""
        self.handle_request()

    def do_HEAD(self) -> None:
        """Handle HTTP HEAD requests."""
        self.handle_request()

    def log_message(self, _format: str, *_args: str) -> None:
        """Suppress noisy default HTTP server logging during chaos tests.

        Args:
            _format: Format string for the log message.
            *_args: Format arguments.
        """
        return None


def create_handler_class(
    mode: str,
    access_log_path: Optional[str] = "java_petstore_access.log",
) -> Type[SaboteurServer]:
    """Create a dedicated `SaboteurServer` subclass bound to the specified mode.

    Args:
        mode: Sabotage mode ('happy_path', '500', or 'invalid_schema').
        access_log_path: Optional access log output path for `happy_path` mode.

    Returns:
        Type[SaboteurServer]: Configured request handler class without mutating base class state.
    """

    class ConfiguredSaboteurHandler(SaboteurServer):
        """Request handler bound to a specific sabotage mode."""

        pass

    ConfiguredSaboteurHandler.mode = mode
    ConfiguredSaboteurHandler.access_log_path = access_log_path
    return ConfiguredSaboteurHandler


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server with `allow_reuse_address` enabled."""

    allow_reuse_address = True


def parse_config(argv: Optional[Sequence[str]] = None) -> SaboteurConfig:
    """Parse command-line arguments into a `SaboteurConfig` instance.

    Args:
        argv: Optional sequence of command-line arguments (excluding program name).

    Returns:
        SaboteurConfig: Parsed server configuration.
    """
    parser = argparse.ArgumentParser(description="Saboteur chaos-engineering HTTP server.")
    parser.add_argument(
        "mode",
        nargs="?",
        default="500",
        help="Sabotage mode ('happy_path', '500', or 'invalid_schema').",
    )
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=8080,
        help="TCP port to listen on (default: 8080).",
    )
    parser.add_argument(
        "--access-log",
        default="java_petstore_access.log",
        help="Access log path for happy_path mode (default: java_petstore_access.log).",
    )
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    return SaboteurConfig(mode=parsed.mode, port=parsed.port, access_log=parsed.access_log)


def run_server(config: SaboteurConfig) -> None:
    """Start the Saboteur HTTP server and serve until interrupted.

    Args:
        config: Saboteur server configuration.
    """
    handler_cls = create_handler_class(config.mode, access_log_path=config.access_log)
    server = ThreadedHTTPServer(("0.0.0.0", config.port), handler_cls)
    print(f"Saboteur Server running in '{config.mode}' mode on port {config.port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for the Saboteur HTTP server.

    Args:
        argv: Optional sequence of command-line arguments.

    Returns:
        int: Exit status code (0 on clean shutdown).
    """
    config = parse_config(argv)
    run_server(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
