"""Pasta do Google Drive = fonte mensal. Padrão de nome: <Mes>_<AAAA>_<titulo>  (ex.: Outubro_2026_dados_criticos.xlsx)."""
import io, re, unicodedata

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
         "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
NOME_MES = {v: k.capitalize() for k, v in list(MESES.items())[:12]}
NOME_MES[3] = "Março"
TIPOS = {"dados_criticos": "SECRE", "dados_criticos_secretaria": "SECRE", "dados_criticos_gabinete": "GAB"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GSHEET = "application/vnd.google-apps.spreadsheet"


def _flat(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-]+", "_", s.strip().lower())


def parse_nome(nome: str):
    """'Outubro_2026_dados_críticos.xlsx' -> {'ano':2026,'mes':10,'tipo':'SECRE','chave':'2026-10'}; None se fora do padrão."""
    stem = re.sub(r"\.(xlsx|csv|xls)$", "", nome.strip(), flags=re.I)
    m = re.match(r"^(?P<mes>[a-zA-ZÀ-ÿ]+|\d{1,2})_(?P<ano>\d{4})_(?P<tit>.+)$", _flat(stem))
    if not m:
        return None
    mes = m["mes"]
    mes = int(mes) if mes.isdigit() else MESES.get(mes)
    tipo = TIPOS.get(m["tit"].strip("_"))
    if not mes or not 1 <= mes <= 12 or not tipo:
        return None
    return {"ano": int(m["ano"]), "mes": mes, "tipo": tipo, "chave": f"{int(m['ano'])}-{mes:02d}", "rotulo": f"{NOME_MES[mes]}/{m['ano']}"}


def servico(info: dict):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    cred = service_account.Credentials.from_service_account_info(dict(info), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=cred, cache_discovery=False)


def listar(svc, folder_id: str):
    """Lista arquivos da pasta. Retorna (reconhecidos, ignorados). Em duplicidade (mesmo mês/tipo) vale o mais recente."""
    itens, tok = [], None
    while True:
        r = svc.files().list(q=f"'{folder_id}' in parents and trashed=false", pageToken=tok, pageSize=200, supportsAllDrives=True,
                             includeItemsFromAllDrives=True, fields="nextPageToken, files(id,name,mimeType,modifiedTime)").execute()
        itens += r.get("files", [])
        tok = r.get("nextPageToken")
        if not tok:
            break
    ok, ign, melhor = [], [], {}
    for f in itens:
        p = parse_nome(f["name"]) if f["mimeType"] in (XLSX, GSHEET, "text/csv") else None
        if not p:
            ign.append(f["name"]); continue
        f = {**f, **p}
        k = (p["chave"], p["tipo"])
        if k not in melhor or f["modifiedTime"] > melhor[k]["modifiedTime"]:
            if k in melhor: ign.append(melhor[k]["name"] + " (substituído por versão mais recente)")
            melhor[k] = f
        else:
            ign.append(f["name"] + " (versão mais antiga)")
    ok = sorted(melhor.values(), key=lambda f: (f["chave"], f["tipo"]))
    return ok, ign


def baixar(svc, f) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    req = svc.files().export_media(fileId=f["id"], mimeType=XLSX) if f["mimeType"] == GSHEET else svc.files().get_media(fileId=f["id"], supportsAllDrives=True)
    buf = io.BytesIO(); dl = MediaIoBaseDownload(buf, req); done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()
