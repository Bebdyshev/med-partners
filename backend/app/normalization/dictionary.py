"""Dictionary loading + bootstrap.

Two ways to populate the target Service dictionary:
  * load_dictionary(path) — load an organizer-provided dictionary (XLSX or JSON).
    This is the mechanism required by the spec (sections 2.2 / 4.3).
  * seed_from_items() — fallback bootstrap when no dictionary is supplied: harvest
    distinct service names from extracted PriceItems and create one Service per
    normalized group, with the other spellings as synonyms.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import session_scope
from app.models import MatchDecision, PriceItem, Service, ServiceSynonym
from app.normalization.engine import Matcher
from app.normalization.text_norm import normalize

# header-name aliases -> canonical field, for flexible XLSX column mapping
_NAME_COLS = {"name_ru", "name", "service_name", "наименование", "наименование услуги", "услуга", "название"}
_CAT_COLS = {"специальность", "category", "категория", "раздел"}
_ICD_COLS = {"tarificatrcode", "icd", "icd_code", "мкб", "код по тарификатору", "tarificator"}
_SYN_COLS = {"synonyms", "синонимы", "synonym"}


def clear_dictionary(db) -> None:
    """Remove the current dictionary and detach items from it (keeps items)."""
    db.execute(delete(MatchDecision))
    db.execute(delete(ServiceSynonym))
    db.execute(update_items_detach())
    db.execute(delete(Service))


def update_items_detach():
    from sqlalchemy import update

    from app.models.enums import MatchStatus

    return (
        update(PriceItem)
        .values(service_id=None, match_status=MatchStatus.unmatched, match_score=None)
    )


def _norm_header(s) -> str:
    return str(s).strip().lower() if s is not None else ""


def load_dictionary(path: str | Path, replace: bool = True) -> int:
    """Load an organizer-provided dictionary (XLSX or JSON) into Service rows.
    Returns the number of services created. If replace, clears the existing one first."""
    path = Path(path)
    rows = _read_json(path) if path.suffix.lower() == ".json" else _read_xlsx(path)
    created = 0
    with session_scope() as db:
        if replace:
            clear_dictionary(db)
            db.flush()
        seen: set[str] = set()
        for rec in rows:
            name = (rec.get("name") or "").strip()
            if not name:
                continue
            key = normalize(name)
            if not key or key in seen:
                # merge as synonym of the existing service with that canonical name
                continue
            seen.add(key)
            svc = Service(
                canonical_name=name,
                category=(rec.get("category") or None),
                icd_code=(rec.get("icd") or None),
            )
            db.add(svc)
            db.flush()
            for syn in rec.get("synonyms") or []:
                if syn and syn.strip():
                    db.add(ServiceSynonym(service_id=svc.id, synonym=syn.strip(), source="seed"))
            created += 1
    return created


def _read_xlsx(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out: list[dict] = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        # find header row within the first few rows
        header_idx, colmap = -1, {}
        for i, row in enumerate(rows[:10]):
            m = _map_dict_columns(row)
            if "name" in m:
                header_idx, colmap = i, m
                break
        if header_idx < 0:
            continue
        for row in rows[header_idx + 1:]:
            def cell(field):
                idx = colmap.get(field)
                return row[idx] if idx is not None and idx < len(row) else None
            name = cell("name")
            if name is None or not str(name).strip():
                continue
            syn_raw = cell("synonyms")
            synonyms = []
            if syn_raw:
                import re as _re
                synonyms = [s for s in _re.split(r"[;,/|]", str(syn_raw)) if s.strip()]
            out.append({
                "name": str(name).strip(),
                "category": (str(cell("category")).strip() if cell("category") else None),
                "icd": (str(cell("icd")).strip() if cell("icd") else None),
                "synonyms": synonyms,
            })
    wb.close()
    return out


def _map_dict_columns(header_row) -> dict:
    m: dict[str, int] = {}
    for idx, raw in enumerate(header_row):
        h = _norm_header(raw)
        if not h:
            continue
        if "name" not in m and h in _NAME_COLS:
            m["name"] = idx
        elif "category" not in m and h in _CAT_COLS:
            m["category"] = idx
        elif "icd" not in m and h in _ICD_COLS:
            m["icd"] = idx
        elif "synonyms" not in m and h in _SYN_COLS:
            m["synonyms"] = idx
    return m


def _read_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("services", [])
    out = []
    for rec in items:
        name = rec.get("service_name") or rec.get("name") or rec.get("Name_ru")
        if not name:
            continue
        out.append({
            "name": str(name).strip(),
            "category": rec.get("category") or rec.get("Специальность"),
            "icd": rec.get("icd_code") or rec.get("TarificatrCode"),
            "synonyms": rec.get("synonyms") or [],
        })
    return out


def load_matcher(db) -> Matcher:
    rows = db.execute(
        select(Service.id, Service.canonical_name, Service.category, Service.icd_code)
    ).all()
    syn_map: dict = defaultdict(list)
    for sid, syn in db.execute(select(ServiceSynonym.service_id, ServiceSynonym.synonym)).all():
        syn_map[sid].append(syn)
    services = [(sid, name, syn_map.get(sid, []), category, icd) for sid, name, category, icd in rows]
    return Matcher(services)


# Process-level cache so API requests don't rebuild/re-encode the dictionary each
# call. Keyed by (service count, synonym count) — cheap to compute, changes when
# the dictionary or learned synonyms change.
_CACHE: dict = {}


def load_matcher_cached(db) -> Matcher:
    from sqlalchemy import func

    key = (
        db.execute(select(func.count(Service.id))).scalar(),
        db.execute(select(func.count(ServiceSynonym.id))).scalar(),
    )
    if _CACHE.get("key") == key and _CACHE.get("matcher") is not None:
        return _CACHE["matcher"]
    m = load_matcher(db)
    _CACHE["key"] = key
    _CACHE["matcher"] = m
    return m


def seed_from_items(min_count: int = 1) -> int:
    """Build the Service dictionary from distinct PriceItem.raw_name values.
    Returns the number of Service rows created. Idempotent-ish: skips if a Service
    with the same canonical name already exists."""
    created = 0
    with session_scope() as db:
        groups: dict[str, Counter] = defaultdict(Counter)
        raw_to_cat: dict[str, Counter] = defaultdict(Counter)
        rows = db.execute(select(PriceItem.raw_name, PriceItem.raw_category)).all()
        for raw_name, raw_cat in rows:
            norm = normalize(raw_name)
            if not norm or len(norm) < 3:
                continue
            groups[norm][raw_name.strip()] += 1
            if raw_cat:
                raw_to_cat[norm][raw_cat] += 1

        existing = {normalize(n) for (n,) in db.execute(select(Service.canonical_name)).all()}

        for norm, spellings in groups.items():
            if norm in existing:
                continue
            if sum(spellings.values()) < min_count:
                continue
            canonical = spellings.most_common(1)[0][0]
            category = raw_to_cat[norm].most_common(1)[0][0] if raw_to_cat.get(norm) else None
            svc = Service(canonical_name=canonical, category=category)
            db.add(svc)
            db.flush()
            # other spellings become synonyms
            for spelling, _ in spellings.most_common()[1:]:
                db.add(ServiceSynonym(service_id=svc.id, synonym=spelling, source="seed"))
            created += 1
    return created
