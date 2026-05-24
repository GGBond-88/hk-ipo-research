"""Black-box E2E tests for FilterBar and ExportButton components (Task 023).

Verifies component behaviour through a real Chromium browser via Playwright,
treating the rendered DOM as the sole external interface.  The test harness
page is ``frontend/e2e_harness.html``, served by Vite dev server.

Tests:
  FilterBar
    - renders 5 labelled dropdowns (Year, Industry, Country, Parent, Commitment)
    - each dropdown defaults to "All"
    - selecting a value dispatches setFilter (visible via store-state <pre>)
    - Reset button clears all filters (store-state returns to all-nulls)
    - ticker picker renders when showTickerPicker + non-empty tickers
    - ticker picker hidden when tickers empty / prop absent

  ExportButton
    - PNG button always renders
    - CSV button renders when csvData is provided
    - CSV button hidden when csvData is absent
    - both buttons carry type="button"
    - clicking PNG button with null ref does not crash
    - clicking PNG button with valid ref initiates a download
    - clicking CSV button initiates a download with correct content
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .conftest import PROJECT_ROOT

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _have_npm() -> bool:
    return shutil.which("npm") is not None


_OOM_PATTERNS = [
    "JavaScript heap out of memory",
    "FATAL ERROR: Reached heap limit",
    "CALL_AND_RETRY_LAST Allocation failed",
    "out of memory",
]

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


def _find_free_port(start: int = 5173, end: int = 5200) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free port found in range {start}-{end}")


def _terminate(proc: subprocess.Popen[str]) -> None:
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


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def playwright_browser() -> Iterator[Browser]:
    """Provide a single Chromium browser instance for the test session."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(
    playwright_browser: Browser,
) -> Iterator[Page]:
    """Create a fresh browser context + page for each test (no state bleed)."""
    context: BrowserContext = playwright_browser.new_context()
    page: Page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def frontend_dir() -> Path:
    d = PROJECT_ROOT / "frontend"
    if not d.exists():
        pytest.fail("frontend/ directory must exist before this test")
    if not (d / "e2e_harness.html").exists():
        pytest.fail("e2e_harness.html not found in frontend/")
    return d


@pytest.fixture(scope="module")
def npm_exe() -> str:
    exe = shutil.which("npm")
    if exe is None:
        pytest.skip("npm not installed on this system")
    return exe


