import json
from pathlib import Path

BASE = Path(r"C:\Users\User\Downloads\Project-autofilter")
TMP = BASE / "_t_app.py"

PEDIDOS = "C:/Users/User/Downloads/CONSIDERA\u00c7\u00d5ES/Pedidos.xlsx"
ESTOQUE = "C:/Users/User/Downloads/CONSIDERA\u00c7\u00d5ES/Estoque CMC.xlsx"

PRELUDE = f"""import streamlit as _st
def _fake_uploader(label, *a, **k):
    return {json.dumps(ESTOQUE)} if 'estoque' in str(label).lower() else {json.dumps(PEDIDOS)}
_st.file_uploader = _fake_uploader
"""

RODAPE = r"""
# --- Bloco de teste: gera o Excel da primeira confecção ---
_conf = sorted(df_filtrado["Confecção"].unique())[0]
_dfc = df_filtrado[df_filtrado["Confecção"] == _conf]
_bytes = gerar_excel_conf(_dfc, _conf)
with open(r"C:\Users\User\Downloads\Project-autofilter\_preview_excel_qe.xlsx", "wb") as _f:
    _f.write(_bytes)
# e o HTML de impressão
_html = gerar_html_impressao(_dfc, incluir_resumo=False, confeccao_destaque=_conf)
with open(r"C:\Users\User\Downloads\Project-autofilter\_preview_impressao_qe.html", "w", encoding="utf-8") as _f:
    _f.write(_html)
print("Q.E total esperado:", _dfc["Q.E"].sum(), "| Saldo total:", _dfc["Saldo"].sum())
"""

TMP.write_text(
    PRELUDE + (BASE / "app.py").read_text(encoding="utf-8") + RODAPE,
    encoding="utf-8",
)

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(TMP), default_timeout=300)
at.run()

out = []
out.append(f"excecoes: {[str(e.value) for e in at.exception]}")
out.append(f"erros: {[e.value for e in at.error]}")

TMP.unlink(missing_ok=True)
Path(BASE / "_check_excel.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
