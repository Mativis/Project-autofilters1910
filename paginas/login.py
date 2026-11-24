"""
Login do Visualfil Cloud
------------------------
Tela de autenticação contra o backend online (Google Sheets / Apps Script).
"""
import streamlit as st

import nuvem as cloud

st.set_page_config(page_title="Entrar — Visualfil", page_icon="🔐", layout="centered")
st.title("🔐 Visualfil — Acesso")

if cloud.logado():
    u = cloud.usuario_atual()
    st.success(f"Conectado como **{u.get('nome', u.get('usuario'))}**"
               + (" · administrador" if u.get("admin") else ""))
    if st.button("Sair"):
        cloud.logout()
        st.rerun()
else:
    st.caption(
        "Informe a URL do Web App do Visualfil Cloud e suas credenciais. "
        "Os campos abaixo também podem vir de `st.secrets` / variáveis de ambiente."
    )
    with st.form("form_login"):
        url = st.text_input(
            "URL do Web App (…/exec)",
            value=cloud.url(),
            placeholder="https://script.google.com/macros/s/.../exec",
        )
        col1, col2 = st.columns(2)
        with col1:
            usuario = st.text_input("Usuário", value=cloud.credenciais()[0])
        with col2:
            senha = st.text_input("Senha", value=cloud.credenciais()[1], type="password")
        entrar = st.form_submit_button("Entrar", width="stretch")

    if entrar:
        try:
            cloud.configurar(url=url)
            resultado = cloud.login(usuario, senha)
            if resultado.get("ok"):
                cloud.carregar_permissoes()
                st.success("Login efetuado!")
                st.rerun()
            else:
                st.error(resultado.get("erro", "Falha no login."))
        except Exception as erro:
            st.error(f"Não foi possível conectar: {erro}")

    with st.expander("Primeira instalação (admin)"):
        st.caption(
            "Publique `appscript/VisualfilCloud.gs` como App da Web e execute "
            "`inicializar()` no editor do Apps Script para criar as planilhas "
            "e o usuário admin (padrão: admin/admin)."
        )
