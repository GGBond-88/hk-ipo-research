# Fix: Missing @pytest.mark.e2e Markers

## Files fixed

- `tests/e2e/test_l5_industry_blackbox.py`: Added `pytestmark = pytest.mark.e2e` after the module-level `PROJECT_ROOT` constants (pytest was already imported). All 21 tests were being collected by `-m "not e2e"`.
- `tests/e2e/test_l1_blackbox.py`: Added `pytestmark = pytest.mark.e2e` (pytest already imported). 15 tests were leaking.
- `tests/e2e/test_l3_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. 20 tests were leaking.
- `tests/e2e/test_l4_blackbox.py`: Added `pytestmark = pytest.mark.e2e` (pytest already imported). Tests were leaking.
- `tests/e2e/test_l5_capex_opex_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. 36 tests were leaking.
- `tests/e2e/test_l5_country_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. Tests were leaking.
- `tests/e2e/test_l5_esg_tag_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. Tests were leaking.
- `tests/e2e/test_l5_timeline_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. Tests were leaking.
- `tests/e2e/test_l6_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. Tests were leaking.
- `tests/e2e/test_l7_blackbox.py`: Added `import pytest` and `pytestmark = pytest.mark.e2e`. Tests were leaking.

Files that already had `pytestmark` (no change needed):
- `tests/e2e/test_pipeline_e2e.py`
- `tests/e2e/test_dashboard_build_e2e.py`
- `tests/e2e/test_dashboard_dev_e2e.py`
- `tests/e2e/test_dashboard_views_e2e.py`
- `tests/e2e/test_filterbar_exportbutton_e2e.py`
- `tests/e2e/test_l5_geo_blackbox.py`

## Pattern used

Module-level `pytestmark = pytest.mark.e2e` (same as `test_pipeline_e2e.py`). This marks every test function in the module with the `e2e` marker without needing per-method decorators.

## Verification

`pytest -m "not e2e" tests/e2e/test_l5_industry_blackbox.py` -> no tests collected (21 deselected)

`pytest -m "e2e" tests/e2e/test_l5_industry_blackbox.py --collect-only` -> 21 tests collected

`pytest -m "not e2e" tests/e2e/ --collect-only -q` -> no tests collected (317 deselected)

## Status
done
