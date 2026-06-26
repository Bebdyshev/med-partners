from app.extractors.common.column_map import _matches, _PRICE_KW, _CODE_KW, map_columns, infer_price_columns
from app.extractors.common.header_detect import detect_header


def test_tarif_not_matching_tarifikator():
    # "тариф" must not match inside "тарификатору" (the Клиника 8 bug)
    assert not _matches("код по тарификатору, мкб-9", _PRICE_KW)
    assert _matches("код по тарификатору, мкб-9", _CODE_KW)


def test_price_keyword_matches():
    assert _matches("цена без учета ндс", _PRICE_KW)
    assert _matches("стоимость, тенге", _PRICE_KW)


def test_buried_header_detection():
    rows = [
        [None, None, "Прейскурант"],
        [None, "Утверждаю", None],
        ["№ п/п", "Наименование услуги", "Код", "Цена, тенге"],
        ["1", "Прием врача", "A01", "5000"],
    ]
    idx, header = detect_header(rows)
    assert idx == 2
    cm = map_columns(header)
    assert cm.name == 1 and cm.price_cols == [3]


def test_small_table_header_not_merged_with_first_data_row():
    # regression: a 3-col table must NOT merge the first data row into the header
    # (that previously turned the "№" 1,2,3 column into a price tier).
    rows = [
        ["Прейскурант", None, None],
        ["№", "Наименование услуги", "Цена, тенге"],
        [1, "Прием кардиолога", 7000],
        [2, "УЗИ", 9500],
    ]
    idx, header = detect_header(rows)
    assert idx == 1  # header stays on its own row, not merged with row 2 (data)
    cm = map_columns(header)
    assert cm.name == 1 and cm.price_cols == [2]


def test_sparse_continuation_header_is_merged():
    # the Клиника-8 case: a genuinely sparse row below the header IS merged
    rows = [
        ["№", "Наименование", "Код", None, None],
        [None, None, None, None, "для граждан РК"],
        ["1", "Прием", "A01", None, "5000"],
    ]
    idx, header = detect_header(rows)
    assert idx == 1  # merged through row 1
    assert any("граждан" in (h or "").lower() for h in header)


def test_inferred_numeric_price_column():
    # price header has no "цена" keyword (tariff-tier label) -> inferred from data
    header = ["№", "Наименование", "Код", "для граждан РК"]
    cm = map_columns(header)
    data = [["1", "Прием", "A01", "5000"], ["2", "УЗИ", "A02", "8000"], ["3", "ЭКГ", "A03", "3000"]]
    infer_price_columns(cm, data, header)
    assert 3 in cm.price_cols
