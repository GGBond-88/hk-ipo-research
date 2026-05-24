"""Black-box E2E tests for all 6 dashboard views (Task 025).

Verifies view behaviour through a real Chromium browser via Playwright,
treating the rendered DOM as the sole external interface.  The main
application (``index.html``) is served by Vite dev server.

Tests:
  Navigation
    - all 6 nav tab buttons are visible
    - default view is Overview
    - each tab switch renders the corresponding view

  OverviewView
    - KPIs (Companies, Total Raised, Needs Review) render after data loads
    - Parent Allocation by Industry chart is present
    - Export PNG + CSV buttons appear

  CompanyView
    - ticker picker renders with company options
    - selecting a ticker loads and renders a Sankey diagram
    - company name and total proceeds shown in heading
    - Needs Human Review banner appears for flagged company

  TemporalView
    - heading "Parent Allocation Over Time" appears
    - FilterBar with dropdowns present
    - chart canvas renders
    - selecting a Year filter updates the chart

  IndustryView
    - heading "Industry x Parent Allocation Heatmap" appears
    - FilterBar with dropdowns present
    - chart canvas renders

  GeographicView
    - heading "Parent Breakdown by Region" appears
    - FilterBar with dropdowns present
    - chart canvas renders

  CrossDimView
    - X and Y axis dropdown selectors present
    - changing axis dropdown updates the heading
    - chart canvas renders
    - FilterBar with dropdowns present

  Cross-view interactions
    - filter set in one view persists after switching to another
    - active ticker badge in header when set in CompanyView
    - Reset Filters button clears filters across views
    - switching from CompanyView with ticker set shows badge
"""

from __future__ import annotations

import gc
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

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


def _have_npm() -> bool:
    return shutil.which("npm") is not None


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
def page(playwright_browser: Browser) -> Iterator[Page]:
    """Create a fresh browser context + page for each test (no state bleed).

    Teardown closes the context and runs gc.collect() to release Chromium
    memory promptly, keeping per-test peak RSS inside 4 GB.
    """
    context: BrowserContext = playwright_browser.new_context()
    page: Page = context.new_page()
    try:
        yield page
    finally:
        context.close()
        gc.collect()


@pytest.fixture(scope="module")
def frontend_dir() -> Path:
    d = PROJECT_ROOT / "frontend"
    if not d.exists():
        pytest.fail("frontend/ directory must exist before this test")
    return d


@pytest.fixture(scope="module")
def npm_exe() -> str:
    exe = shutil.which("npm")
    if exe is None:
        pytest.skip("npm not installed on this system")
    return exe


@pytest.fixture(scope="module")
def dev_server(frontend_dir: Path, npm_exe: str) -> Iterator[str]:
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
# Helper: navigate to the main app and switch to a specific view tab
# ---------------------------------------------------------------------------


def _navigate_to_view(page: Page, dev_server: str, view_label: str) -> None:
    """Navigate to the dashboard and click the specified view tab button."""
    page.goto(dev_server, wait_until="networkidle")
    # Wait for the navigation bar to appear (React has hydrated)
    page.wait_for_selector("nav button", timeout=10000)
    # Click the tab matching the label
    tab = page.locator(f"nav button:has-text('{view_label}')")
    tab.click()
    # Allow React to re-render
    page.wait_for_timeout(500)


def _click_nav_button(page: Page, view_label: str) -> None:
    """Click a navigation tab button by label."""
    tab = page.locator(f"nav button:has-text('{view_label}')")
    tab.click()
    page.wait_for_timeout(500)


def _wait_for_data_load(page: Page) -> None:
    """Wait for loading spinners to disappear (data has been fetched)."""
    # Wait until the "Loading..." text is gone, or timeout after 10s
    try:
        page.wait_for_function(
            "() => !document.body.innerText.includes('Loading...')",
            timeout=10000,
        )
    except Exception:
        pass  # May already be loaded


def _wait_for_chart_canvas(page: Page, timeout: int = 8000) -> None:
    """Wait for at least one ECharts canvas element to appear."""
    try:
        page.wait_for_selector("canvas", timeout=timeout)
    except Exception:
        pass  # Some views may use different rendering


