"""MAT-EQUALIZACAO-CRITICIDADE-001 — App pai (Streamlit): Matriz de Criticidade da Equalização da Força de Trabalho (DRH/TJMA)."""
import json, os, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from eq import auth, drive, engine, io as eio, kpis

st.set_page_config(page_title="Matriz de Criticidade — Equalização", page_icon="📊", layout="wide")
auth.gate()

PASTA_DRIVE_PADRAO = "1tbQhF_HoETuN16mxoYP4wuXN-2oFynel"  # EQUALIZACAO_DADOS_MENSAIS (sobrescreva em [drive] folder_id)
NAVY = "#1F3864"
COR = {"ALTA": "#E53935", "MÉDIA": "#FB8C00", "BAIXA": "#43A047", "SEM DADO": "#9E9E9E"}
CFG = json.load(open(os.path.join(os.path.dirname(__file__), "config", "cfg.json"), encoding="utf8"))
NUM = ["prev", "pre", "deficit", "media", "tx", "afast", "Nd", "Nm", "Nt", "ipco", "cargaServidor", "res", "est"]

st.markdown(f"""<style>
h1,h2,h3{{color:{NAVY}}} [data-testid="stMetricValue"]{{color:{NAVY};font-size:1.6rem}}
[data-testid="stMetric"]{{background:#EEF3FA;border-radius:8px;padding:8px 12px}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- processamento (cache)
@st.cache_data(show_spinner="Processando arquivo original…", max_entries=64)
def processar_arquivo(conteudo: bytes, nome: str, tipo: str, cfg_json: str):
    cfg = json.loads(cfg_json)
    rows = eio.ler_matriz(conteudo, nome)
    r = engine.processar(rows, cfg, "GAB" if tipo == "GAB" else "SECRE")
    df = pd.DataFrame(r["tratados"])
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return {"df": df, "resumo": r["resumo"], "excluidas": r["excluidas"], "descartadas": r["descartadas"]}


@st.cache_data(ttl=300, show_spinner="Lendo a pasta do Google Drive…")
def listar_drive(folder_id: str, _chave: str):
    svc = drive.servico(st.secrets["gcp_service_account"])
    return drive.listar(svc, folder_id)


@st.cache_data(ttl=300, show_spinner="Baixando planilha do Drive…", max_entries=48)
def baixar_drive(file_id: str, mime: str, modificado: str):
    svc = drive.servico(st.secrets["gcp_service_account"])
    return drive.baixar(svc, {"id": file_id, "mimeType": mime})


# ---------------------------------------------------------------- barra lateral: fonte de dados
st.sidebar.title("📊 Equalização")
st.sidebar.caption("Matriz de Criticidade · DRH/TJMA")
drive_ok = "gcp_service_account" in st.secrets
PASTA_ID = (st.secrets["drive"].get("folder_id") if "drive" in st.secrets else None) or PASTA_DRIVE_PADRAO
modos = (["Pasta do Google Drive (meses)"] if drive_ok else []) + ["Arrastar arquivo (esta sessão)"]
modo = st.sidebar.radio("Fonte dos dados", modos)
cfg_json = json.dumps(CFG, ensure_ascii=False)
arquivos, rotulo_mes = [], "Sessão atual"

if modo.startswith("Arrastar"):
    tipo_up = st.sidebar.radio("Tipo do arquivo", ["Cargos de Secretaria", "Cargos de Gabinete"], horizontal=False)
    up = st.sidebar.file_uploader("Arquivo ORIGINAL (.xlsx ou .csv)", type=["xlsx", "csv"])
    if up is not None:
        p = drive.parse_nome(up.name)
        rotulo_mes = p["rotulo"] if p else datetime.date.today().strftime("%d/%m/%Y")
        arquivos = [("GAB" if "Gabinete" in tipo_up else "SECRE", up.name, up.getvalue())]
else:
    if st.sidebar.button("↻ Atualizar pasta"):
        st.cache_data.clear()
    try:
        ok, ign = listar_drive(PASTA_ID, "v1")
    except Exception as e:  # noqa
        st.sidebar.error(f"Falha ao ler a pasta do Drive: {e}")
        ok, ign = [], []
    meses = sorted({f["chave"] for f in ok}, reverse=True)
    if not meses:
        st.sidebar.warning("Nenhum arquivo no padrão Mes_AAAA_dados_criticos na pasta.")
    else:
        rot = {f["chave"]: f["rotulo"] for f in ok}
        mes = st.sidebar.selectbox("Mês", meses, format_func=lambda k: rot[k])
        rotulo_mes = rot[mes]
        for f in ok:
            if f["chave"] == mes:
                arquivos.append((f["tipo"], f["name"], baixar_drive(f["id"], f["mimeType"], f["modifiedTime"])))
        st.sidebar.caption(f"{len(meses)} mês(es) disponível(is) na pasta.")
    if ign:
        with st.sidebar.expander(f"{len(ign)} arquivo(s) ignorado(s)"):
            st.write("\n".join(f"• {n}" for n in ign))
            st.caption("Padrão esperado: Outubro_2026_dados_criticos.xlsx")

tx_crit = st.sidebar.slider("Limite de Tx de congestionamento crítica", 0.0, 1.0, float(CFG.get("txCritica", 0.7)), 0.05,
                            help="Parâmetro inicial a validar pelo DRH; usado só no KPI-22.")
auth.logout_button()

st.title("Matriz de Criticidade — Equalização da Força de Trabalho")
if not arquivos:
    st.info("Escolha um mês da pasta do Drive ou arraste o arquivo ORIGINAL (bagunçado) na barra lateral: o app gera painéis, a Matriz de CRITICIDADE organizada, KPIs e relatórios.")
    if not drive_ok:
        st.caption("Pasta do Google Drive ainda não conectada (falta [gcp_service_account] em Secrets). Veja o README, passo 2.")
    with st.expander("Como funciona"):
        st.markdown("""1. O arquivo **original** (sem filtragem) é lido como vem, inclusive `#N/A` e rodapé.  
2. O motor calcula Déficit normalizado, IPCO, classe (ALTA/MÉDIA/BAIXA) e ranking, com as regras validadas contra a Matriz final.  
3. Painéis, dados brutos filtráveis, KPIs e relatórios saem do mesmo tratamento.  
**Padrão na pasta do Drive:** `Mes_AAAA_dados_criticos` (ex.: `Outubro_2026_dados_criticos.xlsx`); gabinete: `..._dados_criticos_gabinete`.""")
    st.stop()

resultados, erros = [], []
for tipo, nome, cont in arquivos:
    try:
        resultados.append(processar_arquivo(cont, nome, tipo, cfg_json))
    except Exception as e:  # noqa
        erros.append(f"{nome}: {e}")
for e in erros:
    st.error(e)
if not resultados:
    st.stop()
DF = pd.concat([r["df"] for r in resultados], ignore_index=True)
EXCL = sum([r["excluidas"] for r in resultados], [])
DESC = sum([r["descartadas"] for r in resultados], [])
st.caption(f"Referência: **{rotulo_mes}** · {len(DF)} registros tratados · universos: {', '.join(DF['universo'].unique())}")

universo = st.selectbox("Universo", list(DF["universo"].unique()), help="SECRE = cargos de secretaria · SEJUD = unidades atendidas pelas Secretarias Judiciais Únicas Digitais · GAB = cargos de gabinete")
D = DF[DF["universo"] == universo].copy()

tab_pain, tab_dados, tab_mat, tab_kpi, tab_rel, tab_exp, tab_q = st.tabs(["📊 Painéis", "🗂️ Dados brutos", "🧾 Matriz organizada", "📘 KPIs", "📄 Relatório", "📥 Exportação", "🔎 Qualidade"])
SUF = f"{rotulo_mes.replace('/', '-').replace(' ', '_')}"
X = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ---------------------------------------------------------------- PAINÉIS
with tab_pain:
    v = lambda k: kpis.valor(D, k, tx_crit)
    f = lambda k: kpis.formatar(v(k), next(c[9] for c in kpis.CATALOGO if c[0] == k))
    cards = [("Unidades", "KPI-01"), ("Quadro previsto", "KPI-02"), ("Preenchidos", "KPI-03"), ("Taxa de preenchimento", "KPI-04"), ("Déficit bruto", "KPI-05"), ("Superávit", "KPI-06"),
             ("Saldo líquido", "KPI-07"), ("% unid. em déficit", "KPI-08"), ("IPCO médio", "KPI-09"), ("Tx cong. média", "KPI-10"), ("Carga/servidor", "KPI-12"), ("Unid. ALTA", "KPI-20"),
             ("Residentes", "KPI-13"), ("Estagiários", "KPI-14"), ("Unid. c/ afastado >60d", "KPI-23"), ("ALTA sem residente", "KPI-24"), ("Unid. com superávit", "KPI-25"), ("Sem dados estat.", "KPI-26")]
    for i in range(0, len(cards), 6):
        cols = st.columns(6)
        for c, (lab, k) in zip(cols, cards[i:i + 6]):
            c.metric(lab, f(k))

    def layout(fig, h=340):
        fig.update_layout(height=h, margin=dict(l=10, r=10, t=45, b=10), title_font_size=14, plot_bgcolor="white", legend_title_text="")
        return fig

    st.subheader("Indicadores quantitativos")
    ent_ord = ["Inicial", "Intermediária", "Final"]
    g = D.groupby("entrancia").agg(prev=("prev", "sum"), pre=("pre", "sum"), deficit=("deficit", "sum"), ipco=("ipco", "mean"), tx=("tx", "mean"), n=("lot", "count")).reindex(ent_ord).dropna(how="all").reset_index()
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure([go.Bar(name="Prevista", x=g["entrancia"], y=g["prev"], marker_color=NAVY), go.Bar(name="Preenchido", x=g["entrancia"], y=g["pre"], marker_color="#7FA3D6")])
        fig.update_layout(barmode="group", title="Quadro previsto × preenchido por entrância"); st.plotly_chart(layout(fig), use_container_width=True)
    with c2:
        top = D.sort_values("rank").head(15).copy(); top["rot"] = top["unidade"].str[:38] + " · " + top["comarca"].str[:18]
        fig = px.bar(top.iloc[::-1], x="ipco", y="rot", orientation="h", color="classe", color_discrete_map=COR, title="Top 15 unidades por IPCO", labels={"ipco": "IPCO", "rot": ""})
        st.plotly_chart(layout(fig, 420), use_container_width=True)
    c3, c4 = st.columns(2)
    with c3:
        fig = px.histogram(D.dropna(subset=["ipco"]), x="ipco", nbins=10, range_x=[0, 1], color_discrete_sequence=[NAVY], title="Distribuição do IPCO (faixas de 0,1)", labels={"ipco": "IPCO"})
        st.plotly_chart(layout(fig), use_container_width=True)
    with c4:
        com = D[D["deficit"] > 0].groupby("comarca")["deficit"].sum().sort_values(ascending=False).head(15).iloc[::-1].reset_index()
        fig = px.bar(com, x="deficit", y="comarca", orientation="h", color_discrete_sequence=[NAVY], title="Top 15 comarcas — déficit bruto de cargos", labels={"deficit": "Déficit bruto", "comarca": ""})
        st.plotly_chart(layout(fig, 420), use_container_width=True)
    c5, c6 = st.columns(2)
    with c5:
        ap = D.groupby("classe")[["res", "est"]].sum().reindex(["ALTA", "MÉDIA", "BAIXA"]).fillna(0).reset_index()
        fig = go.Figure([go.Bar(name="Residentes", x=ap["classe"], y=ap["res"], marker_color=NAVY), go.Bar(name="Estagiários", x=ap["classe"], y=ap["est"], marker_color="#7FA3D6")])
        fig.update_layout(barmode="stack", title="Residentes e estagiários por classe de criticidade"); st.plotly_chart(layout(fig), use_container_width=True)
    with c6:
        fig = px.scatter(D.dropna(subset=["media", "deficit"]), x="media", y="deficit", color="classe", color_discrete_map=COR, hover_data=["unidade", "comarca", "ipco"],
                         title="Déficit × média de casos novos", labels={"media": "Média de casos novos", "deficit": "Déficit"})
        st.plotly_chart(layout(fig), use_container_width=True)

    st.subheader("Indicadores qualitativos")
    q1, q2 = st.columns(2)
    with q1:
        cl = D["classe"].value_counts().reindex(["ALTA", "MÉDIA", "BAIXA", "SEM DADO"]).dropna().reset_index()
        fig = px.pie(cl, names="classe", values="count", hole=0.5, color="classe", color_discrete_map=COR, title="Unidades por classe de criticidade")
        st.plotly_chart(layout(fig), use_container_width=True)
    with q2:
        sit = D["situacao"].value_counts().reindex(["DÉFICIT", "EQUILÍBRIO", "SUPERÁVIT"]).dropna().reset_index()
        fig = px.bar(sit, x="situacao", y="count", color="situacao", color_discrete_map={"DÉFICIT": "#E53935", "EQUILÍBRIO": "#9E9E9E", "SUPERÁVIT": "#43A047"}, title="Unidades por situação", labels={"situacao": "", "count": "Unidades"})
        fig.update_layout(showlegend=False); st.plotly_chart(layout(fig), use_container_width=True)
    q3, q4 = st.columns(2)
    with q3:
        fig = px.bar(g, x="entrancia", y="ipco", color_discrete_sequence=[NAVY], title="IPCO médio por entrância", labels={"entrancia": "", "ipco": "IPCO médio"})
        st.plotly_chart(layout(fig), use_container_width=True)
    with q4:
        fig = px.bar(g, x="entrancia", y="deficit", color_discrete_sequence=["#7FA3D6"], title="Déficit líquido por entrância", labels={"entrancia": "", "deficit": "Déficit líquido"})
        st.plotly_chart(layout(fig), use_container_width=True)
    tp = D.groupby("tipo").agg(unidades=("lot", "count"), deficit_bruto=("deficit", lambda s: s[s > 0].sum())).sort_values("unidades").reset_index()
    q5, q6 = st.columns(2)
    with q5:
        st.plotly_chart(layout(px.bar(tp, x="unidades", y="tipo", orientation="h", color_discrete_sequence=[NAVY], title="Unidades por tipo de unidade", labels={"tipo": ""}), 420), use_container_width=True)
    with q6:
        st.plotly_chart(layout(px.bar(tp.sort_values("deficit_bruto"), x="deficit_bruto", y="tipo", orientation="h", color_discrete_sequence=["#E53935"], title="Déficit bruto por tipo de unidade", labels={"tipo": "", "deficit_bruto": "Déficit bruto"}), 420), use_container_width=True)

    if modo.startswith("Pasta") and drive_ok:
        st.subheader("Evolução mensal (universo SECRE)")
        if st.toggle("Comparar todos os meses da pasta"):
            linhas = []
            for f_ in [x for x in ok if x["tipo"] == "SECRE"]:
                r_ = processar_arquivo(baixar_drive(f_["id"], f_["mimeType"], f_["modifiedTime"]), f_["name"], "SECRE", cfg_json)
                d_ = r_["df"][r_["df"]["universo"] == "SECRE"]
                linhas.append({"mes": f_["rotulo"], "chave": f_["chave"], "Taxa de preenchimento": kpis.valor(d_, "KPI-04"), "Déficit bruto": kpis.valor(d_, "KPI-05"),
                               "Unidades ALTA": kpis.valor(d_, "KPI-20"), "IPCO médio": kpis.valor(d_, "KPI-09")})
            ev = pd.DataFrame(linhas).sort_values("chave")
            if len(ev) < 2:
                st.info("É preciso ao menos 2 meses na pasta para comparar.")
            else:
                for m_ in ["Taxa de preenchimento", "Déficit bruto", "Unidades ALTA", "IPCO médio"]:
                    st.plotly_chart(layout(px.line(ev, x="mes", y=m_, markers=True, title=m_, color_discrete_sequence=[NAVY]), 260), use_container_width=True)

# ---------------------------------------------------------------- DADOS BRUTOS
with tab_dados:
    st.caption("Dados tratados — 100% dos registros do universo, com filtros. Números são numéricos (não texto).")
    a, b, c, d = st.columns(4)
    fc = a.multiselect("Classe", ["ALTA", "MÉDIA", "BAIXA", "SEM DADO"])
    fe = b.multiselect("Entrância", sorted(D["entrancia"].dropna().unique()))
    fs = c.multiselect("Situação", ["DÉFICIT", "EQUILÍBRIO", "SUPERÁVIT"])
    ft = d.multiselect("Tipo de unidade", sorted(D["tipo"].unique()))
    e1, e2 = st.columns([2, 1])
    fco = e1.multiselect("Comarca", sorted(D["comarca"].unique()))
    busca = e2.text_input("Busca aproximada (unidade/comarca)", help="Tolera erro de digitação (similaridade de trigramas; não é IA).")
    ipr = st.slider("Faixa de IPCO", 0.0, 1.0, (0.0, 1.0), 0.01)
    m = pd.Series(True, index=D.index)
    for col, sel in (("classe", fc), ("entrancia", fe), ("situacao", fs), ("tipo", ft), ("comarca", fco)):
        if sel: m &= D[col].isin(sel)
    m &= D["ipco"].between(*ipr) | D["ipco"].isna() & (ipr == (0.0, 1.0))
    if busca: m &= pd.Series(engine.buscar_mask(D["unidade"].tolist(), D["comarca"].tolist(), busca), index=D.index)
    F = D[m]
    st.write(f"**{len(F)}** de {len(D)} registros")
    show = eio.df_rotulado(F)
    st.dataframe(show, use_container_width=True, height=520, hide_index=True,
                 column_config={"Tx congestionamento": st.column_config.NumberColumn(format="percent"), "IPCO [0-1]": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.3f"),
                                "N_Déficit": st.column_config.NumberColumn(format="%.4f"), "N_Média": st.column_config.NumberColumn(format="%.4f"), "N_TxCong": st.column_config.NumberColumn(format="%.4f")})
    x1, x2, x3, x4 = st.columns(4)
    x1.download_button("⬇ XLSX (filtrado)", eio.xlsx_bytes(show, "Dados"), f"dados_tratados_{universo}_{SUF}.xlsx", X)
    x2.download_button("⬇ CSV UTF-8 (filtrado)", eio.csv_utf8(show), f"dados_tratados_{universo}_{SUF}.csv", "text/csv; charset=utf-8")
    x3.download_button("⬇ HTML (filtrado)", eio.html_tabela(show, f"Dados tratados — {universo}", f"Referência: {rotulo_mes}"), f"dados_tratados_{universo}_{SUF}.html", "text/html; charset=utf-8")
    x4.download_button("⬇ PDF (filtrado)", eio.pdf_bytes(f"Dados tratados — {universo}", f"Referência: {rotulo_mes} · {len(F)} unidades", show), f"dados_tratados_{universo}_{SUF}.pdf", "application/pdf", disabled=F.empty)

# ---------------------------------------------------------------- MATRIZ ORGANIZADA
with tab_mat:
    st.caption("A planilha bagunçada vira a Matriz de CRITICIDADE organizada: mesmo layout do arquivo final (ordenada por IPCO, cores por classe, negrito para residente/estagiário, cinza sem dados, legenda).")
    nomes = {"SECRE": "IPCO - Rank Criticidade - SECRE", "GAB": "IPCO - Rank Criticidade - GAB", "SEJUD": "Unidades Atendidas SEJUD"}
    disp = [u for u in nomes if u in set(DF["universo"])]
    abas = st.tabs([nomes[u] for u in disp])
    corcl = {"ALTA": "background-color:#FF4444;color:white;font-weight:bold", "MÉDIA": "background-color:#FFA500;color:white;font-weight:bold", "BAIXA": "background-color:#5CB85C;color:white;font-weight:bold"}
    for a_, u in zip(abas, disp):
        with a_:
            v_ = eio.df_rotulado(DF[DF["universo"] == u].sort_values("rank")).drop(columns=["Universo"])
            sty = v_.style.map(lambda c: corcl.get(c, ""), subset=["Classe"]).format({"Tx congestionamento": "{:.2%}", "IPCO [0-1]": "{:.4f}", "N_Déficit": "{:+.4f}", "N_Média": "{:.4f}", "N_TxCong": "{:.4f}"}, na_rep="—")
            st.dataframe(sty, use_container_width=True, hide_index=True, height=520)
    m1, m2, m3 = st.columns(3)
    m1.download_button("⬇ Matriz organizada (XLSX)", eio.matriz_formatada(DF), f"Matriz_de_CRITICIDADE_{SUF}.xlsx", X, type="primary")
    m2.download_button("⬇ Matriz organizada (PDF)", eio.matriz_pdf(DF, rotulo_mes), f"Matriz_de_CRITICIDADE_{SUF}.pdf", "application/pdf")
    m3.download_button("⬇ Matriz organizada (HTML)", eio.html_matriz(DF, rotulo_mes), f"Matriz_de_CRITICIDADE_{SUF}.html", "text/html; charset=utf-8")

# ---------------------------------------------------------------- KPIs
with tab_kpi:
    st.caption("O que cada indicador mede, por que existe e o que pede desempenhar. Valor calculado para o universo e mês selecionados. Metas: definir com o DRH.")
    tab = pd.DataFrame([{"ID": k[0], "Indicador": k[1], "Tipo": k[2], "Crítico": "SIM" if k[3] else "", "Definição / regra": k[4], "Colunas-fonte": k[5], "Por que existe": k[6],
                         "O que pede medir / desempenhar": k[7], "Sentido": k[8], "Valor atual": kpis.formatar(kpis.valor(D, k[0], tx_crit), k[9])} for k in kpis.CATALOGO])
    st.dataframe(tab, use_container_width=True, hide_index=True, height=700)
    st.download_button("⬇ Catálogo de KPIs (XLSX)", eio.xlsx_bytes(tab, "KPIs"), "catalogo_kpis.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------------- RELATÓRIO
with tab_rel:
    crit = {f"{k[0]} — {k[1]}": k for k in kpis.CRITICOS}
    esc = st.selectbox("Indicador crítico", list(crit))
    k = crit[esc]
    R = kpis.selecionar(D, k[0], tx_crit).sort_values("rank")
    st.markdown(f"**{k[1]}** — {k[4]}. *Objetivo:* {k[7]}.")
    st.metric("Unidades listadas", len(R)); 
    rel = eio.df_rotulado(R)
    st.dataframe(rel, use_container_width=True, hide_index=True, height=420)
    nome_base = f"Relatorio_{k[0]}_{universo}_{SUF}"
    r1, r2, r3, r4 = st.columns(4)
    r1.download_button("⬇ PDF", eio.pdf_bytes(f"{k[0]} — {k[1]}", f"Universo {universo} · {rotulo_mes} · {len(R)} unidades · emitido em {datetime.date.today():%d/%m/%Y}", rel) if len(R) else b"", nome_base + ".pdf", "application/pdf", disabled=R.empty)
    r2.download_button("⬇ HTML", eio.html_tabela(rel, f"{k[0]} — {k[1]}", f"Universo {universo} · {rotulo_mes}", [("Unidades listadas", len(R))], k[4]), nome_base + ".html", "text/html; charset=utf-8")
    r3.download_button("⬇ XLSX", eio.xlsx_bytes(rel, "Relatório"), nome_base + ".xlsx", X)
    r4.download_button("⬇ CSV UTF-8", eio.csv_utf8(rel), nome_base + ".csv", "text/csv; charset=utf-8")

# ---------------------------------------------------------------- EXPORTAÇÃO
with tab_exp:
    st.caption("Central de exportação — PDF, HTML (CSS3 autônomo), XLSX e CSV em UTF-8 (Unicode). Referência: " + rotulo_mes)
    st.markdown("**Matriz de CRITICIDADE organizada** (todos os universos do arquivo)")
    e1, e2, e3 = st.columns(3)
    e1.download_button("⬇ XLSX", eio.matriz_formatada(DF), f"Matriz_de_CRITICIDADE_{SUF}.xlsx", X, key="e_x")
    e2.download_button("⬇ PDF", eio.matriz_pdf(DF, rotulo_mes), f"Matriz_de_CRITICIDADE_{SUF}.pdf", "application/pdf", key="e_p")
    e3.download_button("⬇ HTML", eio.html_matriz(DF, rotulo_mes), f"Matriz_de_CRITICIDADE_{SUF}.html", "text/html; charset=utf-8", key="e_h")
    st.markdown(f"**Dados tratados — universo {universo}** (sem filtros)")
    full = eio.df_rotulado(D.sort_values("rank"))
    f1, f2, f3, f4 = st.columns(4)
    f1.download_button("⬇ XLSX", eio.xlsx_bytes(full, "Dados"), f"dados_tratados_{universo}_{SUF}.xlsx", X, key="f_x")
    f2.download_button("⬇ CSV UTF-8", eio.csv_utf8(full), f"dados_tratados_{universo}_{SUF}.csv", "text/csv; charset=utf-8", key="f_c")
    f3.download_button("⬇ HTML", eio.html_tabela(full, f"Dados tratados — {universo}", f"Referência: {rotulo_mes}"), f"dados_tratados_{universo}_{SUF}.html", "text/html; charset=utf-8", key="f_h")
    f4.download_button("⬇ PDF", eio.pdf_bytes(f"Dados tratados — {universo}", f"Referência: {rotulo_mes} · {len(full)} unidades", full), f"dados_tratados_{universo}_{SUF}.pdf", "application/pdf", key="f_p")
    st.markdown("**Relatórios por KPI crítico** (aba 📄 Relatório): PDF · HTML · XLSX · CSV UTF-8. **Catálogo de KPIs:** aba 📘 KPIs.")

# ---------------------------------------------------------------- QUALIDADE
with tab_q:
    rs = [r["resumo"] for r in resultados]
    st.write({"unidades lidas": sum(r["lidas"] for r in rs), "base": sum(r["base"] for r in rs), "SEJUD": sum(r["sejud"] for r in rs), "excluídas (erro na fonte)": sum(r["excluidas"] for r in rs), "linhas de rodapé descartadas": sum(r["descartadas"] for r in rs)})
    st.markdown("**Excluídas do ranking (erro de fórmula na fonte)**")
    st.dataframe(pd.DataFrame(EXCL), hide_index=True, use_container_width=True)
    st.markdown("**Linhas descartadas (totais/rodapé/anotações)**")
    st.dataframe(pd.DataFrame(DESC), hide_index=True, use_container_width=True)
    st.markdown("**Unidades sem dados estatísticos (IPCO com menor confiança)**")
    st.dataframe(eio.df_rotulado(DF[DF["semDados"] == "SIM"]), hide_index=True, use_container_width=True)
