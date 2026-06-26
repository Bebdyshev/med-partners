from app.normalization.code_match import CodeIndex, normalize_code


def test_normalize_code_canonical():
    assert normalize_code("A02.004.000") == "A02.004.000"


def test_normalize_code_trims_variant_suffix():
    # clinic codes append a variant suffix -> trim to the 3-group canonical form
    assert normalize_code("A02.020.000.2") == "A02.020.000"
    assert normalize_code(" b06.576.005.7 ") == "B06.576.005"


def test_normalize_code_none():
    assert normalize_code(None) is None
    assert normalize_code("U1.1") is None        # clinic-local code, not a tariff code
    assert normalize_code("прием врача") is None


def test_code_index_lookup():
    idx = CodeIndex([("A02.004.000", "svc-1", "Прием акушер-гинеколога"),
                     ("C03.033.004", "svc-2", "3D УЗИ плода")])
    assert len(idx) == 2
    hit = idx.lookup("A02.004.000.5")  # variant suffix still resolves
    assert hit == ("svc-1", "Прием акушер-гинеколога")
    assert idx.lookup("Z99.999.999") is None
