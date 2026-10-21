"""Refatora app.py -> kanban_confeccao.py (página do kanban como função)."""

import io
from pathlib import Path

BASE = Path(r"C:\Users\User\Downloads\Project-autofilter")
src = (BASE / "app.py").read_text(encoding="utf-8").split("\n")


def bloco(inicio, fim):  # 1-based, inclusivo
    return src[inicio - 1 : fim]


# Trechos do arquivo atual
imports = bloco(1, 31)          # imports
tema = bloco(41, 93)           # deteccao de tema + PALETA
set_page_config = bloco(33, 39)
css_e_interface = bloco(96, len(src))   # CSS + interface (vira corpo da funcao)


def indentar(linhas, n=4):
    saida = []
    for linha in linhas:
        if linha.strip() == "":
            saida.append("")
        else:
            saida.append(" " * n + linha)
    return saida


novo = []
novo.append('"""')
novo.append("Kanban de Confecção")
novo.append("-------------------------")
novo.append("Página principal do sistema: planilha de pedidos por confecção, com")
novo.append("quantidade emergencial (Q.E), impressão por aba e exportação em Excel.")
novo.append("")
novo.append("A função `pagina_kanban` é registrada em `app.py` via `st.navigation`.")
novo.append('"""')
novo.append("")
novo += imports
novo.append("")
novo += tema
novo.append("")
novo.append("")
novo.append("def pagina_kanban():")
novo.append('    """Renderiza a página do Kanban de Confecção."""')
novo += indentar(set_page_config)
novo.append("")
novo += indentar(css_e_interface)

texto = "\n".join(novo).rstrip() + "\n"
(BASE / "kanban_confeccao.py").write_text(texto, encoding="utf-8")
print("kanban_confeccao.py gerado:", len(novo), "linhas")
