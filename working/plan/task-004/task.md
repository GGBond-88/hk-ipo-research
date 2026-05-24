# Task 004: L1 language detection, ticker-from-filename, skip stub

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L1 sectioning -> L2 flat extraction -> L3 validation -> L4 hierarchical categorize -> L5 enrichments -> L6 SQLite loader -> L7 JSON export -> dashboard.
- **Tech Stack:** Python 3.10+, pydantic v2, pymupdf4llm, pdfplumber, langdetect.

## Task Objective

Extend `l1_sectioning.py` to: (a) derive `hk_ticker` from the filename (zero-padded 5-digit pattern); (b) detect document language with `langdetect`; (c) emit a `skipped=true` stub for Chinese-dominant PDFs without running text/table extraction; (d) honour a `--limit N` flag.

This is Task 4 of 27.

---

**Files:**
- Modify: `src/hk_ipo/l1_sectioning.py`
- Modify: `tests/test_l1_sectioning.py`

- [ ] **Step 1: Write failing tests for filename-derived ticker**

Append to `tests/test_l1_sectioning.py`:

```python
# ── Task 004 — filename-derived ticker ──────────────────────────────────────

class TestTickerFromFilename:
    def test_five_digit_filename_yields_zero_padded_ticker(self):
        from hk_ipo.l1_sectioning import ticker_from_filename
        assert ticker_from_filename("01234.pdf") == "01234"

    def test_four_digit_filename_zero_pads_to_five(self):
        from hk_ipo.l1_sectioning import ticker_from_filename
        assert ticker_from_filename("3690.pdf") == "03690"

    def test_non_numeric_filename_returns_none(self):
        from hk_ipo.l1_sectioning import ticker_from_filename
        assert ticker_from_filename("ltn20180907011.pdf") is None

    def test_path_with_directories_uses_basename(self):
        from hk_ipo.l1_sectioning import ticker_from_filename
        assert ticker_from_filename("/foo/bar/03690.pdf") == "03690"
```

- [ ] **Step 2: Run; verify failure**

Run: `python -m pytest tests/test_l1_sectioning.py::TestTickerFromFilename -v`
Expected: `ImportError: cannot import name 'ticker_from_filename'`.

- [ ] **Step 3: Implement `ticker_from_filename` in `l1_sectioning.py`**

Add near the top (after the existing regex constants):

```python
_FILENAME_TICKER_RE = re.compile(r"^(\d{4,5})$")


def ticker_from_filename(path: str) -> str | None:
    """Return zero-padded 5-digit HK ticker from filename stem, or None."""
    stem = Path(path).stem
    m = _FILENAME_TICKER_RE.match(stem)
    return m.group(1).zfill(5) if m else None
```

Run: `python -m pytest tests/test_l1_sectioning.py::TestTickerFromFilename -v`
Expected: all 4 tests pass.

- [ ] **Step 4: Write failing tests for language detection**

Append to `tests/test_l1_sectioning.py`:

```python
class TestDetectLanguage:
    def test_english_majority_text_returns_en(self):
        from hk_ipo.l1_sectioning import detect_language
        text = (
            "The Group intends to use the net proceeds from the Global "
            "Offering for the following purposes. The Company will allocate "
            "approximately 35 per cent of the net proceeds for research."
        ) * 5
        assert detect_language(text) == "en"

    def test_chinese_majority_text_returns_zh(self):
        from hk_ipo.l1_sectioning import detect_language
        text = "本集团拟将全球发售所得款项净额用于以下用途。" * 20
        assert detect_language(text) == "zh"

    def test_mixed_text_returns_mixed_or_majority(self):
        from hk_ipo.l1_sectioning import detect_language
        # 50/50 split — accept either 'mixed' or whichever the heuristic picks
        text = ("The Group intends to use the net proceeds. " * 5
                + "本集团拟将全球发售所得款项净额用于以下用途。" * 5)
        assert detect_language(text) in ("en", "zh", "mixed")

    def test_empty_text_returns_unknown(self):
        from hk_ipo.l1_sectioning import detect_language
        assert detect_language("") == "unknown"
```

Run: `python -m pytest tests/test_l1_sectioning.py::TestDetectLanguage -v`
Expected: import error / NameError.

