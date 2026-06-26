# MedArchive — Normalization Eval

Ground truth: **2938** (raw_name, category) labels derived from exact tariff-code matches (zero manual labeling). Matcher (NAME-only signal) measured against them.

Model: `intfloat/multilingual-e5-base`

| Auto threshold | Auto-rate | Precision | Auto count |
|---:|---:|---:|---:|
| 0.60 | 72% | 71% | 2102 |
| 0.65 | 66% | 74% | 1938 |
| 0.70 | 56% | 77% | 1631 |
| 0.75 | 0% | 0% | 0 |
| 0.78 | 0% | 0% | 0 |
| 0.80 | 0% | 0% | 0 |
| 0.82 | 0% | 0% | 0 |
| 0.85 | 0% | 0% | 0 |
| 0.88 | 0% | 0% | 0 |
| 0.90 | 0% | 0% | 0 |

_No threshold reached the 90% precision target on this set._

> In production, code-matched items (~27% of all rows) are matched by code at ~100% precision **before** name matching — so the overall auto precision is higher than the name-only figures above.
