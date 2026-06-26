"""Code-first matching.

The organizer dictionary carries an official tariff code per service
(`TarificatrCode` -> `Service.icd_code`). Many clinic price rows carry the same
code (`PriceItem.raw_code`). A code match is exact and name-independent, so it is
the highest-precision signal we have — tried before any fuzzy/semantic matching.

Clinic codes often append a variant suffix (e.g. "A02.020.000.2"); we trim to the
canonical 3-group form "X00.000.000" before comparing.
"""
from __future__ import annotations

import re

# canonical dictionary code form, e.g. A02.004.000
_CANON = re.compile(r"[A-Za-z]\d{2}\.\d{3}\.\d{3}")


def normalize_code(raw: str | None) -> str | None:
    """Return the canonical 3-group code embedded in `raw`, or None."""
    if not raw:
        return None
    s = re.sub(r"[^A-Za-z0-9.]", "", str(raw)).upper()
    m = _CANON.search(s)
    return m.group(0) if m else None


class CodeIndex:
    """Maps a canonical code -> (service_id, canonical_name)."""

    def __init__(self, triples):
        # triples: iterable of (icd_code, service_id, canonical_name)
        self.by_code: dict[str, tuple[str, str]] = {}
        for code, sid, name in triples:
            nc = normalize_code(code)
            if nc and nc not in self.by_code:
                self.by_code[nc] = (str(sid), name)

    def lookup(self, raw_code: str | None) -> tuple[str, str] | None:
        nc = normalize_code(raw_code)
        return self.by_code.get(nc) if nc else None

    def __len__(self) -> int:
        return len(self.by_code)
