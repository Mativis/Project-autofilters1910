import pandas as pd
import numpy as np
pro = pd.read_excel(r"C:\Users\User\Downloads\CONSIDERAÇÕES\Projeção.xlsx")
# Remove total row
pro = pro[pro["Pedido"].notna() & pro["Cód Prod"].notna()].reset_index(drop=True)
qtd = pd.to_numeric(pro["Qtd *"], errors="coerce").fillna(0)
sc = pd.to_numeric(pro["Saldo Calc."], errors="coerce").fillna(0)
et = pd.to_numeric(pro["Em Trânsito"], errors="coerce").fillna(0)
saldo = ((qtd - sc) - et).clip(lower=0)
print("total rows:", len(pro))
print("saldo > 0:", (saldo > 0).sum())
print("saldo == 0:", (saldo == 0).sum())
print("agend non-null:", pro["Dt. Agendamento"].notna().sum())
# Among rows with agend non-null, how many have saldo > 0?
mask_agend = pro["Dt. Agendamento"].notna()
print("agend & saldo>0:", ((mask_agend) & (saldo > 0)).sum())
print("agend & saldo>0 & qtd>=100:", ((mask_agend) & (saldo > 0) & (saldo >= 100)).sum())
print()
# Grupo do Cliente
print("Grupo nulls:", pro["Grupo do Cliente"].isna().sum())
print("Grupo value counts (top 10):")
print(pro["Grupo do Cliente"].value_counts(dropna=False).head(10).to_string())
