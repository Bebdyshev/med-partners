from datetime import date
from decimal import Decimal

from app.models.enums import TierType
from app.validation.engine import validate
from app.validation.rules import TierVal, ValItem


def _item(**kw):
    base = dict(raw_name="Прием врача", tiers=[TierVal(TierType.resident_kzt, Decimal("5000"))])
    base.update(kw)
    return ValItem(**base)


def test_price_not_positive():
    codes = {w.code for w in validate(_item(tiers=[TierVal(TierType.resident_kzt, Decimal("0"))])).warnings}
    assert "price_not_positive" in codes


def test_nonresident_lt_resident():
    item = _item(tiers=[
        TierVal(TierType.resident_kzt, Decimal("5000")),
        TierVal(TierType.far_abroad, Decimal("3000")),
    ])
    assert "nonresident_lt_resident" in {w.code for w in validate(item).warnings}


def test_future_date():
    item = _item(effective_date=date(2999, 1, 1), today=date(2026, 1, 1))
    assert "future_date" in {w.code for w in validate(item).warnings}


def test_price_anomaly():
    item = _item(prev_resident_price=Decimal("1000"))  # 5000 vs 1000 = 400%
    assert "price_anomaly" in {w.code for w in validate(item).warnings}


def test_duplicate_and_low_conf():
    item = _item(is_duplicate=True, confidence=0.4)
    codes = {w.code for w in validate(item).warnings}
    assert "duplicate" in codes and "low_confidence" in codes


def test_clean_item_no_warnings():
    item = _item(tiers=[
        TierVal(TierType.resident_kzt, Decimal("5000")),
        TierVal(TierType.far_abroad, Decimal("8000")),
    ], today=date(2026, 1, 1), effective_date=date(2026, 1, 1))
    assert validate(item).warnings == []
