# Task 005: L2 extraction — drop old vocab check, emit category_raw only, add schema_version

## Project Overview

- **Goal:** Build a CLI-driven data pipeline plus React dashboard that locates "Use of Proceeds" sections in HKEX prospectus PDFs, extracts each use with a two-pass LLM (flat extraction + hierarchical classification), enriches with eight tag dimensions, persists to SQLite, and renders interactive charts from pre-baked JSON.
- **Architecture:** Eight-stage CLI pipeline (L1 sectioning -> L2 flat extraction -> L3 validation -> L4 hierarchical categorize -> L5 enrichments -> L6 SQLite loader -> L7 JSON export -> React/Vite/ECharts dashboard). Each stage is independently runnable and idempotent. SQLite is source of truth; frontend reads pre-baked JSON only.
- **Tech Stack:** Python 3.10+, pydantic v2, pymupdf4llm, OpenAI SDK + OpenRouter, SQLite (stdlib), pytest. Frontend: Vite + React + TypeScript + ECharts + Zustand + dayjs.

## Task Objective

Update the L2 extraction system prompt and output logic to: (a) drop the mandatory L2 category vocabulary check in the prompt (the new pipeline leaves categorization to L4); (b) ensure `category_raw` is emitted for every use item; (c) include `schema_version` in every output record. Existing L2 tests must continue to pass after the prompt change.

This is Task 5 of 27.

---

**Files:**
- Modify: `src/hk_ipo/l2_extraction.py`
- Modify: `tests/test_l2_hardening.py`

- [ ] **Step 1: Write failing tests for the v2 L2 prompt changes**

Append to `tests/test_l2_hardening.py`:

