"""Preview local (temporário) da Projeção por Confecção e do Kanban."""

import sys
from pathlib import Path

RAIZ = Path(r"C:\Users\User\Downloads\Project-autofilter")
BASE = next(
    d
    for d in Path(r"C:\Users\User\Downloads").iterdir()
    if d.is_dir() and d.name.startswith("CONSIDERA")
)
sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

PAGINA = sys.argv[-1] if len(sys.argv) > 1 else "projecao"

st.session_state["bytes_pedidos"] = (BASE / "Pedidos.xlsx").read_bytes()
st.session_state["nome_pedidos"] = "Pedidos.xlsx"
st.session_state["bytes_estoque"] = (BASE / "Estoque.xlsx").read_bytes()
st.session_state["nome_estoque"] = "Estoque.xlsx"
st.session_state["producao_conf_bytes"] = next(BASE.glob("Produ*.xlsx")).read_bytes()
st.session_state["producao_conf_nome"] = "Produção por confecção.xlsx"

if PAGINA == "kanban":
    from kanban_confeccao import pagina_kanban

    pagina_kanban()
else:
    arquivo = RAIZ / "paginas" / "projecao_confeccao.py"
    codigo = arquivo.read_text(encoding="utf-8")
    exec(compile(codigo, str(arquivo), "exec"))
