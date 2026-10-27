"""Offline unit tests for scripts/smoke_remote.py."""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scripts.smoke_remote import check_endpoint, main, verify_root, wait_for_health


class MockHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler simulating Streamlit endpoints."""

    def log_message(self, format: str, *args) -> None:
        # Silence standard HTTP server logging during tests
        pass

    def do_GET(self) -> None:
        if self.path == "/_stcore/health":
            if getattr(self.server, "simulate_unhealthy", False):
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"service unavailable")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
        elif self.path in ("/", ""):
            if getattr(self.server, "simulate_root_error", False):
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Internal Server Error")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<!DOCTYPE html><html><body>Streamlit app</body></html>"
                )
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


@pytest.fixture
def mock_server() -> Generator[tuple[HTTPServer, str]]:
    """Start an in-process local HTTP server on an ephemeral port."""
    server = HTTPServer(("127.0.0.1", 0), MockHandler)
    server.simulate_unhealthy = False  # type: ignore[attr-defined]
    server.simulate_root_error = False  # type: ignore[attr-defined]
    host, port = server.server_address
    server_url = f"http://{host}:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server, server_url
    finally:
        server.shutdown()
        server.server_close()


def test_check_endpoint_health_ok(mock_server: tuple[HTTPServer, str]):
    _, server_url = mock_server
    ok, status, msg = check_endpoint(
        f"{server_url}/_stcore/health",
        expected_status=200,
        expected_body_substr="ok",
    )
    assert ok is True
    assert status == 200
    assert msg == "OK"


def test_check_endpoint_health_unhealthy(mock_server: tuple[HTTPServer, str]):
    server, server_url = mock_server
    server.simulate_unhealthy = True  # type: ignore[attr-defined]

    ok, status, msg = check_endpoint(
        f"{server_url}/_stcore/health",
        expected_status=200,
        expected_body_substr="ok",
    )
    assert ok is False
    assert status == 503
    assert "HTTP Error 503" in msg


def test_check_endpoint_body_mismatch(mock_server: tuple[HTTPServer, str]):
    _, server_url = mock_server
    ok, status, msg = check_endpoint(
        f"{server_url}/_stcore/health",
        expected_status=200,
        expected_body_substr="unexpected_content_string",
    )
    assert ok is False
    assert status == 200
    assert "Expected body to contain" in msg


def test_check_endpoint_connection_refused():
    ok, status, msg = check_endpoint(
        "http://127.0.0.1:1/nonexistent", timeout_per_request=0.5
    )
    assert ok is False
    assert status == 0
    assert "URL Error" in msg or "Request error" in msg


def test_wait_for_health_success(mock_server: tuple[HTTPServer, str]):
    _, server_url = mock_server
    success = wait_for_health(server_url, max_wait_seconds=5.0, poll_interval=0.1)
    assert success is True


def test_wait_for_health_timeout(mock_server: tuple[HTTPServer, str]):
    server, server_url = mock_server
    server.simulate_unhealthy = True  # type: ignore[attr-defined]
    success = wait_for_health(server_url, max_wait_seconds=0.2, poll_interval=0.05)
    assert success is False


def test_verify_root_success(mock_server: tuple[HTTPServer, str]):
    _, server_url = mock_server
    assert verify_root(server_url) is True


def test_verify_root_failure(mock_server: tuple[HTTPServer, str]):
    server, server_url = mock_server
    server.simulate_root_error = True  # type: ignore[attr-defined]
    assert verify_root(server_url) is False


def test_main_cli_success(mock_server: tuple[HTTPServer, str]):
    _, server_url = mock_server
    exit_code = main([server_url, "--timeout", "5.0"])
    assert exit_code == 0


def test_main_cli_health_failure(mock_server: tuple[HTTPServer, str]):
    server, server_url = mock_server
    server.simulate_unhealthy = True  # type: ignore[attr-defined]
    exit_code = main([server_url, "--timeout", "0.2"])
    assert exit_code == 1


def test_main_cli_root_failure(mock_server: tuple[HTTPServer, str]):
    server, server_url = mock_server
    server.simulate_root_error = True  # type: ignore[attr-defined]
    exit_code = main([server_url, "--timeout", "5.0"])
    assert exit_code == 1