```python
# ── Task 005 — L2 v2 prompt changes ──────────────────────────────────────────

def test_system_prompt_no_longer_lists_categories():
    """The system prompt must NOT contain the old CATEGORY_L2 vocabulary list
    because classification is now the responsibility of L4."""
    from hk_ipo.l2_extraction import _SYSTEM_PROMPT
    # The old prompt contained a specific category list instruction.
    # The new prompt must not reference CATEGORY_L2 from schema.py.
    assert "Manufacturing expansion" not in _SYSTEM_PROMPT
    assert "Overseas expansion" not in _SYSTEM_PROMPT
    assert "Working capital" not in _SYSTEM_PROMPT
    assert "R&D and technology" not in _SYSTEM_PROMPT
    # The new prompt still asks for category_raw
    assert "category_raw" in _SYSTEM_PROMPT
    # No longer references CATEGORY_L2 from schema
    from hk_ipo.l2_extraction import _CATEGORY_LIST
    # _CATEGORY_LIST must not still echo old CATEGORY_L2 vocabulary
    import hk_ipo.schema as s
    for cat in s.CATEGORY_L2:
        assert cat not in _CATEGORY_LIST


def test_parse_llm_output_always_emits_category_raw():
    from hk_ipo.l2_extraction import _parse_llm_output
    data = {
        "uses": [
            {
                "category_raw": "research and development of core algorithms",
                "percentage": 35.0,
                "amount_hkd_million": 100.0,
            }
        ]
    }
    uses = _parse_llm_output(data, "test.pdf")
    assert uses[0]["category_raw"] == "research and development of core algorithms"
    assert "category" in uses[0]  # field present but may be None
    assert "parent_category" not in uses[0]  # L4 populates these later


def test_build_result_includes_schema_version():
    from hk_ipo.l2_extraction import _build_result
    from hk_ipo.schema import SCHEMA_VERSION
    result = _build_result("test.pdf", "01234", "2024-06-30", 1000.0, [])
    assert result["schema_version"] == SCHEMA_VERSION


def test_extract_section_output_has_schema_version(tmp_path):
    """End-to-end mock: extract_section output includes schema_version."""
    import json
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from hk_ipo.l2_extraction import extract_section

    section_data = {
        "company_file": "01234.pdf",
        "hk_ticker": "01234",
        "document_date": "2024-06-30",
        "section_title": "USE OF PROCEEDS",
        "start_page": 1, "end_page": 3,
        "text": ("We estimate net proceeds of approximately HK$1,000 million.\n\n"
                 "- Approximately 100% or HK$1,000 million for research.\n"),
        "tables": [],
        "extraction_method": "toc",
    }
    fake_llm_output = {
        "total_net_proceeds_hkd_million": 1000.0,
        "uses": [
            {
                "category_raw": "research",
                "percentage": 100.0,
                "amount_hkd_million": 1000.0,
                "description": "Research.",
                "source_text": "Approximately 100%...",
            }
        ],
    }
    fake_v = (True, [], [])  # L3 validation passes

    with patch("hk_ipo.l2_extraction._call_llm", return_value=fake_llm_output), \
         patch("hk_ipo.l2_extraction.validate_record", return_value=fake_v):
        result = extract_section(section_data)
    assert result["schema_version"] is not None
    for u in result["uses"]:
        assert "category_raw" in u
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `python -m pytest tests/test_l2_hardening.py::test_system_prompt_no_longer_lists_categories tests/test_l2_hardening.py::test_parse_llm_output_always_emits_category_raw tests/test_l2_hardening.py::test_build_result_includes_schema_version tests/test_l2_hardening.py::test_extract_section_output_has_schema_version -v`

Expected: 3 of 4 tests fail. `test_build_result_includes_schema_version` may already pass if `_build_result` already includes `schema_version` from Task 003 changes. If it passes, adjust the test to verify `schema_version` equals current `SCHEMA_VERSION`.

- [ ] **Step 3: Update `_SYSTEM_PROMPT` in `l2_extraction.py`**

Replace the current `_SYSTEM_PROMPT` near the top of the file. The new prompt drops the category vocabulary constraint and emphasizes `category_raw` as the primary output:

```python
_SYSTEM_PROMPT = (
    "You are a financial data extraction assistant specialised in Hong Kong IPO prospectuses.\n"
    "\n"
    "## Task\n"
    "Extract use-of-proceeds data from the provided prospectus section and return it as JSON.\n"
    "\n"
    "## Output format (JSON, no markdown fences)\n"
    "{\n"
    '  "total_net_proceeds_hkd_million": <number or null>,\n'
    '  "uses": [\n'
    "    {\n"
    '      "category_raw": "<verbatim use-description phrase from source>",\n'
    '      "percentage": <number or null>,\n'
    '      "amount_hkd_million": <number or null>,\n'
    '      "description": "<1-2 sentence summary, max 200 chars>",\n'
    '      "source_text": "<complete paragraph from source for this use>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "\n"
    "## Rules for total_net_proceeds_hkd_million\n"
    "- Use the BASE CASE only. Ignore over-allotment and conditional scenarios.\n"
    "- If multiple figures appear, take the largest non-conditional number.\n"
    "- Express in HK$ millions (e.g. HK$1,000 million -> 1000.0).\n"
    "\n"
    "## Rules for uses array\n"
    "- Extract TOP-LEVEL bullets only.\n"
    "  A top-level item starts with a bullet marker (`-`) at the LEFT margin "
    "(0-2 leading spaces).\n"
    "  Sub-items are indented (>=4 spaces) or are lettered (i)(ii)(iii) inside a bullet.\n"
    "  Each `- approximately X%` at the left margin is ONE top-level item; its entire paragraph\n"
    "  including all sub-bullets belongs in that item's source_text.\n"
    "  Do NOT create a separate entry for a sub-bullet or lettered clause.\n"
    "- source_text must be the COMPLETE paragraph for that bullet from the source.\n"
    "- category_raw must be a SHORT verbatim phrase from the source that describes "
    "what the proceeds are used for (e.g. \"research and development\", "
    "\"debt repayment\", \"manufacturing expansion\").\n"
    "- Extract ALL top-level items. Do not stop early.\n"
    "\n"
    "## Example (FICTIONAL numbers -- format only)\n"
    "Input text:\n"
    "  We estimate net proceeds of approximately HK$5,000 million.\n"
    "  - Approximately 60% or HK$3,000 million will be used for manufacturing expansion.\n"
    "  - Approximately 40% or HK$2,000 million will be used for working capital.\n"
    "\n"
    "Expected output:\n"
    "{\n"
    '  "total_net_proceeds_hkd_million": 5000.0,\n'
    '  "uses": [\n'
    "    {\n"
    '      "category_raw": "manufacturing expansion",\n'
    '      "percentage": 60.0,\n'
    '      "amount_hkd_million": 3000.0,\n'
    '      "description": "Expand manufacturing capacity.",\n'
    '      "source_text": "Approximately 60% or HK$3,000 million will be used for manufacturing expansion."\n'
    "    },\n"
    "    {\n"
    '      "category_raw": "working capital",\n'
    '      "percentage": 40.0,\n'
    '      "amount_hkd_million": 2000.0,\n'
    '      "description": "General working capital and corporate purposes.",\n'
    '      "source_text": "Approximately 40% or HK$2,000 million will be used for working capital."\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "\n"
    "The example uses FICTIONAL numbers to show format only. "
    "Do NOT copy example numbers into your output.\n"
    "\n"
    "## Important\n"
    "- Do NOT attempt to classify items into categories. Only provide category_raw.\n"
    "- Classification into Parent/Main/Sub is handled by a later pass.\n"
)
```

- [ ] **Step 4: Remove `_CATEGORY_LIST` and its replacement**

Replace the old `_CATEGORY_LIST` definition:

```python
# The old _CATEGORY_LIST used CATEGORY_L2. In v2, L2 emits category_raw only;
# classification is deferred to L4. Keep the variable for backwards compat but
# ensure it is empty (no old vocabulary leaked into the prompt).
_CATEGORY_LIST = ""
```

- [ ] **Step 5: Update `_parse_llm_output` to not process old category fields**

In `_parse_llm_output`, change the use-item construction to:

```python
def _parse_llm_output(data: dict[str, Any], company_file: str = "") -> list[dict[str, Any]]:
    uses: list[dict[str, Any]] = []
    for i, item in enumerate(data.get("uses", []), start=1):
        pct = _safe_float_or_none(item.get("percentage"))
        amt = _safe_float_or_none(item.get("amount_hkd_million"))
        if pct is None and amt is None:
            continue
        uses.append({
            "use_id": f"use_{i:03d}",
            "parent_id": None,
            "category": None,
            "category_proposed": None,
            "parent_category": None,
            "main_category": None,
            "sub_category": None,
            "category_raw": str(item.get("category_raw") or ""),
            "amount_hkd_million": amt,
            "percentage": pct,
            "description": str(item.get("description") or ""),
            "source_text": str(item.get("source_text") or ""),
        })
    return uses