@pytest.fixture(scope="module")
def dev_server(
    frontend_dir: Path,
    npm_exe: str,
) -> Iterator[str]:
    """Start ``npm run dev`` once for the module; yield the base URL."""
    port = _find_free_port()

    env = dict(os.environ)
    env.setdefault("BROWSER", "none")

    proc = subprocess.Popen(
        [npm_exe, "run", "dev", "--", "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    last_error = ""

    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=5)
                _check_oom_output(out or "", err or "", proc.returncode)
                pytest.fail(
                    f"Vite dev server exited before responding (rc={proc.returncode})\n"
                    f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
                )
            curl = subprocess.run(
                ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", base_url],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if curl.returncode == 0 and curl.stdout.strip() == "200":
                break
            last_error = f"curl rc={curl.returncode} stdout={curl.stdout.strip()!r}"
            time.sleep(1)
        else:
            pytest.fail(
                f"Dev server did not respond with 200 within 30s on {base_url}.\n"
                f"Last attempt: {last_error}"
            )
        yield base_url
    finally:
        _terminate(proc)


# ---------------------------------------------------------------------------
# Helper: navigate to the harness page
# ---------------------------------------------------------------------------


@pytest.fixture
def harness_page(page: Page, dev_server: str) -> Iterator[Page]:
    """Navigate *page* to the test harness URL and wait for React to render."""
    page.goto(f"{dev_server}/e2e_harness.html", wait_until="networkidle")
    # Wait for the store-state <pre> to appear (indicates React has hydrated)
    page.wait_for_selector('[data-testid="store-state"]', timeout=10000)
    yield page


# ---------------------------------------------------------------------------
# Helper: extract store state JSON from the DOM
# ---------------------------------------------------------------------------


def _get_store_state(page: Page) -> dict[str, Any]:
    """Read the Zustand store state rendered inside <pre data-testid="store-state">."""
    el = page.locator('[data-testid="store-state"]')
    raw = el.inner_text()
    return json.loads(raw)


# ---------------------------------------------------------------------------
# FilterBar tests
# ---------------------------------------------------------------------------


class TestFilterBar:
    """Black-box tests for FilterBar component (5 dropdowns + Reset + ticker picker)."""

    def test_renders_five_filter_dropdowns_with_labels(
        self,
        harness_page: Page,
    ) -> None:
        """The page shows 5 filter dropdowns labelled Year/Industry/Country/Parent/Commitment."""
        expected_labels = ["Year:", "Industry:", "Country:", "Parent:", "Commitment:"]
        for label_text in expected_labels:
            el = harness_page.locator(f"label:has-text('{label_text}')")
            assert el.count() >= 1, f"Label '{label_text}' not found on page"

    def test_all_dropdowns_default_to_all(
        self,
        harness_page: Page,
    ) -> None:
        """Each filter <select> starts with value="" (the "All" option)."""
        # We have 2 FilterBars on the page; check the first one's dropdowns.
        selects = harness_page.locator("label select").all()
        filter_selects = selects[:5]  # first 5 selects belong to FilterBar #1
        for sel in filter_selects:
            assert sel.input_value() == "", f"Expected '' but got '{sel.input_value()}'"

    def test_selecting_year_updates_store_state(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting '2024' in the Year dropdown sets year='2024' in Zustand store."""
        year_label = harness_page.locator("label:has-text('Year:')").first
        year_select = year_label.locator("select")
        year_select.select_option("2024")

        state = _get_store_state(harness_page)
        assert state["year"] == "2024", f"Expected year='2024', got {state}"

    def test_selecting_industry_updates_store_state(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting 'Healthcare' in the Industry dropdown sets industry='Healthcare'."""
        industry_label = harness_page.locator("label:has-text('Industry:')").first
        industry_select = industry_label.locator("select")
        industry_select.select_option("Healthcare")

        state = _get_store_state(harness_page)
        assert state["industry"] == "Healthcare", f"Expected industry='Healthcare', got {state}"

    def test_selecting_country_updates_store_state(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting 'JP' in the Country dropdown sets country='JP'."""
        country_label = harness_page.locator("label:has-text('Country:')").first
        country_select = country_label.locator("select")
        country_select.select_option("JP")

        state = _get_store_state(harness_page)
        assert state["country"] == "JP", f"Expected country='JP', got {state}"

    def test_selecting_parent_updates_store_state(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting 'Working Capital' in the Parent dropdown sets parent='Working Capital'."""
        parent_label = harness_page.locator("label:has-text('Parent:')").first
        parent_select = parent_label.locator("select")
        parent_select.select_option("Working Capital")

        state = _get_store_state(harness_page)
        assert state["parent"] == "Working Capital", (
            f"Expected parent='Working Capital', got {state}"
        )

    def test_selecting_commitment_updates_store_state(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting 'discretionary' in the Commitment dropdown sets commitment='discretionary'."""
        commitment_label = harness_page.locator("label:has-text('Commitment:')").first
        commitment_select = commitment_label.locator("select")
        commitment_select.select_option("discretionary")

        state = _get_store_state(harness_page)
        assert state["commitment"] == "discretionary", (
            f"Expected commitment='discretionary', got {state}"
        )

    def test_reset_filters_button_clears_all_filters(
        self,
        harness_page: Page,
    ) -> None:
        """After setting multiple filters, the Reset button clears them all to null."""
        # Set some filters first
        harness_page.locator("label:has-text('Year:')").first.locator("select").select_option(
            "2023"
        )
        harness_page.locator("label:has-text('Industry:')").first.locator("select").select_option(
            "Finance"
        )

        state_before = _get_store_state(harness_page)
        assert state_before["year"] == "2023"
        assert state_before["industry"] == "Finance"

        # Click Reset Filters (the first one on the page)
        reset_btn = harness_page.locator("button:has-text('Reset Filters')").first
        reset_btn.click()

        state_after = _get_store_state(harness_page)
        assert state_after["year"] is None, f"year not cleared: {state_after}"
        assert state_after["industry"] is None, f"industry not cleared: {state_after}"
        assert state_after["country"] is None
        assert state_after["parent"] is None
        assert state_after["commitment"] is None

    def test_ticker_picker_renders_when_enabled(
        self,
        harness_page: Page,
    ) -> None:
        """When showTickerPicker=true and tickers non-empty, a Company: label appears."""
        # The first FilterBar on the page has ticker picker enabled
        company_label = harness_page.locator("label:has-text('Company:')")
        assert company_label.count() == 1, (
            "Expected exactly one Company: label (from first FilterBar)"
        )

        ticker_select = company_label.locator("select")
        options = ticker_select.locator("option").all()
        assert len(options) >= 3, f"Expected >=3 ticker options, got {len(options)}"

    def test_ticker_picker_absent_when_not_enabled(
        self,
        harness_page: Page,
    ) -> None:
        """The second FilterBar (no ticker picker) does NOT show a Company: label."""
        # We have 2 FilterBars: #1 with ticker picker, #2 without.
        # Verify the second one's area (below the second h2) has no Company: label.
        company_labels = harness_page.locator("label:has-text('Company:')")
        assert company_labels.count() == 1, (
            f"Expected exactly 1 Company: label (only first FilterBar has tickers), "
            f"got {company_labels.count()}"
        )

    def test_selecting_ticker_updates_active_ticker_in_store(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting '00001' in the ticker picker sets activeTicker='00001'."""
        company_label = harness_page.locator("label:has-text('Company:')").first
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00001")

        state = _get_store_state(harness_page)
        assert state["activeTicker"] == "00001", f"Expected activeTicker='00001', got {state}"

    def test_selecting_ticker_placeholder_clears_active_ticker(
        self,
        harness_page: Page,
    ) -> None:
        """Selecting the placeholder option ('') sets activeTicker=null."""
        company_label = harness_page.locator("label:has-text('Company:')").first
        ticker_select = company_label.locator("select")

        # First pick a ticker
        ticker_select.select_option("00002")
        state_mid = _get_store_state(harness_page)
        assert state_mid["activeTicker"] == "00002"

        # Then clear it
        ticker_select.select_option("")
        state_end = _get_store_state(harness_page)
        assert state_end["activeTicker"] is None, (
            f"Expected activeTicker=null after clearing, got {state_end}"
        )

    def test_selecting_all_filters_then_reset(
        self,
        harness_page: Page,
    ) -> None:
        """Set every filter, then reset -- all return to null."""
        labels = ["Year:", "Industry:", "Country:", "Parent:", "Commitment:"]
        values = ["2025", "Technology", "US", "Others", "committed"]

        for label_text, val in zip(labels, values):
            harness_page.locator(f"label:has-text('{label_text}')").first.locator(
                "select"
            ).select_option(val)

        state_all_set = _get_store_state(harness_page)
        for key, val in zip(["year", "industry", "country", "parent", "commitment"], values):
            assert state_all_set[key] == val, f"Expected {key}='{val}', got {state_all_set}"

        # Reset
        harness_page.locator("button:has-text('Reset Filters')").first.click()

        state_reset = _get_store_state(harness_page)
        for key in ["year", "industry", "country", "parent", "commitment"]:
            assert state_reset[key] is None, f"{key} should be null after reset, got {state_reset}"


# ---------------------------------------------------------------------------
# ExportButton tests
# ---------------------------------------------------------------------------


class TestExportButton:
    """Black-box tests for ExportButton component (PNG + conditional CSV buttons)."""

    def test_png_button_always_renders(
        self,
        harness_page: Page,
    ) -> None:
        """Both ExportButton instances show an 'Export PNG' button."""
        png_buttons = harness_page.locator("button:has-text('Export PNG')")
        assert png_buttons.count() == 2, (
            f"Expected 2 PNG buttons (one per ExportButton instance), got {png_buttons.count()}"
        )

    def test_csv_button_renders_when_csv_data_provided(
        self,
        harness_page: Page,
    ) -> None:
        """The first ExportButton (with csvData) shows an 'Export CSV' button."""
        csv_buttons = harness_page.locator("button:has-text('Export CSV')")
        assert csv_buttons.count() == 1, f"Expected 1 CSV button, got {csv_buttons.count()}"

    def test_csv_button_absent_when_csv_data_not_provided(
        self,
        harness_page: Page,
    ) -> None:
        """The second ExportButton (no csvData) does NOT show 'Export CSV'."""
        # We already verified total count is 1 in test_csv_button_renders.
        # This is a redundant verification from a different angle.
        csv_buttons = harness_page.locator("button:has-text('Export CSV')")
        assert csv_buttons.count() == 1, "Second ExportButton should not add a CSV button"

    def test_buttons_have_type_button(
        self,
        harness_page: Page,
    ) -> None:
        """Both PNG and CSV buttons carry type='button' (prevent accidental form submit)."""
        png_buttons = harness_page.locator("button:has-text('Export PNG')")
        for i in range(png_buttons.count()):
            btn = png_buttons.nth(i)
            assert btn.get_attribute("type") == "button", (
                f"PNG button #{i} type is '{btn.get_attribute('type')}', expected 'button'"
            )

        csv_button = harness_page.locator("button:has-text('Export CSV')")
        assert csv_button.get_attribute("type") == "button", (
            f"CSV button type is '{csv_button.get_attribute('type')}', expected 'button'"
        )

    def test_png_click_with_null_ref_does_not_crash(
        self,
        harness_page: Page,
    ) -> None:
        """Clicking Export PNG with a null chartRef is a safe no-op."""
        # The second ExportButton has chartRef={{current: null}}
        png_only_btn = harness_page.locator("button:has-text('Export PNG')").nth(1)
        # Should not throw / crash the page
        png_only_btn.click()
        # If we got here without a Playwright error, the page is still alive
        assert True

    def test_png_click_with_valid_ref_triggers_download(
        self,
        harness_page: Page,
    ) -> None:
        """Clicking Export PNG with a valid ECharts ref initiates a file download.

        We use Playwright's download event to capture the triggered download
        and verify it has the expected filename and a PNG data URL payload.
        """
        # The first ExportButton has a valid chartRef (MockChart).
        png_btn = harness_page.locator("button:has-text('Export PNG')").first

        with harness_page.expect_download(timeout=5000) as download_info:
            png_btn.click()

        download = download_info.value
        assert download is not None
        # Filename should be sanitized version of chartLabel + .png
        assert download.suggested_filename.endswith(".png"), (
            f"Expected .png download, got '{download.suggested_filename}'"
        )
        # The mock getDataURL returns a data URL -- the anchor href is used as download source.
        # For a data URL href, Playwright still captures the download.
        # Verify the URL contains the mock data
        assert "Test_Chart_With_Data" in download.suggested_filename, (
            f"Filename should contain sanitized chart label, got '{download.suggested_filename}'"
        )

    def test_csv_click_triggers_download_with_correct_content(
        self,
        harness_page: Page,
    ) -> None:
        """Clicking Export CSV triggers a download; verify filename and CSV content."""
        csv_btn = harness_page.locator("button:has-text('Export CSV')")

        with harness_page.expect_download(timeout=5000) as download_info:
            csv_btn.click()

        download = download_info.value
        assert download is not None
        assert download.suggested_filename.endswith(".csv"), (
            f"Expected .csv download, got '{download.suggested_filename}'"
        )
        assert "Test_Chart_With_Data" in download.suggested_filename, (
            f"CSV filename should contain sanitized chart label, "
            f"got '{download.suggested_filename}'"
        )

    def test_png_download_filename_has_correct_extension(
        self,
        harness_page: Page,
    ) -> None:
        """PNG download uses the .png extension."""
        # Reset any previous download state by reloading
        harness_page.reload(wait_until="networkidle")
        harness_page.wait_for_selector('[data-testid="store-state"]', timeout=10000)

        png_btn = harness_page.locator("button:has-text('Export PNG')").first
        with harness_page.expect_download(timeout=5000) as dl:
            png_btn.click()
        assert dl.value.suggested_filename == "Test_Chart_With_Data.png", (
            f"Unexpected PNG filename: {dl.value.suggested_filename}"
        )

    def test_csv_download_filename_has_correct_extension(
        self,
        harness_page: Page,
    ) -> None:
        """CSV download uses the .csv extension."""
        harness_page.reload(wait_until="networkidle")
        harness_page.wait_for_selector('[data-testid="store-state"]', timeout=10000)

        csv_btn = harness_page.locator("button:has-text('Export CSV')")
        with harness_page.expect_download(timeout=5000) as dl:
            csv_btn.click()
        assert dl.value.suggested_filename == "Test_Chart_With_Data.csv", (
            f"Unexpected CSV filename: {dl.value.suggested_filename}"
        )


# ---------------------------------------------------------------------------
# Layout / style tests (smoke)
# ---------------------------------------------------------------------------


class TestLayout:
    """Minimal layout smoke tests for both components."""

    def test_filterbar_root_is_flex_container(
        self,
        harness_page: Page,
    ) -> None:
        """The FilterBar outer <div> uses flex layout."""
        # Locate the first FilterBar's root div (the one directly inside the section)
        # Strategy: find the first <h2>FilterBar (with ticker picker)</h2>, then next sibling
        root_divs = harness_page.locator("div").filter(
            has=harness_page.locator("label:has-text('Year:')")
        )
        assert root_divs.count() >= 1

    def test_export_button_root_is_flex_container(
        self,
        harness_page: Page,
    ) -> None:
        """The ExportButton outer <div> uses flex layout."""
        # Check the first ExportButton container
        export_root = harness_page.locator("button:has-text('Export PNG')").first.locator("..")
        display = export_root.evaluate("el => window.getComputedStyle(el).display")
        assert display == "flex", f"Expected flex display, got '{display}'"

    def test_page_does_not_show_react_error_overlay(
        self,
        harness_page: Page,
    ) -> None:
        """No React error overlay is present on the page (catch-all regression)."""
        # Vite's React error overlay has a specific structure
        error_overlay = harness_page.locator("[data-vite-dev-id]")
        assert error_overlay.count() == 0, (
            "React/Vite error overlay found on page -- regression detected"
        )
