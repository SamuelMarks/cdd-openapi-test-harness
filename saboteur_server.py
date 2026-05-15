#!/usr/bin/env python3
"""
saboteur_server.py

A simple HTTP server designed for Chaos Engineering / Mutation Testing.
It acts as a substitute for the real Petstore server to prove that 
generated SDK tests actually validate responses rather than just "fire and forget".

Modes:
  500: Returns HTTP 500 Internal Server Error for all requests.
       (Proves tests validate HTTP status codes).
  invalid_schema: Returns HTTP 200 OK, but with an invalid JSON payload.
       (Proves tests perform deserialization/schema validation).

Usage:
  python3 saboteur_server.py [500|invalid_schema] [port]
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

class SaboteurServer(BaseHTTPRequestHandler):
    """
    Request handler that intercepts all HTTP requests and returns a sabotaged response
    based on the configured failure mode.
    """
    
    # Static configuration shared across all handler instances
    MODE = '500'

    def handle_request(self):
        """
        Processes the incoming request and returns the sabotaged payload.
        """
        if self.MODE == '500':
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "Internal Sabotage"}')
            
        elif self.MODE == 'invalid_schema':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            # Valid JSON, but definitely fails OpenAPI schema validation for Pet/User/Order
            self.wfile.write(b'{"sabotage": true, "unexpected_type": ["array", "instead", "of", "object"]}')
            
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Unknown Saboteur Mode")

    def do_GET(self):
        """Handle GET requests."""
        self.handle_request()

    def do_POST(self):
        """Handle POST requests."""
        self.handle_request()

    def do_PUT(self):
        """Handle PUT requests."""
        self.handle_request()

    def do_DELETE(self):
        """Handle DELETE requests."""
        self.handle_request()

    def do_PATCH(self):
        """Handle PATCH requests."""
        self.handle_request()
        
    def do_OPTIONS(self):
        """Handle OPTIONS requests."""
        self.handle_request()

    def do_HEAD(self):
        """Handle HEAD requests."""
        self.handle_request()
        
    def log_message(self, format, *args):
        """Suppress default HTTP logging to keep CI logs clean."""
        pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SaboteurServer.MODE = sys.argv[1]
        
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    
    server_address = ('', port)
    httpd = ThreadedHTTPServer(server_address, SaboteurServer)
    
    print(f"Saboteur Server running on port {port} in mode: {SaboteurServer.MODE}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
