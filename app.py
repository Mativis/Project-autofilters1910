"""
Sistema de Confecção — ponto de entrada
---------------------------------------
Páginas do sistema:

    Kanban de Confecção   -> kanban_confeccao.py
    Dashboards de Pedidos -> paginas/dashboards.py
    Análise de Estoque    -> paginas/analise_estoque.py
    Projeção Futuro       -> paginas/projecao_futuro.py

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

pagina = st.navigation(
    [
        st.Page(
            pagina_kanban,
            title="Kanban de Confecção",
            icon="📋",
            default=True,
        ),
        st.Page(
            "paginas/dashboards.py",
            title="Dashboards de Pedidos",
            icon="📊",
        ),
        st.Page(
            "paginas/analise_estoque.py",
            title="Análise de Estoque",
            icon="📦",
        ),
        st.Page(
            "paginas/projecao_futuro.py",
            title="Projeção Futuro",
            icon="📅",
        ),
    ],
    position="sidebar",
)

pagina.run()
