#!/usr/bin/env python3
"""Saboteur chaos-engineering HTTP server (`saboteur_server.py`).

A lightweight HTTP server designed for Chaos Engineering and Mutation Testing.
It acts as a substitute for the real Petstore server to prove that generated
SDK tests actually validate HTTP status codes and response schemas rather than
merely firing requests and ignoring responses.

Modes:
  happy_path: Returns schema-compliant HTTP 200 Petstore JSON responses and logs requests.
  500: Returns HTTP 500 Internal Server Error for all requests.
  invalid_schema: Returns HTTP 200 OK with an invalid JSON payload.

Usage:
  python3 saboteur_server.py [happy_path|500|invalid_schema] [port]
"""

import json
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Dict, Optional, Sequence, Type


@dataclass(frozen=True)
class SaboteurConfig:
    """Configuration for the Saboteur chaos server.

    Attributes:
        mode: Server mode ('happy_path', '500', or 'invalid_schema').
        port: TCP port to bind the HTTP server to.
    """

    mode: str = "500"
    port: int = 8080


def build_petstore_payload(method: str, path: str) -> bytes:
    """Build a schema-valid JSON response payload for a Petstore endpoint.

    Args:
        method: Uppercase HTTP method (e.g., 'GET', 'POST').
        path: Request path including optional query string.

    Returns:
        bytes: UTF-8 encoded JSON response body matching the Petstore schema.
    """
    clean_path = path.split("?", 1)[0].rstrip("/")
    pet_obj: Dict[str, object] = {
        "id": 998877665,
        "name": "KtorIntegrationDog",
        "photoUrls": ["http://example.com/photo.jpg"],
        "status": "available",
        "category": {"id": 1, "name": "Dogs"},
        "tags": [{"id": 1, "name": "tag1"}],
    }
    if clean_path.endswith("/findByStatus") or clean_path.endswith("/findByTags"):
        return json.dumps([pet_obj]).encode("utf-8")
    if clean_path.endswith("/store/inventory"):
        return json.dumps({"available": 10, "pending": 2, "sold": 5}).encode("utf-8")
    if "/store/order" in clean_path and method in ("GET", "POST"):
        return json.dumps(
            {
                "id": 1,
                "petId": 998877665,
                "quantity": 1,
                "shipDate": "2026-01-01T00:00:00Z",
                "status": "placed",
                "complete": True,
            }
        ).encode("utf-8")
    if clean_path.endswith("/user/login"):
        return json.dumps("logged_in_session").encode("utf-8")
    if "/user" in clean_path and not clean_path.endswith("/logout") and method in ("GET", "POST"):
        return json.dumps(
            {
                "id": 1,
                "username": "user1",
                "firstName": "First",
                "lastName": "Last",
                "email": "user@example.com",
                "password": "secret",
                "phone": "123456",
                "userStatus": 1,
            }
        ).encode("utf-8")
    if "/pet" in clean_path and not clean_path.endswith("/uploadImage") and method in ("GET", "POST", "PUT"):
        return json.dumps(pet_obj).encode("utf-8")
    return json.dumps({"code": 200, "type": "unknown", "message": "ok"}).encode("utf-8")


class SaboteurServer(BaseHTTPRequestHandler):
    """Request handler that intercepts all HTTP requests and returns a configured response.

    Attributes:
        mode: Active server mode ('happy_path', '500', or 'invalid_schema').
        access_log_path: Optional file path to append NCSA access log lines in happy_path mode.
    """

    mode: str = "500"
    access_log_path: Optional[str] = "java_petstore_access.log"

    def _drain_request_body(self) -> None:
        """Read and discard any incoming request body so the client socket is not reset."""
        headers = getattr(self, "headers", None)
        rfile = getattr(self, "rfile", None)
        if headers is not None and rfile is not None:
            length_str = headers.get("Content-Length")
            if length_str and length_str.isdigit():
                length = int(length_str)
                if length > 0:
                    rfile.read(length)

    def handle_request(self) -> None:
        """Process the incoming HTTP request and write the configured payload."""
        self._drain_request_body()
        if self.mode == "happy_path":
            method = getattr(self, "command", "GET") or "GET"
            req_path = getattr(self, "path", "/") or "/"
            payload = build_petstore_payload(method, req_path)
            if self.access_log_path:
                with open(self.access_log_path, "a", encoding="utf-8") as log_f:
                    log_f.write(
                        f'127.0.0.1 - - [24/Oct/2026:00:00:00 +0000] "{method} {req_path} HTTP/1.1" 200 {len(payload)}\n'
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        elif self.mode == "500":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Internal Sabotage"}')
        elif self.mode == "invalid_schema":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"sabotage": true, "unexpected_type": ["array", "instead", "of", "object"]}')
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

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default HTTP logging to keep CI logs clean.

        Args:
            format: Format string for the log message.
            *args: Format arguments for the log message.
        """
        return None


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server handling each request in a separate thread."""

    allow_reuse_address = True
    daemon_threads = True


def create_handler_class(mode: str) -> Type[SaboteurServer]:
    """Create a SaboteurServer handler subclass bound to a specific sabotage mode.

    Args:
        mode: Sabotage mode ('500' or 'invalid_schema').

    Returns:
        Type[SaboteurServer]: Configured request handler class without mutating global state.
    """

    class ConfiguredSaboteurHandler(SaboteurServer):
        """Request handler bound to a specific sabotage mode."""

    ConfiguredSaboteurHandler.mode = mode
    return ConfiguredSaboteurHandler


def parse_config(argv: Optional[Sequence[str]] = None) -> SaboteurConfig:
    """Parse CLI arguments into an immutable SaboteurConfig instance.

    Args:
        argv: Command-line arguments (excluding program name). Defaults to `sys.argv[1:]`.

    Returns:
        SaboteurConfig: Parsed mode and port configuration.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    mode = args[0] if len(args) > 0 else "500"
    port = int(args[1]) if len(args) > 1 else 8080
    return SaboteurConfig(mode=mode, port=port)


def run_server(config: SaboteurConfig) -> None:
    """Start and run the ThreadedHTTPServer until interrupted.

    Args:
        config: Saboteur server configuration specifying mode and port.
    """
    handler_cls = create_handler_class(config.mode)
    httpd = ThreadedHTTPServer(("", config.port), handler_cls)
    print(f"Saboteur Server running on port {config.port} in mode: {config.mode}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for `saboteur_server.py`.

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
