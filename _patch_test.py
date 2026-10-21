import io

p = "kanban_confeccao.py"
s = io.open(p, encoding="utf-8").read()
old = "def pagina_kanban():"
new = (
    "def pagina_kanban():\n"
    "    st.session_state.setdefault('_contador_teste', 0)\n"
    "    st.session_state['_contador_teste'] += 1\n"
    "    st.markdown(\n"
    "        f\"<div style='font-size:2rem'>CONTADOR DE SESSAO: {st.session_state['_contador_teste']}</div>\",\n"
    "        unsafe_allow_html=True,\n"
    "    )"
)
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("patch aplicado")
