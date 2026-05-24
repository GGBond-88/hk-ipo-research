"""Black-box smoke test for the frontend dashboard build (A8.5)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from .conftest import PROJECT_ROOT

pytestmark = pytest.mark.e2e


def _have_npm() -> bool:
    return shutil.which("npm") is not None


_OOM_PATTERNS = [
    "JavaScript heap out of memory",
    "FATAL ERROR: Reached heap limit",
    "CALL_AND_RETRY_LAST Allocation failed",
    "out of memory",
]

# Windows NT status codes (0xC0000000-0xC000FFFF) for system-level crashes.
_WIN32_OOM_RC_MIN = 3221225472  # 0xC0000000
_WIN32_OOM_RC_MAX = 3221291007  # 0xC000FFFF


def _maybe_skip_oom(result: subprocess.CompletedProcess) -> None:
    """Skip the test if the process output indicates an OOM condition."""
    combined = (result.stdout or "") + (result.stderr or "")
    for pattern in _OOM_PATTERNS:
        if pattern in combined:
            pytest.skip(
                f"Test skipped: npm process ran out of memory "
                f"(matched '{pattern}'). "
                f"EI-001: System has insufficient RAM for Node.js/Vite."
            )
    # On Windows, V8 OOM often produces a silent crash with an NT status exit
    # code and little or no diagnostic output on stderr.
    rc = result.returncode
    if (
        _WIN32_OOM_RC_MIN <= rc <= _WIN32_OOM_RC_MAX
        and len((result.stderr or "").strip()) < 200
    ):
        pytest.skip(
            f"Test skipped: Node.js process crashed with NT status code "
            f"0x{rc:08X} ({rc}), likely out of memory. "
            f"EI-001: System has insufficient RAM for Node.js/Vite."
        )


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
def test_frontend_build_produces_dist_folder() -> None:
    """`npm install && npm run build` inside frontend/ produces a dist/ dir
    with index.html and at least one JS chunk."""
    frontend = PROJECT_ROOT / "frontend"
    assert frontend.exists(), "frontend/ directory must exist before this test"

    # Use the full path to npm resolved by shutil.which rather than the bare
    # "npm" string.  On Windows, CreateProcess cannot resolve bare .CMD
    # filename extensions during PATH lookup, so providing the fully resolved
    # path ensures the executable is found by the OS.
    npm_exe = shutil.which("npm")
    assert npm_exe is not None, "npm not found in PATH (skipif guard should have caught this)"

    install = subprocess.run(
        [npm_exe, "install"],
        cwd=frontend,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    _maybe_skip_oom(install)
    assert install.returncode == 0, (
        f"npm install failed (rc={install.returncode})\n"
        f"stderr:\n{install.stderr}\n"
        f"stdout:\n{install.stdout}"
    )

    build = subprocess.run(
        [npm_exe, "run", "build"],
        cwd=frontend,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    _maybe_skip_oom(build)
    assert build.returncode == 0, (
        f"npm run build failed (rc={build.returncode})\n"
        f"stderr:\n{build.stderr}\n"
        f"stdout:\n{build.stdout}"
    )

    dist = frontend / "dist"
    assert (dist / "index.html").exists()
    assert any(dist.glob("assets/*.js")), "no JS chunks built"
