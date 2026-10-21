import json
from pathlib import Path

BASE = Path(r"C:\Users\User\Downloads\Project-autofilter")
TMP = BASE / "_t_pagina.py"

PEDIDOS = "C:/Users/User/Downloads/CONSIDERA\u00c7\u00d5ES/Pedidos.xlsx"
ESTOQUE = "C:/Users/User/Downloads/CONSIDERA\u00c7\u00d5ES/Estoque CMC.xlsx"

PRELUDE = f"""import streamlit as _st
def _fake_uploader(label, *a, **k):
    return {json.dumps(ESTOQUE)} if 'estoque' in str(label).lower() else {json.dumps(PEDIDOS)}
_st.file_uploader = _fake_uploader
"""

from streamlit.testing.v1 import AppTest

saida = []

for pagina in ["dashboards.py", "analise_estoque.py"]:
    TMP.write_text(PRELUDE + (BASE / "paginas" / pagina).read_text(encoding="utf-8"), encoding="utf-8")
    at = AppTest.from_file(str(TMP), default_timeout=300)
    at.run()

    saida.append("=" * 70)
    saida.append(f"PAGINA: {pagina}")
    saida.append(f"  excecoes: {[str(e.value)[:200] for e in at.exception]}")
    saida.append(f"  erros st.error: {[e.value[:200] for e in at.error]}")
    saida.append(f"  warnings: {[w.value[:120] for w in at.warning][:3]}")
    saida.append(f"  graficos (plotly): {len(at.get('plotly_chart'))}")
    saida.append(f"  dataframes: {len(at.get('dataframe'))}")
    saida.append(f"  downloads: {[b.label for b in at.get('download_button')]}")
    markdown = [m.value for m in at.get("markdown")]
    saida.append(f"  cards KPI: {sum(1 for m in markdown if 'db-card' in m)}")
    saida.append(f"  secoes: {len([m for m in markdown if 'db-secao' in m])}")

TMP.unlink(missing_ok=True)
Path(BASE / "_check_paginas.txt").write_text("\n".join(saida), encoding="utf-8")
print("ok")
