# MAT-EQUALIZACAO-CRITICIDADE-001 — App pai (Streamlit)

Matriz de Criticidade da Equalização da Força de Trabalho (DRH/TJMA): o arquivo **original** (sem filtragem) vira dado **tratado**, painéis, KPIs e relatórios.

## Fase 1 — arrastar o arquivo (funciona só com o login)
1. Suba esta pasta para um repositório **privado** no GitHub (`config/cfg.json` contém números de processos administrativos de residentes/estagiários).
2. Em share.streamlit.io: *New app* → repositório → arquivo principal `app.py`.
3. *Settings → Secrets*: cole o conteúdo de `.streamlit/secrets.toml.example` e troque o hash:
   `python tools/gerar_hash.py "SUA-SENHA"` → cole em `password_sha256`. Login: `equalizacao`.
   Sem o bloco `[auth]` o app **não abre** (não existe senha padrão no código).
4. Abra o app, entre e arraste o original (`.xlsx` ou `.csv`) na barra lateral. Escolha *Cargos de Secretaria* ou *Cargos de Gabinete*.

## Fase 2 — pasta do Google Drive com meses
1. Crie uma pasta no Drive. Padrão de nome dos arquivos: **`Mes_AAAA_dados_criticos`** (ex.: `Outubro_2026_dados_criticos.xlsx`).
   Gabinete: `Outubro_2026_dados_criticos_gabinete.xlsx`. Aceita `.xlsx`, `.csv` e Planilha Google nativa; mês por extenso, abreviado ou numérico (`10_2026_...`); acentos e maiúsculas são ignorados.
2. Google Cloud → crie um projeto → ative a **Google Drive API** → crie uma **conta de serviço** → gere a chave JSON.
3. **Compartilhe a pasta** com o e-mail da conta de serviço (papel Leitor).
4. Em Secrets, acrescente `[drive] folder_id` (trecho final da URL da pasta) e `[gcp_service_account]` (campos do JSON).
5. O app passa a mostrar a opção *Pasta do Google Drive (meses)*: cada arquivo novo vira um mês selecionável; em duplicidade vale o mais recente; arquivos fora do padrão ficam listados como ignorados. Cache de 5 min (botão ↻ Atualizar pasta).

## O que o app entrega
Painéis (18 cartões + 12 gráficos, quantitativos e qualitativos, evolução mensal) · Dados brutos com filtros e busca aproximada · Catálogo de 26 KPIs com valor atual · Relatório por KPI crítico (PDF/XLSX/CSV) · Qualidade (rodapé, N/A, sem dados) · Download da **Matriz de CRITICIDADE formatada** (mesmo layout do arquivo final).

## Regras do motor (validadas contra a Matriz final)
Déficit em escala bipartida; Média e Tx min–máx; IPCO = média ponderada 60/30/10 (SEJUD 50/50) dos componentes disponíveis, reescalonada [0,1]; ALTA ≥ 0,70 · MÉDIA ≥ 0,40 · BAIXA < 0,40.
Parâmetros em `config/cfg.json`: lista SEJUD, recentes e residentes/estagiários por unidade (vêm do arquivo final; atualize quando mudarem).

## Testes
`pytest tests -q` (paridade com o motor JS: defina `EQ_ORIG_ROWS` e `EQ_JS_OUT`).
