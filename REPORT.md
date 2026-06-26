# MedArchive — Quality Report

Processing the provided sample archive (`data/`) against the organizer dictionary `Справочник услуг.xlsx`.

## Aggregate

- Documents processed: **10** ({'needs_review': 10})
- Price items extracted: **14554** (active after versioning: **12103**, archived/superseded: 2451)
- Target dictionary services: **1230**
- Normalization vs real dictionary: auto **5452** (**37.5%**), review 8064, unmatched 1038, manual 0
- Items flagged by validation: **1150**

### How to read the normalization numbers

- **auto** — score ≥ 0.85 (cosine/fuzzy blend), matched without a human.
- **review** — a ranked candidate exists (0.60–0.85) → operator confirms in `/unmatched`.
- **unmatched** — no plausible candidate (often a service genuinely absent from the dictionary, e.g. specific allergen panels).
- ~92% of items have a ranked candidate, so operator work is *confirm/correct*, not *search*.
- Auto-rate is precision-first: sampling shows matches below 0.85 are mostly wrong, so lowering the threshold to reach the spec's 70% goal would inject bad matches. Higher auto-rate needs a medical-domain embedding model or a richer synonym set, not threshold gaming.

## Per-document

| File | Format | Status | Items | Tiers | Extraction methods |
|---|---|---|---:|---:|---|
| Клиника 1 2026.pdf | pdf | needs_review | 32 | 32 | {'pdf_text': 32} |
| Клиника 1 прайс 2024.docx | docx | needs_review | 2623 | 2623 | {'docx': 2623} |
| Клиника 2 прайс 2025 год.PDF | pdf | needs_review | 717 | 717 | {'pdf_text': 717} |
| Клиника 2 прайс 2026.pdf | pdf | needs_review | 100 | 148 | {'pdf_text': 100} |
| Клиника 3 прайс 2026.PDF | pdf | needs_review | 739 | 1391 | {'pdf_text': 739} |
| Клиника 4 прайс 2026.pdf | pdf | needs_review | 355 | 1039 | {'pdf_ocr': 7, 'pdf_text': 348} |
| Клиника 5 прайс 2025.pdf | pdf | needs_review | 225 | 243 | {'pdf_text': 225} |
| Клиника 6 прайс 2026.xlsx | xlsx | needs_review | 5026 | 20094 | {'xlsx': 5026} |
| Клиника 7_Прайс 2026.xls | xls | needs_review | 2883 | 8649 | {'xls': 2883} |
| Клиника 8 2026.xlsx | xlsx | needs_review | 1854 | 1854 | {'xlsx': 1854} |