- [ ] **Step 5: Implement `detect_language` using `langdetect`**

Add the import at the top of `l1_sectioning.py`:

```python
from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0  # deterministic
```

And the function:

```python
def detect_language(text: str) -> str:
    """Classify text language. Returns one of: 'en', 'zh', 'mixed', 'unknown'.

    Rule:
      - 'en' if English share >= 80%
      - 'zh' if Chinese share >= 80%
      - 'mixed' if either is in (20%, 80%) and the other has at least 20%
      - 'unknown' otherwise (empty text, langdetect failure)
    """
    if not text or not text.strip():
        return "unknown"
    try:
        langs = detect_langs(text[:5000])  # cap to avoid huge inputs
    except LangDetectException:
        return "unknown"
    shares: dict[str, float] = {}
    for L in langs:
        code = "en" if str(L.lang) == "en" else ("zh" if str(L.lang).startswith("zh") else None)
        if code:
            shares[code] = shares.get(code, 0.0) + float(L.prob)
    en = shares.get("en", 0.0)
    zh = shares.get("zh", 0.0)
    if en >= 0.8:
        return "en"
    if zh >= 0.8:
        return "zh"
    if en >= 0.2 and zh >= 0.2:
        return "mixed"
    return "unknown"
```

Run: `python -m pytest tests/test_l1_sectioning.py::TestDetectLanguage -v`
Expected: all 4 tests pass.

- [ ] **Step 6: Write failing test for `extract_use_of_proceeds` Chinese stub**

Append:

```python
class TestExtractZhStub:
    def test_chinese_pdf_emits_stub_record(self, tmp_path):
        """When detect_language(cover_text) == 'zh', extract returns a stub
        with skipped=True and no section text."""
        from unittest.mock import patch
        from hk_ipo.l1_sectioning import extract_use_of_proceeds

        fake_doc = MagicMock()
        fake_doc.page_count = 200
        fake_doc.get_toc.return_value = []

        with patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=fake_doc), \
             patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                   return_value="本集团拟将全球发售所得款项净额用于" * 30), \
             patch("hk_ipo.l1_sectioning._extract_text", return_value=""), \
             patch("hk_ipo.l1_sectioning._extract_tables", return_value=[]):
            result = extract_use_of_proceeds("/tmp/03690.pdf")

        assert result["language"] == "zh"
        assert result["skipped"] is True
        assert result["text"] == ""
        assert result["tables"] == []
        assert result["hk_ticker"] == "03690"
```

Run: `python -m pytest tests/test_l1_sectioning.py::TestExtractZhStub -v`
Expected: KeyError or AssertionError because the language/skipped fields are not yet emitted.

- [ ] **Step 7: Integrate language detection into `extract_use_of_proceeds`**

In `extract_use_of_proceeds`, after opening the doc and before computing `_locate_via_toc`:

```python
# v2 — read a head sample to detect language; skip non-English with stub
head_pages = list(range(min(5, doc.page_count)))
head_md = pymupdf4llm.to_markdown(doc, pages=head_pages)
language = detect_language(head_md)

# v2 — derive ticker from filename FIRST (authoritative), fall back to cover
filename_ticker = ticker_from_filename(pdf_path)
cover_ticker = _extract_ticker(doc)
hk_ticker = filename_ticker or (cover_ticker.zfill(5) if cover_ticker else None)

if language == "zh":
    return {
        "company_file": Path(pdf_path).name,
        "hk_ticker": hk_ticker,
        "document_date": _extract_document_date(doc, Path(pdf_path).name),
        "section_title": "",
        "start_page": 0,
        "end_page": 0,
        "text": "",
        "tables": [],
        "extraction_method": "skipped",
        "language": language,
        "skipped": True,
    }
```

And at the end of the success branch (just before `return {...}` already there), add `"language": language` and `"skipped": False`. Also replace the line `hk_ticker = _extract_ticker(doc)` with the new `filename_ticker or cover_ticker.zfill(5) ...` resolution.

Run: `python -m pytest tests/test_l1_sectioning.py -v`
Expected: all tests pass. The new tests + all pre-existing tests pass.

