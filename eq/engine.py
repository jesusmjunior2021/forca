"""Motor de transformação ORIGINAL → TRATADO (porte fiel de engine.js, validado contra o arquivo final)."""
import re, unicodedata, json, copy

DEFAULT_CFG = {
    "pesos": {"Nd": 0.6, "Nm": 0.3, "Nt": 0.1},
    "pesosSejud": {"Nd": 0.5, "Nm": 0.5, "Nt": 0.0},
    "prevSejud": 3,
    "faixas": {"alta": 0.70, "media": 0.40},
    "txCritica": 0.70,
    "sejud": [], "recentes": [], "apoio": {},
}

_ERR = re.compile(r"#(N/A|REF|DIV|VALUE|NAME|NULL|NUM)", re.I)


def is_err(v):
    return isinstance(v, str) and bool(_ERR.search(v))


def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)
    s = str(v).strip()
    if not s or s in ("—", "-") or re.fullmatch(r"n/?d", s, re.I) or is_err(s):
        return None
    pct = "%" in s
    s = s.replace("%", "").replace("+", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return n / 100 if pct else n


def norm(s):
    return re.sub(r"\s+", " ", "" if s is None else str(s)).strip().upper()


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _find_header(rows):
    for i, r in enumerate(rows[:15]):
        n = [norm(c) for c in r]
        if "CARGO" in n and any(c.startswith("LOTA") for c in n):
            return i
    return -1


def parse_original(rows):
    h = _find_header(rows)
    if h < 0:
        raise ValueError("Cabeçalho do arquivo ORIGINAL não encontrado (esperado: Cargo | Descrição | Lotação | ...).")
    ix = {}
    for i, c in enumerate(norm(x) for x in rows[h]):
        if c.startswith("LOTA"):
            ix["lot"] = i
        elif c.startswith("DESCRI"):
            if "lot" in ix and "uni" not in ix:
                ix["uni"] = i
        elif c == "COMARCA":
            ix["com"] = i
        elif c.startswith("ENTR"):
            ix["ent"] = i
        elif c.startswith("PREVISTA"):
            ix["prev"] = i
        elif c.startswith("PREENCH"):
            ix["pre"] = i
        elif c.startswith("D") and c[1:6] == "FICIT":
            ix["def"] = i
        elif c.startswith("M") and "CASOS NOVOS" in c:
            ix["med"] = i
        elif "CONGEST" in c:
            ix["tx"] = i
        elif "AFASTADOS" in c:
            ix["afa"] = i
    faltam = [k for k in ("lot", "uni", "com", "ent", "prev", "pre", "med", "tx") if k not in ix]
    if faltam:
        raise ValueError("Coluna(s) obrigatória(s) ausente(s) no ORIGINAL: " + ", ".join(faltam))
    out, desc = [], []
    for i in range(h + 1, len(rows)):
        r = list(rows[i]) + [None] * (max(ix.values()) + 1 - len(rows[i]))
        if all(c is None or c == "" for c in r):
            continue
        lot = num(r[ix["lot"]])
        if lot is None:
            desc.append({"linha": i + 1, "motivo": "Sem Lotação numérica (total/rodapé/anotação)",
                         "conteudo": " | ".join(str(c) for c in r if c not in (None, ""))})
            continue
        med, tx = r[ix["med"]], r[ix["tx"]]
        out.append({
            "lin": i + 1, "lot": int(lot), "unidade": re.sub(r"\s+", " ", str(r[ix["uni"]] or "")).strip(),
            "comarca": str(r[ix["com"]] or "").strip(), "entrancia": str(r[ix["ent"]] or "").strip(),
            "prev": num(r[ix["prev"]]), "pre": num(r[ix["pre"]]),
            "media": num(med), "tx": num(tx),
            "afast": (num(r[ix["afa"]]) or 0) if "afa" in ix else 0,
            "erroFonte": is_err(med) or is_err(tx),
        })
    return out, desc


def _minmax(vals):
    v = [x for x in vals if x is not None]
    return (min(v), max(v)) if v else (None, None)


def pontuar(lst, pesos):
    for x in lst:
        x["deficit"] = None if x["prev"] is None or x["pre"] is None else x["prev"] - x["pre"]
    pos = [x["deficit"] for x in lst if x["deficit"] is not None and x["deficit"] > 0]
    neg = [-x["deficit"] for x in lst if x["deficit"] is not None and x["deficit"] < 0]
    mx, mn = (max(pos) if pos else None), (max(neg) if neg else None)
    mM, MM = _minmax([x["media"] for x in lst])
    mT, MT = _minmax([x["tx"] for x in lst])
    for x in lst:
        d = x["deficit"]
        x["Nd"] = None if d is None else ((d / mx if mx else 0) if d >= 0 else d / mn)
        x["Nm"] = None if (x["media"] is None or MM == mM) else (x["media"] - mM) / (MM - mM)
        x["Nt"] = None if (x["tx"] is None or MT == mT) else (x["tx"] - mT) / (MT - mT)
        s = w = 0.0
        if x["Nd"] is not None:
            s += pesos["Nd"] * x["Nd"]; w += pesos["Nd"]
        if x["Nm"] is not None and pesos["Nm"]:
            s += pesos["Nm"] * x["Nm"]; w += pesos["Nm"]
        if x["Nt"] is not None and pesos["Nt"]:
            s += pesos["Nt"] * x["Nt"]; w += pesos["Nt"]
        x["raw"] = s / w if w else None
    rMin, rMax = _minmax([x["raw"] for x in lst])
    for x in lst:
        x["ipco"] = None if (x["raw"] is None or rMax == rMin) else (x["raw"] - rMin) / (rMax - rMin)
    return lst


def classe(ipco, f):
    if ipco is None:
        return "SEM DADO"
    return "ALTA" if ipco >= f["alta"] else ("MÉDIA" if ipco >= f["media"] else "BAIXA")


def situacao(d):
    if d is None:
        return "SEM DADO"
    return "DÉFICIT" if d > 0 else ("SUPERÁVIT" if d < 0 else "EQUILÍBRIO")


def tipo_unidade(nome):
    n = norm(nome)
    S = lambda p: re.search(p, n)
    if S(r"SECRETARIA (JUDICIAL )?(ÚNICA|UNICA)"): return "Secretaria Única Digital"
    if (S(r"TURMA") and S(r"RECURSAL|RECURSAIS")) or S(r"TURMAS RECURSAIS"): return "Turma Recursal"
    if S(r"JUIZADO"): return "Juizado Especial"
    if S(r"CENTRAL"): return "Central de Garantias"
    if S(r"VARA ÚNICA|VARA UNICA"): return "Vara Única"
    if S(r"CRIMINAL|EXECU..ES PENAIS|J[ÚU]RI|ENTORPECENTES|VIOL.NCIA DOM"): return "Vara Criminal / Execução / Violência Doméstica"
    if S(r"FAZENDA P"): return "Vara da Fazenda Pública"
    if S(r"FAM[ÍI]LIA"): return "Vara da Família"
    if S(r"C[ÍI]VEL"): return "Vara Cível"
    if S(r"INF[ÂA]NCIA"): return "Vara da Infância e Juventude"
    if S(r"AGR[ÁA]RIA|SA[ÚU]DE|INTERESSES DIFUSO|AUDITORIA|ESMA"): return "Vara Especializada / Outras"
    if S(r"VARA"): return "Vara de Comarca (competência geral)"
    return "Outras"


def _finalizar(lst, universo, cfg, pesos):
    pontuar(lst, pesos)
    lst.sort(key=lambda x: (-(x["ipco"] or 0), -(x["deficit"] or 0), -(x["media"] or 0)))
    out = []
    for i, x in enumerate(lst, start=1):
        ap = cfg["apoio"].get(f"{universo}|{x['lot']}", {})
        out.append({
            "universo": universo, "rank": i, "lot": x["lot"], "lotFinal": x.get("lotFinal", x["lot"]), "unidade": x["unidade"],
            "comarca": x["comarca"], "entrancia": x["entrancia"], "tipo": tipo_unidade(x["unidade"]),
            "prev": x["prev"], "pre": x["pre"], "deficit": x["deficit"], "situacao": situacao(x["deficit"]),
            "media": x["media"], "tx": x["tx"], "afast": x["afast"], "Nd": x["Nd"], "Nm": x["Nm"], "Nt": x["Nt"],
            "ipco": x["ipco"], "classe": classe(x["ipco"], cfg["faixas"]),
            "semDados": "SIM" if x["media"] is None else "NÃO",
            "recente": "SIM" if x["lot"] in cfg["recentes"] else "NÃO",
            "cargaServidor": (x["media"] / x["pre"]) if (x["media"] is not None and x["pre"]) else None,
            "res": ap.get("res"), "est": ap.get("est"), "solic": ap.get("solic") or "", "grupo": x.get("grupo", ""),
        })
    return out


def processar(rows, cfg_in=None, universo_base="SECRE"):
    cfg = copy.deepcopy(DEFAULT_CFG)
    cfg.update(copy.deepcopy(cfg_in or {}))
    reg, desc = parse_original(rows)
    por_lot = {r["lot"]: r for r in reg}
    # saem da base só as unidades com código do ORIGINAL igual ao da lista SEJUD (lot == lotFinal)
    sej_lots = {s["lot"] for s in cfg["sejud"] if s.get("lotFinal", s["lot"]) == s["lot"]}
    excl, base = [], []
    for r in reg:
        if r["erroFonte"]:
            excl.append({"lot": r["lot"], "unidade": r["unidade"], "motivo": "Erro de fórmula na fonte (#N/A) em Média/Tx — fora do ranking"})
            continue
        if universo_base == "SECRE" and r["lot"] in sej_lots:
            continue
        base.append(copy.deepcopy(r))
    out = _finalizar(base, universo_base, cfg, cfg["pesos"])
    sej = []
    if universo_base == "SECRE":
        for s in cfg["sejud"]:
            o = por_lot.get(s["lot"])
            if not o:
                continue
            ov = s.get("preenchidoOverride")
            sej.append({"lot": s["lot"], "lotFinal": s.get("lotFinal", s["lot"]), "unidade": s.get("unidade") or o["unidade"],
                        "comarca": o["comarca"], "entrancia": o["entrancia"], "prev": cfg["prevSejud"],
                        "pre": o["pre"] if ov is None else ov, "media": o["media"], "tx": o["tx"], "afast": o["afast"],
                        "grupo": s.get("grupo", "")})
        sej = _finalizar(sej, "SEJUD", cfg, cfg["pesosSejud"])
    return {"tratados": out + sej, "excluidas": excl, "descartadas": desc,
            "resumo": {"lidas": len(reg), "base": len(out), "sejud": len(sej), "excluidas": len(excl), "descartadas": len(desc)}}


def _tri(s):
    s = "  " + sem_acento(norm(s)) + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def similaridade(a, b):
    A, B = _tri(a), _tri(b)
    return 2 * len(A & B) / (len(A) + len(B)) if (A or B) else 0.0


def buscar_mask(unidades, comarcas, consulta, limiar=0.35):
    """Busca aproximada (trigramas, sem IA). Retorna lista de booleanos."""
    q = sem_acento(norm(consulta))
    if not q:
        return [True] * len(unidades)
    res = []
    for u, c in zip(unidades, comarcas):
        alvo = sem_acento(norm(f"{u} {c}"))
        res.append(q in alvo or similaridade(q, alvo) >= limiar or similaridade(q, c) >= 0.6)
    return res
