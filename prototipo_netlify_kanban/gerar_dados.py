"""Gera dados reais do Kanban de Confecção para o protótipo Netlify.

Uso:
  python gerar_dados.py --pedidos "...\\Pedidos.xlsx" --estoque "...\\Estoque.xlsx"

Saídas:
  - dados.js   (window.KANBAN_DADOS = ...; compatível com file:// e Netlify)
  - dados.json (mesmo conteúdo, para integrações/API)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

import pandas as pd

# Reusa regras oficiais do projeto
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
from reflex_app.visualfil_reflex import dados  # noqa: E402


def _json_default(valor):
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return valor.isoformat()
    if pd.isna(valor):
        return None
    return str(valor)


def gerar(pedidos_xlsx: str, estoque_xlsx: str, saida_dir: str) -> dict:
    ped = pd.read_excel(pedidos_xlsx)
    est = pd.read_excel(estoque_xlsx)
    info = dados.montar_offline(ped, est)

    payload = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "pedidos": os.path.basename(pedidos_xlsx),
            "estoque": os.path.basename(estoque_xlsx),
        },
        "kpis": info.get("kpis", {}),
        "total_qe": info.get("total_qe", 0),
        "codigos_negativos": info.get("codigos_negativos", 0),
        "retornos": info.get("retornos", ""),
        "avisos": info.get("avisos", []),
        "resumo_confeccao": info.get("resumo_confeccao", []),
        "resumo_classificacao": info.get("resumo_classificacao", []),
        "cards": info.get("cards", []),
    }

    os.makedirs(saida_dir, exist_ok=True)
    json_path = os.path.join(saida_dir, "dados.json")
    js_path = os.path.join(saida_dir, "dados.js")
    texto = json.dumps(payload, ensure_ascii=False, default=_json_default)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(texto)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.KANBAN_DADOS = ")
        f.write(texto)
        f.write(";\n")

    print(f"OK: {len(payload['cards'])} cards")
    print(f"JSON: {json_path}")
    print(f"JS:   {js_path}")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pedidos", required=True)
    parser.add_argument("--estoque", required=True)
    parser.add_argument("--saida", default=os.path.dirname(__file__))
    args = parser.parse_args()
    gerar(args.pedidos, args.estoque, args.saida)


if __name__ == "__main__":
    main()