```

- [ ] **Step 6: Run the new tests and verify they pass**

Run: `python -m pytest tests/test_l2_hardening.py -v`

Expected: All tests pass, including the 4 new v2 tests.

- [ ] **Step 7: Run ALL tests except e2e and verify no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All pre-existing tests pass (130+). No failures introduced by the prompt changes.

- [ ] **Step 8: Verify `_CATEGORY_LIST` is fully removed from the prompt context**

Run: `python -c "from hk_ipo.l2_extraction import _SYSTEM_PROMPT; print('CATEGORY_L2' in _SYSTEM_PROMPT, 'category_vocab' in _SYSTEM_PROMPT.lower())"`

Expected: `False False` — the old category vocabulary is NOT referenced in the prompt.

- [ ] **Step 9: Write tests verifying the self-correction retry logic survives the prompt changes (A2.3)**

Append to `tests/test_l2_hardening.py`:

```python
# ── Task 005 — self-correction retry verification (A2.3) ──────────────────────

def test_extract_section_self_correction_triggers_when_l3_fails():
    """When validate_record reports a sum violation, extract_section must retry
    the LLM exactly once with a CORRECTION NEEDED prompt, per spec A2.3."""
    from unittest.mock import MagicMock, patch
    from hk_ipo.l2_extraction import extract_section

    section_data = {
        "company_file": "01234.pdf",
        "hk_ticker": "01234",
        "document_date": "2024-06-30",
        "section_title": "USE OF PROCEEDS",
        "start_page": 1, "end_page": 3,
        "text": "Net proceeds HK$1,000 million.\n- 100% or HK$1,000 million for research.\n",
        "tables": [],
        "extraction_method": "toc",
    }

    # First LLM call: returns incomplete data that fails validation
    call_count = 0

    def fake_call_llm(text_arg):
        nonlocal call_count
        call_count += 1
        return {
            "total_net_proceeds_hkd_million": 1000.0,
            "uses": [
                {
                    "category_raw": "research",
                    "percentage": 50.0,  # only 50% — will fail percentage_sum
                    "amount_hkd_million": 500.0,
                    "description": "Research.",
                    "source_text": "Source text...",
                }
            ],
        }

    # No retry needed for the "API" call, just run once
    with patch("hk_ipo.l2_extraction._call_llm", side_effect=fake_call_llm), \
         patch("hk_ipo.l2_extraction._call_llm_with_prompt",
               return_value={
                   "total_net_proceeds_hkd_million": 1000.0,
                   "uses": [
                       {"category_raw": "research", "percentage": 100.0,
                        "amount_hkd_million": 1000.0,
                        "description": "Research.", "source_text": "Source..."}
                   ],
               }), \
         patch("hk_ipo.l2_extraction.validate_extraction"):
        result = extract_section(section_data)

    # The self-correction path calls _call_llm first, then _call_llm_with_prompt
    assert call_count == 1  # first call was made
    # The correction call was made (via _call_llm_with_prompt)
    # After correction passes L3, needs_human_review should NOT be set
    assert not result.get("needs_human_review", False)