- [ ] **Step 8: Write failing test for `--limit N` and `--all` CLI behaviour**

Append:

```python
class TestProcessAllLimit:
    def test_limit_caps_pdfs_processed(self, tmp_path, monkeypatch):
        from hk_ipo import l1_sectioning as L1
        raw = tmp_path / "raw"; raw.mkdir()
        sec = tmp_path / "sec"; sec.mkdir()
        for stem in ("00001", "00002", "00003"):
            (raw / f"{stem}.pdf").write_bytes(b"fake")

        calls: list[str] = []
        def fake_extract(p):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": Path(p).stem,
                "document_date": None,
                "section_title": "x", "start_page": 1, "end_page": 1,
                "text": "x", "tables": [], "extraction_method": "stub",
                "language": "en", "skipped": False,
            }
        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)
        L1.process_all(raw, sec, limit=2)
        assert len(calls) == 2

    def test_non_matching_filename_is_skipped(self, tmp_path, monkeypatch):
        from hk_ipo import l1_sectioning as L1
        raw = tmp_path / "raw"; raw.mkdir()
        sec = tmp_path / "sec"; sec.mkdir()
        (raw / "ltn20180907011.pdf").write_bytes(b"fake")  # legacy name
        (raw / "03690.pdf").write_bytes(b"fake")           # good
        calls: list[str] = []
        def fake_extract(p):
            calls.append(Path(p).name)
            return {"company_file": Path(p).name, "hk_ticker": "03690",
                    "document_date": None, "section_title": "x",
                    "start_page": 1, "end_page": 1, "text": "x", "tables": [],
                    "extraction_method": "stub", "language": "en",
                    "skipped": False}
        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)
        L1.process_all(raw, sec, all_files=True)
        assert calls == ["03690.pdf"]  # ltn-named PDF was skipped
```

Run: `python -m pytest tests/test_l1_sectioning.py::TestProcessAllLimit -v`
Expected: failure — current `process_all` accepts neither `limit` nor `all_files` kwarg.

- [ ] **Step 9: Extend `process_all` to support `limit` and the filename gate**

```python
def process_all(
    raw_dir: Path, sections_dir: Path,
    limit: int | None = None, force: bool = False,
    all_files: bool = True,
) -> None:
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if all_files:
        skipped = [p for p in pdfs if ticker_from_filename(p.name) is None]
        for p in skipped:
            print(f"[SKIP] filename does not match \\d{{4,5}}.pdf: {p.name}",
                  file=sys.stderr)
        pdfs = [p for p in pdfs if ticker_from_filename(p.name) is not None]
    if limit is not None:
        pdfs = pdfs[:limit]
    if not pdfs:
        print(f"[WARN] No PDF files to process in {raw_dir}")
        return
    for pdf in pdfs:
        out_path = sections_dir / f"{ticker_from_filename(pdf.name)}.json"
        if not force and out_path.exists():
            print(f"[SKIP] {out_path.name} exists; --force to re-run")
            continue
        try:
            data = extract_use_of_proceeds(str(pdf))
        except Exception as exc:
            print(f"[ERROR] {pdf.name}: {exc}", file=sys.stderr)
            continue
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  -> {out_path.name} (lang={data.get('language')}, "
              f"skipped={data.get('skipped')})")
```

Also update the `__main__` block to parse `--all`, `--force`, `--limit` via argparse and call `process_all` with them.

```python
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("pdf", nargs="?")
    p.add_argument("--force", action="store_true")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    from hk_ipo.config import RAW_PDFS_DIR, SECTIONS_DIR
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        process_all(RAW_PDFS_DIR, SECTIONS_DIR,
                    limit=args.limit, force=args.force, all_files=True)
    else:
        data = extract_use_of_proceeds(args.pdf)
        ticker = data.get("hk_ticker") or "unknown"
        out = SECTIONS_DIR / f"{ticker}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"-> {out}")
```

Run: `python -m pytest tests/test_l1_sectioning.py -v`
Expected: all tests pass.

- [ ] **Step 10: Run the full unit suite**

Run: `python -m pytest -q --ignore=tests/e2e`
Expected: all green (including the original L1 tests).
