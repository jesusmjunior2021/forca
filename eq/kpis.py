"""Catálogo de KPIs (mesmo da aba 3_KPIs da planilha-raiz) e cálculo sobre um DataFrame de um universo."""
import pandas as pd

# (id, nome, tipo, crítico, definição, colunas-fonte, por que existe, o que pede desempenhar, sentido, formato)
CATALOGO = [
 ("KPI-01","Unidades no universo","Quant",False,"Contagem de unidades do universo selecionado","Lotação","Dimensiona a base analisada","Confirmar que 100% das unidades foram carregadas","—","int"),
 ("KPI-02","Quadro previsto (cargos)","Quant",False,"Σ Prevista","Prevista","Referência de lotação ideal","Comparar com o efetivo real","—","int"),
 ("KPI-03","Cargos preenchidos","Quant",False,"Σ Preenchido","Preenchido","Efetivo real em exercício","Acompanhar a força de trabalho efetiva","↑","int"),
 ("KPI-04","Taxa de preenchimento","Quant",False,"Σ Preenchido ÷ Σ Prevista","Prevista, Preenchido","Mostra a cobertura do quadro","Aproximar de 100% respeitando o equilíbrio entre unidades","↑","pct"),
 ("KPI-05","Déficit bruto (falta)","Quant",False,"Σ Déficit das unidades com Déficit > 0","Déficit","Volume de cargos a suprir","Dimensionar necessidade de provimento/remoção","↓","int"),
 ("KPI-06","Superávit (excedente)","Quant",False,"Σ |Déficit| das unidades com Déficit < 0","Déficit","Volume de cargos excedentes ao quadro","Identificar fonte de remanejamento (equalização)","—","int"),
 ("KPI-07","Saldo líquido","Quant",False,"Σ Déficit (falta − sobra)","Déficit","Resultado global da equalização","Medir quanto falta após remanejar excedentes","↓","int"),
 ("KPI-08","% de unidades em déficit","Quant",False,"Unidades com Déficit > 0 ÷ unidades","Déficit","Abrangência do problema","Reduzir a proporção de unidades com falta","↓","pct"),
 ("KPI-09","IPCO médio","Quant",False,"Média do IPCO [0-1] (60% Déficit + 30% Média de casos + 10% Tx cong.; SEJUD 50/50)","IPCO","Síntese de criticidade operacional","Acompanhar a tendência geral de criticidade","↓","dec3"),
 ("KPI-10","Taxa de congestionamento média","Quant",False,"Média simples da Tx congestionamento","Tx Congestionamento","Mede acúmulo processual","Priorizar unidades com fila alta","↓","pct"),
 ("KPI-11","Média de casos novos por unidade","Quant",False,"Média da Média de Distribuição de Casos Novos","Média Casos Novos","Demanda de entrada","Ajustar força de trabalho à demanda","—","int"),
 ("KPI-12","Carga por servidor preenchido","Quant",False,"Casos novos ÷ Preenchido (média)","Média Casos Novos, Preenchido","Normaliza a demanda pelo efetivo real","Comparar unidades de porte distinto","↓","dec1"),
 ("KPI-13","Residentes alocados","Quant",False,"Σ Residentes","Residentes","Apoio adicional em cada unidade","Direcionar apoio às unidades ALTA","—","int"),
 ("KPI-14","Estagiários alocados","Quant",False,'Σ Estagiários ("—" = vazio)',"Estagiários","Apoio adicional em cada unidade","Direcionar apoio às unidades ALTA","—","int"),
 ("KPI-15","Distribuição por classe de criticidade","Qual",False,"Contagem por ALTA / MÉDIA / BAIXA (IPCO ≥0,70 / ≥0,40 / <0,40)","IPCO","Priorização visual","Concentrar ação na classe ALTA","—","txt"),
 ("KPI-16","Distribuição por situação","Qual",False,"Déficit / Equilíbrio / Superávit","Déficit","Mostra onde falta e onde sobra","Equalizar","—","txt"),
 ("KPI-17","Distribuição por entrância","Qual",False,"Inicial / Intermediária / Final","Entrância","Recorte de porte da comarca","Comparar cobertura entre entrâncias","—","txt"),
 ("KPI-18","Distribuição por tipo de unidade","Qual",False,"Tipo derivado do nome (Vara Única, Juizado, Turma Recursal...)","Unidade / Vara","Recorte funcional","Identificar tipos mais deficitários","—","txt"),
 ("KPI-19","Unidades sem dados estatísticos / recentes","Qual",False,"Média de casos novos ausente ou unidade instalada recentemente","Média Casos Novos","Sinaliza IPCO com menor confiança","Completar dados antes de decidir","↓","int"),
 ("KPI-20","Unidades de criticidade ALTA","Quant",True,"Unidades com IPCO ≥ 0,70","IPCO, Classe","Lista de ação prioritária","Suprir/remanejar primeiro","↓","int"),
 ("KPI-21","Unidades em déficit (falta)","Quant",True,"Unidades com Déficit > 0","Déficit","Lista de unidades que precisam de servidores","Provimento/remoção","↓","int"),
 ("KPI-22","Unidades com congestionamento crítico","Quant",True,"Unidades com Tx cong. ≥ limite (parâmetro)","Tx Congestionamento","Fila processual elevada","Investigar causa (pessoal x demanda)","↓","int"),
 ("KPI-23","Unidades com servidor afastado > 60 dias","Quant",True,"Unidades com Afastados >60d > 0","Servidores afastados > 60d","Déficit oculto por afastamento","Repor/avaliar substituição","↓","int"),
 ("KPI-24","Unidades ALTA sem residente","Quant",True,"Classe ALTA e Residentes = 0","Classe, Residentes","Criticidade sem apoio alocado","Direcionar residentes/estagiários","↓","int"),
 ("KPI-25","Unidades com superávit (excedente)","Quant",True,"Unidades com Déficit < 0","Déficit","Candidatas a ceder cargos","Remanejamento para unidades ALTA","—","int"),
 ("KPI-26","Unidades sem dados estatísticos","Qual",True,"Média de casos novos ausente","Média Casos Novos","Ranking com menor confiança","Regularizar a fonte","↓","int"),
]
CRITICOS = [k for k in CATALOGO if k[3]]


