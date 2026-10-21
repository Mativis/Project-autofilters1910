"""Verifica as 3 paginas do sistema (AppTest) com arquivos simulados."""

import json
from pathlib import Path

BASE = Path(r"C:\Users\User\Downloads\Project-autofilter")
CONS = Path(r"C:\Users\User\Downloads\CONSIDERAÇÕES")

PEDIDOS = CONS / "Pedidos.xlsx"
ESTOQUE = CONS / "Estoque CMC.xlsx"

PRELUDE = """
import os
import streamlit as _st


class _FakeUpload:
    def __init__(self, path):
        self.name = os.path.basename(path)
        with open(path, "rb") as _f:
            self._data = _f.read()

    def getvalue(self):
        return self._data

    @property
    def size(self):
        return len(self._data)


_PEDIDOS = r"{pedidos}"
_ESTOQUE = r"{estoque}"


def _fake_uploader(label, *a, **k):
    caminho = _ESTOQUE if "estoque" in str(label).lower() else _PEDIDOS
    return _FakeUpload(caminho)


_st.file_uploader = _fake_uploader
"""

from streamlit.testing.v1 import AppTest

saida = []
paginas = [
    ("Kanban (app.py)", BASE / "app.py", BASE / "_t_app.py"),
    ("Dashboards", BASE / "paginas" / "dashboards.py", BASE / "_t_pagina.py"),
    ("Analise de Estoque", BASE / "paginas" / "analise_estoque.py", BASE / "_t_pagina.py"),
]

for nome, origem, tmp in paginas:
    prelude = PRELUDE.format(pedidos=PEDIDOS, estoque=ESTOQUE)
    tmp.write_text(prelude + origem.read_text(encoding="utf-8"), encoding="utf-8")
    at = AppTest.from_file(str(tmp), default_timeout=300)
    at.run()

    saida.append("=" * 70)
    saida.append(f"PAGINA: {nome}")
    saida.append(f"  excecoes: {[str(e.value)[:200] for e in at.exception]}")
    saida.append(f"  erros st.error: {[e.value[:200] for e in at.error]}")
    saida.append(f"  warnings: {[w.value[:150] for w in at.warning][:3]}")
    saida.append(f"  graficos (plotly): {len(at.get('plotly_chart'))}")
    saida.append(f"  dataframes: {len(at.get('dataframe'))}")
    saida.append(f"  tabs: {[t.label for t in at.tabs]}")
    saida.append(f"  downloads: {[b.label for b in at.get('download_button')]}")
    saida.append(f"  botoes: {[b.label for b in at.get('button')][:6]}")
    markdown = [m.value for m in at.get("markdown")]
    saida.append(f"  cards KPI: {sum(1 for m in markdown if 'db-card' in m)}")
    saida.append(f"  arquivo carregado (sidebar): {[m[:80] for m in markdown if 'db-file-ok' in m]}")
    if nome.startswith("Kanban"):
        htmls = [m for m in markdown if "<table" in m]
        if htmls:
            h = htmls[0]
            import re

            celulas = re.findall(r'kb-num kb-qe">([^<]*)<', h)
            saida.append(f"  cabecalho tem Q.E: {'>Q.E<' in h}")
            saida.append(f"  celulas Q.E: {len(celulas)} | total no rodape: {celulas[-1] if celulas else None}")

    tmp.unlink(missing_ok=True)

Path(BASE / "_check_all.txt").write_text("\n".join(saida), encoding="utf-8")
print("ok")
