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

TMP.write_text(PRELUDE + (BASE / "app.py").read_text(encoding="utf-8"), encoding="utf-8")

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(TMP), default_timeout=300)
at.run()

out = []
out.append(f"excecoes: {[str(e.value)[:300] for e in at.exception]}")
out.append(f"erros: {[e.value[:200] for e in at.error]}")
out.append(f"iframes: {len(at.get('iframe'))}")
out.append(f"tabs: {[t.label for t in at.tabs]}")
out.append(f"downloads: {[b.label for b in at.get('download_button')]}")
out.append(f"metrics: {[(m.label, m.value) for m in at.get('metric')]}")

htmls = [m.value for m in at.get("markdown") if m.value and "<table" in m.value]
out.append(f"tabelas html: {len(htmls)}")
if htmls:
    h = htmls[0]
    out.append(f"  cabecalho tem Q.E: {'>Q.E<' in h}")
    out.append(f"  celulas Q.E: {h.count('kb-num kb-qe')}")
    import re
    celulas = re.findall(r'kb-num kb-qe">([^<]*)<', h)
    out.append(f"  primeiras celulas Q.E: {celulas[:6]}")
    out.append(f"  total Q.E no rodape: {celulas[-1] if celulas else None}")

TMP.unlink(missing_ok=True)
Path(BASE / "_check_out.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
