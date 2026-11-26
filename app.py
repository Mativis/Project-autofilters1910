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

# Cada página só aparece para quem tem nível >= visualização nela.
# Sem nenhuma regra cadastrada, cloud.pode() devolve True (comportamento legado).
itens = [
    ("Online", "Painel Online", "paginas/painel_online.py", "☁️", True),
    ("Operação", "Kanban de Confecção", pagina_kanban, "📋", False),
    ("Análise", "Dashboards de Pedidos", "paginas/dashboards.py", "📊", False),
    ("Análise", "Análise de Estoque", "paginas/analise_estoque.py", "📦", False),
    ("Projeção", "Projeção Futuro", "paginas/projecao_futuro.py", "📅", False),
    ("Projeção", "Projeção por Confecção", "paginas/projecao_confeccao.py", "🏭", False),
    ("Integração", "All for One", "paginas/all_for_one.py", "🎯", False),
]
if cloud.eh_admin():
    itens.append(("Sistema", "Administração", "paginas/admin.py", "⚙️", False))

paginas_dict: dict[str, list] = {}
for secao, titulo, alvo, icon, default in itens:
    if not cloud.pode(titulo):
        continue
    paginas_dict.setdefault(secao, []).append(
        st.Page(alvo, title=titulo, icon=icon, default=default)
    )

if not paginas_dict:
    st.warning("Seu usuário não tem permissão de visualização em nenhuma página. "
               "Solicite acesso ao administrador.")
    st.stop()

usuario = cloud.usuario_atual()
with st.sidebar:
    st.caption(f"👤 **{usuario.get('nome', usuario.get('usuario'))}**"
               + (" · admin" if usuario.get("admin") else ""))
    if st.button("🚪 Sair"):
        cloud.logout()
        st.rerun()

pagina = st.navigation(paginas_dict, position="sidebar")
pagina.run()
