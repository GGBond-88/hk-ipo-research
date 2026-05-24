# Golden PDF corpus for E2E tests

This directory must hold exactly THREE prospectus PDFs named after their HK
ticker, zero-padded to 5 digits:

  03690.pdf   — Meituan (already known to project, English, has TOC bookmark)
  ?????.pdf   — pick one other from data/raw_pdfs/ at execution time
  zh_demo.pdf — a Chinese-dominant PDF (used to test the language-skip path)

Do NOT commit PDF binaries here. Each task that needs to run the e2e suite
must copy three files from `data/raw_pdfs/` (or use symlinks).

The e2e tests skip when these files are missing.
