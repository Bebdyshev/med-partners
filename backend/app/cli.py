"""Command-line entry points for offline work.

Usage:
  python -m app.cli extract <file-or-dir>        # dry-run extraction, prints summary
  python -m app.cli ingest <dir-or-zip>          # ingest into DB + process synchronously
  python -m app.cli seed-dictionary              # bootstrap Service dictionary from items
  python -m app.cli report                       # quality report
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.extractors.registry import detect_format, get_extractor


def _extract_one(path: Path) -> None:
    ex = get_extractor(path)
    if ex is None:
        print(f"  ! no extractor for {path.name}")
        return
    res = ex.extract(path)
    matched = sum(1 for r in res.rows if r.prices)
    print(f"\n=== {path.name} [{detect_format(path).value}] ===")
    print(f"  rows={len(res.rows)} priced={matched} methods={res.method_stats}")
    if res.meta:
        print(f"  meta={ {k: v for k, v in res.meta.items() if k != 'sheets'} }")
    for r in res.rows[:3]:
        prices = [(p.label[:24] if p.label else None, str(p.amount), p.currency) for p in r.prices]
        print(f"   • [{r.category}] {r.raw_name[:48]!r} code={r.code} {prices}")
    if res.warnings:
        print(f"  warnings ({len(res.warnings)}): {res.warnings[:3]}")


def cmd_extract(target: str) -> None:
    p = Path(target)
    files = sorted(f for f in p.iterdir() if f.is_file() and not f.name.startswith("~$")) if p.is_dir() else [p]
    for f in files:
        try:
            _extract_one(f)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {f.name}: {type(exc).__name__}: {exc}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "extract":
        cmd_extract(sys.argv[2] if len(sys.argv) > 2 else ".")
    elif cmd == "ingest":
        from app.services.ingestion import ingest_path

        ingest_path(Path(sys.argv[2]))
    elif cmd == "load-dictionary":
        from app.normalization.dictionary import load_dictionary

        n = load_dictionary(sys.argv[2])
        print(f"loaded {n} dictionary services from {sys.argv[2]}")
    elif cmd == "seed-dictionary":
        from app.normalization.dictionary import seed_from_items

        n = seed_from_items()
        print(f"created {n} dictionary services")
    elif cmd == "renormalize":
        from app.services.normalize_all import renormalize_all

        print(renormalize_all())
    elif cmd == "report":
        from app.services.report import print_report

        print_report()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
