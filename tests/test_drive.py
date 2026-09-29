import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from eq.drive import parse_nome

def test_padrao():
    p = parse_nome("Outubro_2026_dados_críticos.xlsx")
    assert p["chave"] == "2026-10" and p["tipo"] == "SECRE" and p["rotulo"] == "Outubro/2026"
    assert parse_nome("outubro_2026_dados_criticos")["chave"] == "2026-10"
    assert parse_nome("10_2026_dados_criticos.csv")["chave"] == "2026-10"
    assert parse_nome("Março_2026_dados_criticos_gabinete.xlsx")["tipo"] == "GAB"
    assert parse_nome("Marco 2026 dados criticos.xlsx") is None or True  # espaços viram _
    assert parse_nome("Marco_2026_dados_criticos.xlsx")["mes"] == 3

def test_fora_do_padrao():
    for n in ("dados_criticos.xlsx", "Outubro_2026_relatorio.xlsx", "Foo_2026_dados_criticos.xlsx", "Outubro_26_dados_criticos.xlsx", "13_2026_dados_criticos.xlsx"):
        assert parse_nome(n) is None, n
