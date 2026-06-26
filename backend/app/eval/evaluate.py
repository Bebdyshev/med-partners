"""Honest precision/recall of the NAME matcher, using code matches as ground truth.

Tariff-code matches are exact, so (raw_name, category) -> service_id derived from
codes is a label set with zero manual annotation. We run the NAME-only matcher on
those names and measure, per auto-threshold:
  - auto-rate:  share of gold names whose top suggestion scores >= threshold
  - precision:  of those, share whose top suggestion is the code-truth service

Picks the threshold giving the target precision at max auto-rate and writes EVAL.md.
This turns a vague "auto %" into a defensible "X% auto @ Y% precision on N labels".
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db.session import session_scope
from app.models import PriceItem
from app.normalization.dictionary import load_matcher

THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.78, 0.80, 0.82, 0.85, 0.88, 0.90]
TARGET_PRECISION = 0.90


def evaluate() -> dict:
    with session_scope() as db:
        matcher = load_matcher(db)
        rows = db.execute(
            select(PriceItem.raw_name, PriceItem.raw_category, PriceItem.raw_code)
        ).all()

        # build gold labels from code matches; drop names with conflicting truths
        gold: dict[tuple, str | None] = {}
        for name, cat, code in rows:
            hit = matcher.code_lookup(code)
            if not hit:
                continue
            key = (name, cat or "")
            sid = str(hit.service_id)
            if key in gold and gold[key] != sid:
                gold[key] = None
            elif key not in gold:
                gold[key] = sid
        gold = {k: v for k, v in gold.items() if v}

        keys = list(gold)
        names = [k[0] for k in keys]
        cats = [k[1] or None for k in keys]
        sugg = matcher.suggest_many(names, categories=cats)  # NAME-only signal

        preds = []  # (truth_sid, top_sid, score)
        for key, s in zip(keys, sugg):
            top = s[0] if s else None
            preds.append((gold[key], str(top.service_id) if top else None, top.score if top else 0.0))

        total = len(preds)
        curve = []
        for t in THRESHOLDS:
            auto = [p for p in preds if p[2] >= t]
            n = len(auto)
            correct = sum(1 for p in auto if p[0] == p[1])
            prec = correct / n if n else 0.0
            curve.append({"threshold": t, "auto_rate": n / total if total else 0,
                          "precision": prec, "n_auto": n})

        # recommended threshold: highest auto-rate among those meeting target precision
        ok = [c for c in curve if c["precision"] >= TARGET_PRECISION]
        recommended = max(ok, key=lambda c: c["auto_rate"])["threshold"] if ok else None

        return {"gold_size": total, "curve": curve, "recommended_threshold": recommended,
                "target_precision": TARGET_PRECISION,
                "model": _model_name()}


def _model_name() -> str:
    from app.config import settings
    from app.normalization import embeddings

    return settings.embedding_model if embeddings.available() else "rapidfuzz-only"


def print_report() -> None:
    import json

    r = evaluate()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    _write_md(r)


def _write_md(r: dict) -> None:
    L = ["# MedArchive — Normalization Eval\n"]
    L.append(f"Ground truth: **{r['gold_size']}** (raw_name, category) labels derived from exact "
             "tariff-code matches (zero manual labeling). Matcher (NAME-only signal) measured against them.\n")
    L.append(f"Model: `{r['model']}`\n")
    L.append("| Auto threshold | Auto-rate | Precision | Auto count |")
    L.append("|---:|---:|---:|---:|")
    for c in r["curve"]:
        L.append(f"| {c['threshold']:.2f} | {c['auto_rate']*100:.0f}% | {c['precision']*100:.0f}% | {c['n_auto']} |")
    rec = r["recommended_threshold"]
    L.append("")
    if rec is not None:
        chosen = next(c for c in r["curve"] if c["threshold"] == rec)
        L.append(f"**Recommended `MATCH_AUTO_THRESHOLD = {rec}`** — "
                 f"{chosen['auto_rate']*100:.0f}% auto @ {chosen['precision']*100:.0f}% precision "
                 f"(target ≥ {int(r['target_precision']*100)}%).")
    else:
        L.append(f"_No threshold reached the {int(r['target_precision']*100)}% precision target on this set._")
    L.append("\n> In production, code-matched items (~27% of all rows) are matched by code at ~100% "
             "precision **before** name matching — so the overall auto precision is higher than the "
             "name-only figures above.")
    # repo root = two levels up from app/eval/
    out = Path(__file__).resolve().parents[2].parent / "EVAL.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
