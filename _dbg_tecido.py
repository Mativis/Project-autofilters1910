import os, sys
from pathlib import Path
BASE = Path(r"C:\Users\User\Downloads\Project-autofilter")
sys.path.insert(0, str(BASE))
# Check what fabric columns are available and how Saldo 5 relates
import pandas as pd
est = pd.read_excel(r"C:\Users\User\Downloads\CONSIDERAÇÕES\Estoque CMC.xlsx")
print("Saldo 5 stats:")
print(est["Saldo 5"].describe())
print("Saldo 5 < 0 count:", (est["Saldo 5"] < 0).sum())
print("Saldo 5 == 0 count:", (est["Saldo 5"] == 0).sum())
print("Saldo 5 > 0 count:", (est["Saldo 5"] > 0).sum())
print()
print("Tec Faz x Confec nulls:", est['Tec Faz "x" Confec'].isna().sum())
print("Cons. Unitário nulls:", est["Cons. Unitário"].isna().sum())
print()
pro = pd.read_excel(r"C:\Users\User\Downloads\CONSIDERAÇÕES\Projeção.xlsx")
pro = pro[pro["Pedido"].notna() & pro["Cód Prod"].notna()]
# Cross: how many projection codes have Saldo 5 < 0?
from nucleo import normalizar_cod
est["_cod"] = est["Cód Confec"].map(normalizar_cod)
pro["_cod"] = pro["Cód Prod"].map(normalizar_cod)
common = set(pro["_cod"]) & set(est["_cod"])
print("common codes:", len(common))
neg = 0
for c in common:
    s5 = est[est["_cod"]==c]["Saldo 5"].iloc[0]
    if pd.notna(s5) and s5 < 0:
        neg += 1
print("common codes with Saldo 5 < 0:", neg)
print("common codes with Saldo 5 >= 0:", len(common) - neg)