def selecionar(df: pd.DataFrame, kpi_id: str, tx_critica: float = 0.70) -> pd.DataFrame:
    """Unidades que compõem um KPI crítico (mesmas regras da aba 4_RELATORIO)."""
    if kpi_id == "KPI-20": m = df["classe"] == "ALTA"
    elif kpi_id == "KPI-21": m = df["deficit"] > 0
    elif kpi_id == "KPI-22": m = df["tx"].notna() & (df["tx"] >= tx_critica)
    elif kpi_id == "KPI-23": m = df["afast"].fillna(0) > 0
    elif kpi_id == "KPI-24": m = (df["classe"] == "ALTA") & (df["res"].fillna(0) == 0)
    elif kpi_id == "KPI-25": m = df["deficit"] < 0
    elif kpi_id == "KPI-26": m = df["semDados"] == "SIM"
    else: raise KeyError(kpi_id)
    return df[m.fillna(False)]


def _s(df, c): return float(pd.to_numeric(df[c], errors="coerce").fillna(0).sum())
def _m(df, c):
    v = pd.to_numeric(df[c], errors="coerce").dropna()
    return float(v.mean()) if len(v) else 0.0


def valor(df: pd.DataFrame, kpi_id: str, tx_critica: float = 0.70):
    n = len(df)
    if kpi_id == "KPI-01": return n
    if kpi_id == "KPI-02": return _s(df, "prev")
    if kpi_id == "KPI-03": return _s(df, "pre")
    if kpi_id == "KPI-04": return _s(df, "pre") / _s(df, "prev") if _s(df, "prev") else 0.0
    d = pd.to_numeric(df["deficit"], errors="coerce")
    if kpi_id == "KPI-05": return float(d[d > 0].sum())
    if kpi_id == "KPI-06": return float(-d[d < 0].sum())
    if kpi_id == "KPI-07": return float(d.sum())
    if kpi_id == "KPI-08": return float((d > 0).sum() / n) if n else 0.0
    if kpi_id == "KPI-09": return _m(df, "ipco")
    if kpi_id == "KPI-10": return _m(df, "tx")
    if kpi_id == "KPI-11": return _m(df, "media")
    if kpi_id == "KPI-12": return _m(df, "cargaServidor")
    if kpi_id == "KPI-13": return _s(df, "res")
    if kpi_id == "KPI-14": return _s(df, "est")
    if kpi_id == "KPI-15": return " · ".join(f"{k} {v}" for k, v in df["classe"].value_counts().items())
    if kpi_id == "KPI-16": return " · ".join(f"{k} {v}" for k, v in df["situacao"].value_counts().items())
    if kpi_id == "KPI-17": return " · ".join(f"{k} {v}" for k, v in df["entrancia"].value_counts().items())
    if kpi_id == "KPI-18": return " · ".join(f"{k} {v}" for k, v in df["tipo"].value_counts().head(4).items()) + " …"
    if kpi_id == "KPI-19": return int((df["semDados"] == "SIM").sum())
    return len(selecionar(df, kpi_id, tx_critica))


def formatar(v, fmt):
    if fmt == "int": return f"{v:,.0f}".replace(",", ".")
    if fmt == "pct": return f"{v*100:.1f}%".replace(".", ",")
    if fmt == "dec3": return f"{v:.3f}".replace(".", ",")
    if fmt == "dec1": return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(v)
