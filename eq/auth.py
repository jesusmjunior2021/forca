"""Login e senha (salvaguarda inicial). Credenciais ficam em st.secrets — nunca no código nem no repositório."""
import hashlib, hmac, time
import streamlit as st


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def gate():
    """Bloqueia o app até login válido. Sem [auth] em secrets, o app NÃO abre (não há senha padrão)."""
    if st.session_state.get("auth_ok"):
        return
    cfg = st.secrets.get("auth") if hasattr(st, "secrets") else None
    st.markdown("### 🔒 Equalização da Força de Trabalho — acesso restrito")
    if not cfg or "user" not in cfg or "password_sha256" not in cfg:
        st.error("Credenciais não configuradas. Defina [auth] user e password_sha256 em Secrets (ver README).")
        st.stop()
    tent = st.session_state.get("tentativas", 0)
    if tent >= 5:
        st.error("Muitas tentativas nesta sessão. Feche e reabra a página.")
        st.stop()
    with st.form("login"):
        u = st.text_input("Login")
        p = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        good = hmac.compare_digest(u.strip().lower(), str(cfg["user"]).lower()) & hmac.compare_digest(_sha(p), str(cfg["password_sha256"]).lower())
        if good:
            st.session_state["auth_ok"] = True
            st.session_state["tentativas"] = 0
            st.rerun()
        st.session_state["tentativas"] = tent + 1
        time.sleep(1.5)
        st.error("Login ou senha inválidos.")
    st.stop()


def logout_button():
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()
