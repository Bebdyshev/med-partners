"""Shared enums used across models."""
from __future__ import annotations

import enum


class FileFormat(str, enum.Enum):
    pdf = "pdf"
    scan_pdf = "scan_pdf"
    docx = "docx"
    xlsx = "xlsx"
    xls = "xls"
    unknown = "unknown"


class ParseStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    needs_review = "needs_review"
    error = "error"


class MatchStatus(str, enum.Enum):
    auto = "auto"          # matched automatically above threshold
    manual = "manual"      # confirmed/changed by an operator
    review = "review"      # candidate exists but below auto threshold
    unmatched = "unmatched"


class TierType(str, enum.Enum):
    base_no_vat = "base_no_vat"             # цена без НДС
    resident_kzt = "resident_kzt"           # граждане РК / оралманы / ПМЖ
    near_abroad = "near_abroad"             # СНГ / ближнее зарубежье
    far_abroad = "far_abroad"               # дальнее зарубежье
    nonresident_generic = "nonresident_generic"  # «для нерезидентов» без уточнения
    unknown = "unknown"


class MatchMethod(str, enum.Enum):
    exact = "exact"
    fuzzy = "fuzzy"
    embedding = "embedding"
    manual = "manual"


class MatchAction(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"
    created_service = "created_service"