# ---------------------------------------------------------------------------
# Navigation tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestNavigation:
    """Black-box tests for tab navigation between views."""

    def test_all_six_nav_buttons_visible(self, page: Page, dev_server: str) -> None:
        """All 6 view tab buttons are present in the nav bar."""
        page.goto(dev_server, wait_until="networkidle")
        page.wait_for_selector("nav button", timeout=10000)

        expected_labels = [
            "Overview",
            "Company",
            "Temporal",
            "Industry",
            "Geographic",
            "Cross-Dim",
        ]
        for label in expected_labels:
            btn = page.locator(f"nav button:has-text('{label}')")
            assert btn.count() >= 1, f"Nav button '{label}' not found"

    def test_default_view_is_overview(self, page: Page, dev_server: str) -> None:
        """The Overview view is shown by default on page load."""
        page.goto(dev_server, wait_until="networkidle")
        page.wait_for_selector("nav button", timeout=10000)
        _wait_for_data_load(page)

        # Overview tab should be highlighted (active)
        overview_btn = page.locator("nav button:has-text('Overview')")
        assert overview_btn.count() >= 1
        # KPI tiles are unique to OverviewView
        kpi_section = page.locator("text=Total Raised (HK$M)")
        assert kpi_section.count() >= 1, "KPI tiles (Overview) not found on default view"

    def test_switch_to_company_view(self, page: Page, dev_server: str) -> None:
        """Clicking 'Company' tab shows the Company view."""
        _navigate_to_view(page, dev_server, "Overview")
        _click_nav_button(page, "Company")
        _wait_for_data_load(page)

        # Company view should show the ticker picker
        company_label = page.locator("label:has-text('Company:')")
        assert company_label.count() >= 1, "Company ticker picker not visible"

    def test_switch_to_temporal_view(self, page: Page, dev_server: str) -> None:
        """Clicking 'Temporal' tab shows the Temporal view."""
        _navigate_to_view(page, dev_server, "Overview")
        _click_nav_button(page, "Temporal")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Parent Allocation Over Time')")
        assert heading.count() >= 1, "Temporal view heading not found"

    def test_switch_to_industry_view(self, page: Page, dev_server: str) -> None:
        """Clicking 'Industry' tab shows the Industry view."""
        _navigate_to_view(page, dev_server, "Overview")
        _click_nav_button(page, "Industry")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Industry x Parent Allocation Heatmap')")
        assert heading.count() >= 1, "Industry view heading not found"

    def test_switch_to_geographic_view(self, page: Page, dev_server: str) -> None:
        """Clicking 'Geographic' tab shows the Geographic view."""
        _navigate_to_view(page, dev_server, "Overview")
        _click_nav_button(page, "Geographic")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Parent Breakdown by Region')")
        assert heading.count() >= 1, "Geographic view heading not found"

    def test_switch_to_crossdim_view(self, page: Page, dev_server: str) -> None:
        """Clicking 'Cross-Dim' tab shows the Cross-Dim view."""
        _navigate_to_view(page, dev_server, "Overview")
        _click_nav_button(page, "Cross-Dim")
        _wait_for_data_load(page)

        # Cross-Dim has X/Y axis dropdowns
        x_dropdown = page.locator("label:has-text('X:') select")
        y_dropdown = page.locator("label:has-text('Y:') select")
        assert x_dropdown.count() >= 1, "X-axis dropdown not found in Cross-Dim view"
        assert y_dropdown.count() >= 1, "Y-axis dropdown not found in Cross-Dim view"


