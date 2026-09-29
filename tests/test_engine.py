"""Valida o porte Python contra a saída do motor JS (que por sua vez foi validado contra o arquivo final).
Uso: pytest tests -q   (variáveis: EQ_ORIG_ROWS=orig_rows.json, EQ_JS_OUT=tratados.json)"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from eq import engine

ROWS = os.environ.get("EQ_ORIG_ROWS")
JS = os.environ.get("EQ_JS_OUT")
CFG = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config", "cfg.json"), encoding="utf8"))

def test_paridade_js():
    if not (ROWS and JS):
        import pytest; pytest.skip("defina EQ_ORIG_ROWS e EQ_JS_OUT")
    rows = json.load(open(ROWS, encoding="utf8"))
    py = engine.processar(rows, CFG)
    js = json.load(open(JS, encoding="utf8"))["tratados"]
    assert py["resumo"] == json.load(open(JS, encoding="utf8"))["resumo"]
    assert len(py["tratados"]) == len(js)
    for a, b in zip(py["tratados"], js):
        for k in ("universo", "rank", "lot", "unidade", "tipo", "classe", "situacao", "semDados", "recente", "res", "est", "solic"):
            assert a[k] == b[k], (k, a["lot"], a[k], b[k])
        for k in ("prev", "pre", "deficit", "media", "tx", "Nd", "Nm", "Nt", "ipco"):
            if a[k] is None or b[k] is None:
                assert a[k] == b[k], (k, a["lot"])
            else:
                assert math.isclose(a[k], b[k], abs_tol=1e-9), (k, a["lot"], a[k], b[k])

def test_num():
    assert abs(engine.num("75.99%") - 0.7599) < 1e-12 and engine.num("+1.0000") == 1.0 and engine.num("=#N/A") is None and engine.num("—") is None

def test_busca_fuzzy():
    m = engine.buscar_mask(["2ª VARA DA COMARCA DE BURITICUPU", "VARA ÚNICA DE PERITORÓ"], ["BURITICUPU", "PERITORÓ"], "burticupu")
    assert m == [True, False]
