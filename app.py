"""
Sistema de Confecção — ponto de entrada
---------------------------------------
Páginas do sistema, agrupadas por área:

    Operação      -> Kanban de Confecção
    Análise       -> Dashboards de Pedidos, Análise de Estoque
    Projeção      -> Projeção Futuro, Projeção por Confecção
    Integração    -> All for One, Envio ao Visual Kanban (dentro do Kanban)

Os arquivos enviados na barra lateral (Pedidos e Estoque) ficam disponíveis
em todas as páginas — envie uma única vez.
"""

import streamlit as st

from kanban_confeccao import pagina_kanban

st.set_page_config(
    page_title="Sistema de Confecção",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Navegação agrupada por área (Streamlit >= 1.36 suporta seções)
# ------------------------------------------------------------------ #
paginas = {
    "Operação": [
        st.Page(pagina_kanban, title="Kanban de Confecção", icon="📋", default=True),
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

pagina = st.navigation(paginas, position="sidebar")
pagina.run()
