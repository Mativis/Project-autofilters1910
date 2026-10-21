from pathlib import Path

import pandas as pd

BASE = Path(r"C:\Users\User\Downloads\CONSIDERAÇÕES")
ARQS = [
    "Pedidos.xlsx",
    "Estoque CMC.xlsx",
    "Estoque LR.xlsx",
]

saida = []
for nome in ARQS:
    p = BASE / nome
    if not p.exists():
        saida.append(f"!! {nome} nao existe")
        continue
    xls = pd.ExcelFile(p)
    saida.append("=" * 70)
    saida.append(f"ARQUIVO: {nome} | abas: {xls.sheet_names}")
    for aba in xls.sheet_names:
        df = pd.read_excel(p, sheet_name=aba, nrows=400)
        saida.append(f"  -- aba '{aba}': {df.shape[0]} linhas x {df.shape[1]} colunas")
        saida.append(f"     colunas: {list(df.columns)}")
        saida.append("     dtypes: " + ", ".join(f"{c}={df[c].dtype}" for c in df.columns))
        saida.append("     amostra:")
        for _, row in df.head(3).iterrows():
            saida.append("       " + " | ".join(f"{c}={row[c]!r}" for c in df.columns))
        for c in df.columns:
            if df[c].dtype == object:
                uniq = df[c].dropna().astype(str).unique()[:12]
                saida.append(f"     uniques[{c}] ({df[c].nunique()}): {list(uniq)}")

Path("_inspecao.txt").write_text("\n".join(saida), encoding="utf-8")
print("ok")
