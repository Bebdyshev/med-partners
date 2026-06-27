# MedArchive — Normalization Eval

Ground truth: **2938** (raw_name, category) labels derived from exact tariff-code matches (zero manual labeling). Matcher (NAME-only signal) measured against them.

Model: `intfloat/multilingual-e5-base`

| Auto threshold | Auto-rate | Precision | Auto count |
|---:|---:|---:|---:|
| 0.60 | 63% | 72% | 1857 |
| 0.65 | 63% | 72% | 1857 |
| 0.70 | 63% | 72% | 1857 |
| 0.75 | 63% | 72% | 1841 |
| 0.78 | 63% | 72% | 1841 |
| 0.80 | 63% | 72% | 1841 |
| 0.82 | 54% | 79% | 1583 |
| 0.85 | 54% | 79% | 1583 |
| 0.88 | 53% | 81% | 1549 |
| 0.90 | 53% | 81% | 1549 |

_No threshold reached the 90% precision target on this set._

> In production, code-matched items (~27% of all rows) are matched by code at ~100% precision **before** name matching — so the overall auto precision is higher than the name-only figures above.