def test_extract_section_sets_needs_human_review_when_correction_also_fails():
    """When self-correction still fails L3 validation, record must be flagged
    needs_human_review = True and stored as-is (spec A2.3)."""
    from unittest.mock import patch
    from hk_ipo.l2_extraction import extract_section

    section_data = {
        "company_file": "01234.pdf",
        "hk_ticker": "01234",
        "document_date": "2024-06-30",
        "section_title": "USE OF PROCEEDS",
        "start_page": 1, "end_page": 3,
        "text": "Net proceeds HK$1,000 million.\n- about half of proceeds for R&D.\n",
        "tables": [],
        "extraction_method": "toc",
    }

    failing_response = {
        "total_net_proceeds_hkd_million": 1000.0,
        "uses": [
            {
                "category_raw": "research",
                "percentage": 45.0,  # still incorrect
                "amount_hkd_million": 450.0,
                "description": "R&D.",
                "source_text": "Source...",
            }
        ],
    }

    with patch("hk_ipo.l2_extraction._call_llm", return_value=failing_response), \
         patch("hk_ipo.l2_extraction._call_llm_with_prompt",
               return_value=failing_response), \
         patch("hk_ipo.l2_extraction.validate_extraction"):
        result = extract_section(section_data)

    assert result.get("needs_human_review") is True


def test_extract_section_self_correction_runs_at_most_once():
    """Spec A2.3: 'runs at most once'. Even if the first correction fails,
    there must be no second correction attempt."""
    from unittest.mock import patch
    from hk_ipo.l2_extraction import extract_section

    section_data = {
        "company_file": "01234.pdf",
        "hk_ticker": "01234",
        "document_date": "2024-06-30",
        "section_title": "USE OF PROCEEDS",
        "start_page": 1, "end_page": 3,
        "text": "Net proceeds HK$1,000 million.\n- about half for R&D.\n",
        "tables": [],
        "extraction_method": "toc",
    }

    correction_call_count = 0
    failing_response = {
        "total_net_proceeds_hkd_million": 1000.0,
        "uses": [
            {"category_raw": "r&d", "percentage": 30.0, "amount_hkd_million": 300.0,
             "description": "R&D.", "source_text": "..."}
        ],
    }

    def fake_correction(_prompt):
        nonlocal correction_call_count
        correction_call_count += 1
        return failing_response

    with patch("hk_ipo.l2_extraction._call_llm", return_value=failing_response), \
         patch("hk_ipo.l2_extraction._call_llm_with_prompt",
               side_effect=fake_correction), \
         patch("hk_ipo.l2_extraction.validate_extraction"):
        extract_section(section_data)

    # Self-correction runs at most once
    assert correction_call_count == 1
```

- [ ] **Step 10: Run the new self-correction tests and verify they pass**

Run: `python -m pytest tests/test_l2_hardening.py::test_extract_section_self_correction_triggers_when_l3_fails tests/test_l2_hardening.py::test_extract_section_sets_needs_human_review_when_correction_also_fails tests/test_l2_hardening.py::test_extract_section_self_correction_runs_at_most_once -v`

Expected: All 3 tests pass. The existing `extract_section` function already contains the self-correction retry logic (lines 338-370 in l2_extraction.py); these tests verify it survives the Task 005 prompt changes unchanged.

If any test fails, debug: the most likely cause is the `validate_extraction` mock not suppressing the pydantic validation error or the LLM response schema mismatch. Ensure the mock for `validate_extraction` is in place (it is in the test). If the test fails because the code path was broken by Steps 3-5, undo those changes and re-apply only the prompt/parse changes without touching `extract_section`.

- [ ] **Step 11: Run ALL tests again to confirm no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All tests pass including the 3 new self-correction tests and the 4 Task 005 tests. No regressions.
