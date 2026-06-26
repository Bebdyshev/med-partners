from decimal import Decimal

from app.extractors.common.price_parse import parse_price, looks_like_price


def test_space_thousands():
    assert parse_price("14 400")[0] == Decimal("14400")
    assert parse_price("9 975")[0] == Decimal("9975")


def test_comma_decimal():
    assert parse_price("2099,5")[0] == Decimal("2099.5")


def test_currency_suffix():
    amt, cur = parse_price("12 840 тг")
    assert amt == Decimal("12840") and cur == "KZT"
    assert parse_price("100 USD")[1] == "USD"


def test_numeric_passthrough():
    assert parse_price(2210)[0] == Decimal("2210")
    assert parse_price(2099.5)[0] == Decimal("2099.5")


def test_non_price():
    assert parse_price(None) is None
    assert parse_price("консультация") is None
    assert not looks_like_price("прием врача")