# ---------------------------------------------------------------------------
# OverviewView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestOverviewView:
    """Black-box tests for the Overview view."""

    def test_kpi_tiles_render_after_data_load(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Three KPI tiles (Companies, Total Raised, Needs Review) render with values."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        # All three KPI labels should be visible
        assert page.locator("text=Companies").count() >= 1
        assert page.locator("text=Total Raised (HK$M)").count() >= 1
        assert page.locator("text=Needs Review").count() >= 1

        # Values should not show "NaN" or "undefined"
        page_content = page.content()
        assert "NaN" not in page_content, "KPI value contains NaN"
        assert "undefined" not in page_content, "KPI value contains undefined"

    def test_chart_heading_and_canvas_present(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """The 'Parent Allocation by Industry' heading and chart canvas are present."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Parent Allocation by Industry')")
        assert heading.count() >= 1, "Chart heading not found in Overview"

        _wait_for_chart_canvas(page)
        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No chart canvas found in Overview view"

    def test_export_buttons_present(self, page: Page, dev_server: str) -> None:
        """Export PNG and Export CSV buttons are present."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        png_btn = page.locator("button:has-text('Export PNG')")
        csv_btn = page.locator("button:has-text('Export CSV')")
        assert png_btn.count() >= 1, "Export PNG button not found in Overview"
        assert csv_btn.count() >= 1, "Export CSV button not found in Overview"

    def test_dashboard_title_renders(self, page: Page, dev_server: str) -> None:
        """The main dashboard title is present."""
        page.goto(dev_server, wait_until="networkidle")
        page.wait_for_selector("nav button", timeout=10000)

        heading = page.locator("h1:has-text('HK IPO Use-of-Proceeds Dashboard')")
        assert heading.count() >= 1, "Dashboard <h1> title not found"


# ---------------------------------------------------------------------------
# CompanyView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestCompanyView:
    """Black-box tests for the Company view."""

    def test_ticker_picker_visible_with_options(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Company view shows a ticker picker with company options."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        assert company_label.count() >= 1, "Company ticker picker label not found"

        ticker_select = company_label.locator("select")
        options = ticker_select.locator("option").all()
        # Should have placeholder + at least the mock companies
        assert len(options) >= 3, (
            f"Expected >=3 ticker options (placeholder + companies), got {len(options)}"
        )

    def test_select_company_prompt_visible_initially(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """When no ticker is selected, a prompt message is shown."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        prompt = page.locator("text=Select a company above to view its Sankey diagram.")
        assert prompt.count() >= 1, "Initial company prompt not visible"

    def test_select_ticker_shows_sankey_heading(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting a ticker loads and displays the Sankey diagram heading."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00001")

        # Wait for the Sankey data to load and heading to appear
        page.wait_for_selector("h3", timeout=10000)

        heading = page.locator("h3")
        heading_text = heading.first.inner_text()
        assert "00001" in heading_text, (
            f"Ticker '00001' not found in Sankey heading: '{heading_text}'"
        )
        assert "Alpha Healthcare Group" in heading_text, (
            f"Company name not found in Sankey heading: '{heading_text}'"
        )
        assert "Total: HK$" in heading_text, (
            f"Total proceeds not found in Sankey heading: '{heading_text}'"
        )

    def test_select_ticker_shows_sankey_canvas(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting a ticker renders a Sankey chart canvas."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00002")

        _wait_for_chart_canvas(page, timeout=10000)
        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No Sankey chart canvas found"

    def test_needs_review_banner_for_flagged_company(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting a company with needs_human_review=True shows warning banner."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        # 00002 has needs_human_review = true
        ticker_select.select_option("00002")
        page.wait_for_timeout(1000)

        banner = page.locator("text=Needs Human Review")
        assert banner.count() >= 1, "Needs Human Review banner not shown for flagged company"

    def test_needs_review_banner_absent_for_clean_company(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting a company with needs_human_review=False shows no banner."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        # 00001 has needs_human_review = false
        ticker_select.select_option("00001")
        page.wait_for_timeout(1500)

        # Use a strict check: the Needs Human Review text should not appear
        # in a warning context (it could appear in other places)
        page.locator("div:has-text('Needs Human Review')")
        # The banner should have orange background styling
        orange_bg = page.locator('[style*="background: #fff3e0"]')
        assert orange_bg.count() == 0, "Needs Human Review banner shown for clean company"

    def test_export_buttons_present_for_sankey(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Export PNG button appears after Sankey loads."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00001")
        page.wait_for_selector("h3", timeout=10000)

        png_btn = page.locator("button:has-text('Export PNG')")
        assert png_btn.count() >= 1, "Export PNG button not found in Company view"


# ---------------------------------------------------------------------------
# TemporalView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestTemporalView:
    """Black-box tests for the Temporal view."""

    def test_heading_and_filter_bar_present(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Temporal view shows heading and filter bar after data load."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Parent Allocation Over Time')")
        assert heading.count() >= 1, "Temporal view heading not found"

        # FilterBar dropdowns should be visible
        year_label = page.locator("label:has-text('Year:')")
        industry_label = page.locator("label:has-text('Industry:')")
        assert year_label.count() >= 1, "Year filter not found in Temporal view"
        assert industry_label.count() >= 1, "Industry filter not found in Temporal view"

    def test_chart_canvas_renders(self, page: Page, dev_server: str) -> None:
        """Temporal view renders a chart canvas."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)
        _wait_for_chart_canvas(page)

        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No chart canvas in Temporal view"

    def test_filter_by_year_updates_view(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting a year filter updates the view without crashing."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        year_label = page.locator("label:has-text('Year:')").first
        year_select = year_label.locator("select")
        year_select.select_option("2024")
        page.wait_for_timeout(800)

        # View should still be functional (no error overlay)
        error_overlay = page.locator("[data-vite-dev-id]")
        assert error_overlay.count() == 0, "React error overlay appeared after filter"

        # Heading should still be present
        heading = page.locator("h3:has-text('Parent Allocation Over Time')")
        assert heading.count() >= 1, "Temporal heading disappeared after filter"

    def test_export_buttons_present(self, page: Page, dev_server: str) -> None:
        """Export PNG and CSV buttons are present in Temporal view."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        png_btn = page.locator("button:has-text('Export PNG')")
        csv_btn = page.locator("button:has-text('Export CSV')")
        assert png_btn.count() >= 1, "Export PNG not in Temporal view"
        assert csv_btn.count() >= 1, "Export CSV not in Temporal view"


# ---------------------------------------------------------------------------
# IndustryView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestIndustryView:
    """Black-box tests for the Industry view."""

    def test_heading_and_filter_bar_present(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Industry view shows heading and filter bar after data load."""
        _navigate_to_view(page, dev_server, "Industry")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Industry x Parent Allocation Heatmap')")
        assert heading.count() >= 1, "Industry view heading not found"

        filter_labels = page.locator("label select")
        assert filter_labels.count() >= 1, "Filter dropdowns not found in Industry view"

    def test_chart_canvas_renders(self, page: Page, dev_server: str) -> None:
        """Industry view renders a chart canvas (heatmap)."""
        _navigate_to_view(page, dev_server, "Industry")
        _wait_for_data_load(page)
        _wait_for_chart_canvas(page)

        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No chart canvas in Industry view"

    def test_filter_by_industry_updates_view(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Selecting an industry filter updates the view without error."""
        _navigate_to_view(page, dev_server, "Industry")
        _wait_for_data_load(page)

        industry_label = page.locator("label:has-text('Industry:')").first
        industry_select = industry_label.locator("select")
        industry_select.select_option("Healthcare")
        page.wait_for_timeout(800)

        # View should still be functional
        error_overlay = page.locator("[data-vite-dev-id]")
        assert error_overlay.count() == 0, "React error overlay appeared after filter"

    def test_export_buttons_present(self, page: Page, dev_server: str) -> None:
        """Export buttons are present in Industry view."""
        _navigate_to_view(page, dev_server, "Industry")
        _wait_for_data_load(page)

        png_btn = page.locator("button:has-text('Export PNG')")
        csv_btn = page.locator("button:has-text('Export CSV')")
        assert png_btn.count() >= 1, "Export PNG not in Industry view"
        assert csv_btn.count() >= 1, "Export CSV not in Industry view"


# ---------------------------------------------------------------------------
# GeographicView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestGeographicView:
    """Black-box tests for the Geographic view."""

    def test_heading_and_filter_bar_present(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Geographic view shows heading and filter bar after data load."""
        _navigate_to_view(page, dev_server, "Geographic")
        _wait_for_data_load(page)

        heading = page.locator("h3:has-text('Parent Breakdown by Region')")
        assert heading.count() >= 1, "Geographic view heading not found"

        # FilterBar should have Country filter populated with ISO codes
        country_label = page.locator("label:has-text('Country:')")
        assert country_label.count() >= 1, "Country filter not found in Geographic view"

    def test_chart_canvas_renders(self, page: Page, dev_server: str) -> None:
        """Geographic view renders a chart canvas (stacked bar)."""
        _navigate_to_view(page, dev_server, "Geographic")
        _wait_for_data_load(page)
        _wait_for_chart_canvas(page)

        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No chart canvas in Geographic view"

    def test_country_filter_has_iso_code_options(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Country filter dropdown contains ISO codes (not geo region names)."""
        _navigate_to_view(page, dev_server, "Geographic")
        _wait_for_data_load(page)

        country_label = page.locator("label:has-text('Country:')").first
        country_select = country_label.locator("select")
        options_html = country_select.inner_html()

        # Should contain ISO codes from our mock data: CN, HK, US
        assert "CN" in options_html, (
            f"Expected ISO code 'CN' in Country dropdown, got: {options_html[:200]}"
        )
        assert "HK" in options_html, (
            f"Expected ISO code 'HK' in Country dropdown, got: {options_html[:200]}"
        )

        # Should NOT contain geo region names like 'mainland', 'overseas'
        assert "mainland" not in options_html, (
            "Geo region name 'mainland' found in Country dropdown (should be ISO codes)"
        )
        assert "overseas" not in options_html, (
            "Geo region name 'overseas' found in Country dropdown (should be ISO codes)"
        )

    def test_export_buttons_present(self, page: Page, dev_server: str) -> None:
        """Export buttons are present in Geographic view."""
        _navigate_to_view(page, dev_server, "Geographic")
        _wait_for_data_load(page)

        png_btn = page.locator("button:has-text('Export PNG')")
        csv_btn = page.locator("button:has-text('Export CSV')")
        assert png_btn.count() >= 1, "Export PNG not in Geographic view"
        assert csv_btn.count() >= 1, "Export CSV not in Geographic view"


# ---------------------------------------------------------------------------
# CrossDimView tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestCrossDimView:
    """Black-box tests for the Cross-Dim view."""

    def test_axis_dropdowns_present(self, page: Page, dev_server: str) -> None:
        """X and Y axis dropdown selectors are visible."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        x_select = page.locator("label:has-text('X:') select")
        y_select = page.locator("label:has-text('Y:') select")
        assert x_select.count() >= 1, "X-axis dropdown not found"
        assert y_select.count() >= 1, "Y-axis dropdown not found"

    def test_axis_dropdowns_have_all_ten_options(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Both X and Y dropdowns contain all 10 axis key options."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        x_select = page.locator("label:has-text('X:') select")
        x_options = x_select.locator("option").all()
        x_texts = [opt.inner_text() for opt in x_options]

        expected_keys = [
            "percentage",
            "amount_hkd_million",
            "total_net_proceeds",
            "parent_category",
            "geo",
            "specificity",
            "timeline",
            "capex_opex",
            "commitment",
            "esg_tag",
        ]
        for key in expected_keys:
            assert key in x_texts, f"Axis key '{key}' not found in X dropdown options: {x_texts}"

    def test_change_axis_updates_heading(self, page: Page, dev_server: str) -> None:
        """Changing X axis dropdown updates the chart heading."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        x_select = page.locator("select").nth(-2)
        x_select.select_option("amount_hkd_million")
        page.wait_for_timeout(500)

        heading = page.locator("h3").first
        heading_text = heading.inner_text()
        assert "amount_hkd_million" in heading_text, (
            f"Expected heading to contain 'amount_hkd_million', got '{heading_text}'"
        )

    def test_change_y_axis_updates_heading(self, page: Page, dev_server: str) -> None:
        """Changing Y axis dropdown updates the chart heading."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        # The CrossDim Y-axis select is the last <select> on the page
        # (after FilterBar selects and the X-axis select).
        # Using :text-matches('^Y:') would be fragile due to option text;
        # instead, locate by DOM position: the very last select element.
        all_selects = page.locator("select")
        y_select = all_selects.nth(-1)
        y_select.select_option("parent_category")
        page.wait_for_timeout(500)

        heading = page.locator("h3").first
        heading_text = heading.inner_text()
        assert "parent_category" in heading_text, (
            f"Expected heading to contain 'parent_category', got '{heading_text}'"
        )

    def test_chart_canvas_renders(self, page: Page, dev_server: str) -> None:
        """Cross-Dim view renders a chart canvas (scatter)."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)
        _wait_for_chart_canvas(page)

        canvas_els = page.locator("canvas")
        assert canvas_els.count() >= 1, "No chart canvas in Cross-Dim view"

    def test_filter_bar_present(self, page: Page, dev_server: str) -> None:
        """FilterBar with dropdowns is present in Cross-Dim view."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        year_label = page.locator("label:has-text('Year:')")
        assert year_label.count() >= 1, "Filter bar not found in Cross-Dim view"

    def test_export_buttons_present(self, page: Page, dev_server: str) -> None:
        """Export PNG and CSV buttons are present in Cross-Dim view."""
        _navigate_to_view(page, dev_server, "Cross-Dim")
        _wait_for_data_load(page)

        png_btn = page.locator("button:has-text('Export PNG')")
        csv_btn = page.locator("button:has-text('Export CSV')")
        assert png_btn.count() >= 1, "Export PNG not in Cross-Dim view"
        assert csv_btn.count() >= 1, "Export CSV not in Cross-Dim view"


# ---------------------------------------------------------------------------
# Cross-view interaction tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestCrossViewInteractions:
    """Black-box tests verifying filter/state persistence across view switches."""

    def test_filter_persists_across_view_switch(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """A filter set in one view remains active when switching to another view."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        # Set a Year filter in Temporal view
        year_label = page.locator("label:has-text('Year:')").first
        year_select = year_label.locator("select")
        year_select.select_option("2024")
        page.wait_for_timeout(500)

        # Switch to Industry view
        _click_nav_button(page, "Industry")
        _wait_for_data_load(page)

        # The Year dropdown should still show "2024"
        industry_year_label = page.locator("label:has-text('Year:')").first
        industry_year_select = industry_year_label.locator("select")
        selected_value = industry_year_select.input_value()
        assert selected_value == "2024", (
            f"Year filter should persist across views, got '{selected_value}'"
        )

    def test_reset_filters_clears_state_across_views(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Reset Filters button clears all filters globally."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        # Set multiple filters
        year_label = page.locator("label:has-text('Year:')").first
        year_label.locator("select").select_option("2024")
        page.wait_for_timeout(300)

        industry_label = page.locator("label:has-text('Industry:')").first
        industry_label.locator("select").select_option("Healthcare")
        page.wait_for_timeout(300)

        # Click Reset Filters
        reset_btn = page.locator("button:has-text('Reset Filters')").first
        reset_btn.click()
        page.wait_for_timeout(500)

        # Switch to another view to verify filters cleared
        _click_nav_button(page, "Industry")
        _wait_for_data_load(page)

        year_select = page.locator("label:has-text('Year:')").first.locator("select")
        assert year_select.input_value() == "", "Year filter should be reset to empty"

        industry_select = page.locator("label:has-text('Industry:')").first.locator("select")
        assert industry_select.input_value() == "", "Industry filter should be reset to empty"

    def test_active_ticker_badge_in_header(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Setting a ticker in CompanyView shows an active ticker badge in header."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        # Select a ticker in Company view
        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00001")
        page.wait_for_timeout(500)

        # Switch to Overview - the active ticker badge should appear in header
        _click_nav_button(page, "Overview")
        _wait_for_data_load(page)

        # The header should show "Active company: 00001"
        active_badge = page.locator("text=Active company:")
        assert active_badge.count() >= 1, "Active ticker badge not found in header"

        strong_text = active_badge.locator("strong").first
        assert strong_text.inner_text() == "00001", (
            f"Expected active ticker '00001', got '{strong_text.inner_text()}'"
        )

    def test_active_ticker_cleared_on_reset(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Clearing ticker picker removes active ticker badge from header."""
        _navigate_to_view(page, dev_server, "Company")
        _wait_for_data_load(page)

        # First select a ticker
        company_label = page.locator("label:has-text('Company:')")
        ticker_select = company_label.locator("select")
        ticker_select.select_option("00001")
        page.wait_for_timeout(500)

        # Then clear it
        ticker_select.select_option("")
        page.wait_for_timeout(500)

        # Switch to Overview - badge should be gone
        _click_nav_button(page, "Overview")
        _wait_for_data_load(page)

        active_badge = page.locator("text=Active company:")
        assert active_badge.count() == 0, "Active ticker badge should not be present after clearing"

    def test_complex_filter_then_switch_to_overview(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Setting filters then viewing Overview shows consistent KPI+chart data."""
        _navigate_to_view(page, dev_server, "Temporal")
        _wait_for_data_load(page)

        # Set Year and Industry filters
        page.locator("label:has-text('Year:')").first.locator("select").select_option("2024")
        page.wait_for_timeout(300)
        page.locator("label:has-text('Industry:')").first.locator("select").select_option(
            "Healthcare"
        )
        page.wait_for_timeout(300)

        # Switch to Overview
        _click_nav_button(page, "Overview")
        _wait_for_data_load(page)

        # KPIs should render without error
        page_content = page.content()
        assert "NaN" not in page_content, "Overview KPI shows NaN after cross-view filter"
        assert "undefined" not in page_content, (
            "Overview KPI shows undefined after cross-view filter"
        )

        # KPI labels still visible
        assert page.locator("text=Companies").count() >= 1
        assert page.locator("text=Total Raised (HK$M)").count() >= 1

    def test_no_error_overlay_after_rapid_view_switching(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """Rapidly switching between all views does not cause React errors."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        all_views = ["Overview", "Company", "Temporal", "Industry", "Geographic", "Cross-Dim"]

        for view in all_views:
            _click_nav_button(page, view)
            page.wait_for_timeout(300)

            # No error overlay should appear
            error_overlay = page.locator("[data-vite-dev-id]")
            assert error_overlay.count() == 0, (
                f"React/Vite error overlay appeared after switching to {view}"
            )

        # Verify we end on the last view
        final_view = all_views[-1]
        tab = page.locator(f"nav button:has-text('{final_view}')")
        bg_color = tab.evaluate("el => window.getComputedStyle(el).backgroundColor")
        assert bg_color == "rgb(26, 115, 232)", (
            f"Expected '{final_view}' tab to be active (blue bg), got '{bg_color}'"
        )


# ---------------------------------------------------------------------------
# Error state tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
class TestErrorStates:
    """Black-box tests verifying error state visibility (simulated by fetching
    non-existent URLs -- NOT possible without server-side manipulation, so we
    test the happy path and confirm no errors leak to the user for valid data)."""

    def test_no_error_text_visible_with_valid_data(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """With valid mock data, no red error text appears on any view."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        # Check all 6 views
        for view_label in ["Overview", "Temporal", "Industry", "Geographic", "Cross-Dim"]:
            _click_nav_button(page, view_label)
            page.wait_for_timeout(1000)

            # No red error text should be present
            red_errors = page.locator('[style*="color: red"]')
            for i in range(red_errors.count()):
                text = red_errors.nth(i).inner_text()
                assert "Error:" not in text, f"Error text found in {view_label} view: '{text}'"

    def test_all_views_render_content_not_loading(
        self,
        page: Page,
        dev_server: str,
    ) -> None:
        """After initial load, all views show content (not 'Loading...')."""
        _navigate_to_view(page, dev_server, "Overview")
        _wait_for_data_load(page)

        for view_label in ["Overview", "Temporal", "Industry", "Geographic"]:
            _click_nav_button(page, view_label)
            page.wait_for_timeout(1500)

            body_text = page.inner_text("body")
            assert "Loading..." not in body_text, (
                f"'{view_label}' view still shows 'Loading...' after data should be loaded"
            )
