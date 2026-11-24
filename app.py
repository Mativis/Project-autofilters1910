"""
Sistema Visualfil — ponto de entrada
------------------------------------
Agora com usuários e persistência online (Google Sheets / Apps Script):
  - 🔐 Entrar: autenticação;
  - ☁️ Painel Online: leitura dos XLSX salvos por demanda + análise salva;
  - ⚙️ Administração: usuários, permissões, demandas e XLSX (somente admin);
  - páginas clássicas (Kanban, Dashboards, Estoque, Projeções, All for One).

Os arquivos enviados na barra lateral continuam disponíveis em todas as
páginas clássicas — envie uma única vez.
"""
import streamlit as st

from kanban_confeccao import pagina_kanban
import nuvem as cloud

st.set_page_config(
    page_title="Visualfil",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not cloud.logado():
    pagina = st.navigation([st.Page("paginas/login.py", title="Entrar", icon="🔐", default=True)])
    pagina.run()
    st.stop()

cloud.carregar_permissoes()

paginas_dict = {
    "Online": [
        st.Page("paginas/painel_online.py", title="Painel Online", icon="☁️", default=True),
    ],
    "Operação": [
        st.Page(pagina_kanban, title="Kanban de Confecção", icon="📋"),
    ],
    "Análise": [
        st.Page("paginas/dashboards.py", title="Dashboards de Pedidos", icon="📊"),
        st.Page("paginas/analise_estoque.py", title="Análise de Estoque", icon="📦"),
    ],
    "Projeção": [
        st.Page("paginas/projecao_futuro.py", title="Projeção Futuro", icon="📅"),
        st.Page("paginas/projecao_confeccao.py", title="Projeção por Confecção", icon="🏭"),
    ],
    "Integração": [
        st.Page("paginas/all_for_one.py", title="All for One", icon="🎯"),
    ],
}

if cloud.eh_admin():
    paginas_dict["Sistema"] = [
        st.Page("paginas/admin.py", title="Administração", icon="⚙️"),
    ]

usuario = cloud.usuario_atual()
with st.sidebar:
    st.caption(f"👤 **{usuario.get('nome', usuario.get('usuario'))}**"
               + (" · admin" if usuario.get("admin") else ""))
    if st.button("🚪 Sair"):
        cloud.logout()
        st.rerun()

pagina = st.navigation(paginas_dict, position="sidebar")
pagina.run()
