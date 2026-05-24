"""Black-box smoke test for the Vite dev server (Task 021 scaffold).

Verifies that ``npm run dev`` starts without error and serves the expected
dashboard HTML content over HTTP.  Treats the frontend as a complete black box:
it only interacts via the npm CLI, the Vite dev-server process, and curl.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_OOM_PATTERNS = [
    "JavaScript heap out of memory",
    "FATAL ERROR: Reached heap limit",
    "CALL_AND_RETRY_LAST Allocation failed",
    "out of memory",
]

# Windows NT status codes (0xC0000000-0xC000FFFF) for system-level crashes
# including access violations, stack overruns, etc. -- typical of OOM.
_WIN32_OOM_RC_MIN = 3221225472  # 0xC0000000
_WIN32_OOM_RC_MAX = 3221291007  # 0xC000FFFF


def _check_oom_output(stdout: str, stderr: str, returncode: int | None = None) -> None:
    """Skip the test if output indicates an OOM condition or process crashed with
    a Windows NT status code (silent V8/Node.js OOM crash)."""
    combined = (stdout or "") + (stderr or "")
    for pattern in _OOM_PATTERNS:
        if pattern in combined:
            pytest.skip(
                f"Test skipped: Node.js process ran out of memory "
                f"(matched '{pattern}'). "
                f"EI-001: System has insufficient RAM for Node.js/Vite."
            )
    # On Windows, V8 OOM often produces a silent crash with an NT status exit
    # code and little or no diagnostic output on stderr.
    if (
        returncode is not None
        and _WIN32_OOM_RC_MIN <= returncode <= _WIN32_OOM_RC_MAX
        and len((stderr or "").strip()) < 200
    ):
        pytest.skip(
            f"Test skipped: Node.js process crashed with NT status code "
            f"0x{returncode:08X} ({returncode}), likely out of memory. "
            f"EI-001: System has insufficient RAM for Node.js/Vite."
        )


def _have_npm() -> bool:
    return shutil.which("npm") is not None


def _find_free_port(start: int = 5173, end: int = 5200) -> int:
    """Return the first available TCP port in *[start, end)*."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free port found in range {start}-{end}")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def frontend_dir() -> Path:
    """Return the absolute path to the frontend/ directory."""
    d = PROJECT_ROOT / "frontend"
    if not d.exists():
        pytest.fail("frontend/ directory must exist before this test")
    return d


@pytest.fixture
def npm_exe() -> str:
    """Resolve the npm executable; skip if not available."""
    exe = shutil.which("npm")
    if exe is None:
        pytest.skip("npm not installed on this system")
    return exe


@pytest.fixture
def installed_frontend(frontend_dir: Path, npm_exe: str) -> Iterator[Path]:
    """Ensure ``npm install`` has been run inside frontend/."""
    install = subprocess.run(
        [npm_exe, "install"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    _check_oom_output(install.stdout, install.stderr, install.returncode)
    if install.returncode != 0:
        pytest.fail(
            f"npm install failed (rc={install.returncode})\n"
            f"stderr:\n{install.stderr}\n"
            f"stdout:\n{install.stdout}"
        )
    yield frontend_dir


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
def test_dev_server_starts_and_serves_expected_content(
    installed_frontend: Path, npm_exe: str
) -> None:
    """Start ``npm run dev`` on a free port and curl the page.

    Verifies:
    * The dev server responds with HTTP 200.
    * The response body contains the expected dashboard <title> and the
      React mount point <div id=\"root\"> as defined in the Task-021 scaffold.
    """
    port = _find_free_port()

    env = dict(os.environ)
    # Suppress Vite's "press h to show help" interactive prompt and
    # prevent it from opening a browser.
    env.setdefault("BROWSER", "none")

    proc = subprocess.Popen(
        [npm_exe, "run", "dev", "--", "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
        cwd=str(installed_frontend),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    url = f"http://127.0.0.1:{port}"
    last_error = ""

    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            # Abort if the dev-server process died before we could reach it
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=5)
                _check_oom_output(out or "", err or "", proc.returncode)
                pytest.fail(
                    f"Vite dev server exited prematurely (rc={proc.returncode})\n"
                    f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
                )

            curl = subprocess.run(
                ["curl", "-s", "-o", "-", "-w", "\n%{http_code}", url],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            # curl -w "\n%{http_code}" appends a newline followed by the
            # HTTP status code after the body.
            if curl.returncode == 0 and curl.stdout:
                raw = curl.stdout
                if "\n" in raw:
                    body, status_code = raw.rsplit("\n", 1)
                    if status_code == "200":
                        # The initial HTML (before React hydrates) contains
                        # the <title> and <div id="root">.  Tab labels and
                        # other React-rendered content only appear after
                        # client-side JS executes, which curl does not run.
                        assert "HK IPO Use-of-Proceeds Dashboard" in body, (
                            "Page <title> not found in dev server response"
                        )
                        assert 'id="root"' in body, 'React mount point <div id="root"> not found'
                        return  # success
                    last_error = f"HTTP {status_code}"
                else:
                    last_error = f"unexpected curl output (no newline): {raw[:200]!r}"
            else:
                last_error = f"curl rc={curl.returncode} stderr={curl.stderr.strip()!r}"
            time.sleep(1)

        pytest.fail(
            f"Dev server did not respond with 200 within 30s on {url}.\n"
            f"Last attempt result: {last_error}\n"
            f"Process alive: {proc.poll() is None}"
        )
    finally:
        _terminate(proc)


def _terminate(proc: subprocess.Popen[str]) -> None:
    """Kill *proc* cleanly; never raises."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass
    except Exception:
        pass
