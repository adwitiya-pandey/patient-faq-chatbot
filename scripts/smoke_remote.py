"""Smoke test a deployed Streamlit container app on Azure or local.

Checks:
1. /_stcore/health returns HTTP 200 with body 'ok'.
2. / returns HTTP 200.

Retries up to timeout seconds (default 90s) to handle container cold starts.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request


def check_endpoint(
    url: str,
    expected_status: int = 200,
    expected_body_substr: str | None = None,
    timeout_per_request: float = 10.0,
) -> tuple[bool, int, str]:
    """Perform a single HTTP GET request to check status and body."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PatientFAQBot-SmokeTest/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_per_request) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            if status != expected_status:
                return False, status, f"Expected status {expected_status}, got {status}"
            if expected_body_substr and expected_body_substr not in body:
                return (
                    False,
                    status,
                    f"Expected body to contain {expected_body_substr!r}, got {body[:100]!r}",
                )
            return True, status, "OK"
    except urllib.error.HTTPError as err:
        return False, err.code, f"HTTP Error {err.code}: {err.reason}"
    except urllib.error.URLError as err:
        return False, 0, f"URL Error: {err.reason}"
    except (TimeoutError, OSError) as err:
        return False, 0, f"Request error: {err}"


def wait_for_health(
    base_url: str,
    max_wait_seconds: float = 90.0,
    poll_interval: float = 3.0,
) -> bool:
    """Poll /_stcore/health until healthy or timeout exceeded."""
    health_url = f"{base_url.rstrip('/')}/_stcore/health"
    start_time = time.time()
    attempt = 1

    print(
        f"Polling health endpoint: {health_url} (timeout: {max_wait_seconds:.0f}s)..."
    )

    while True:
        elapsed = time.time() - start_time
        remaining = max(1.0, max_wait_seconds - elapsed)
        ok, status, message = check_endpoint(
            health_url,
            expected_status=200,
            expected_body_substr="ok",
            timeout_per_request=min(10.0, remaining),
        )

        if ok:
            print(
                f"[{elapsed:.1f}s] Health check PASSED on attempt {attempt} (HTTP {status})."
            )
            return True

        print(
            f"[{elapsed:.1f}s] Attempt {attempt} waiting for cold start... ({message})"
        )

        if elapsed >= max_wait_seconds:
            print(f"ERROR: Health check timed out after {elapsed:.1f}s.")
            return False

        time.sleep(poll_interval)
        attempt += 1


def verify_root(base_url: str, timeout: float = 10.0) -> bool:
    """Verify that root URL returns HTTP 200."""
    root_url = base_url.rstrip("/") + "/"
    print(f"Checking root page: {root_url}...")
    ok, status, message = check_endpoint(
        root_url, expected_status=200, timeout_per_request=timeout
    )
    if ok:
        print(f"Root page check PASSED (HTTP {status}).")
        return True
    print(f"ERROR: Root page check FAILED: {message}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test a deployed Streamlit container app."
    )
    parser.add_argument("url", help="Base URL of the deployed application")
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Max wait time in seconds for healthcheck (default: 90.0)",
    )
    args = parser.parse_args(argv)

    base_url = args.url.strip()
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"

    print(f"Starting remote smoke test for: {base_url}")
    if not wait_for_health(base_url, max_wait_seconds=args.timeout):
        return 1

    if not verify_root(base_url):
        return 1

    print("\nRemote smoke test PASSED successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
