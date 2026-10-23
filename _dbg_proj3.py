import pandas as pd
pro = pd.read_excel(r"C:\Users\User\Downloads\CONSIDERAÇÕES\Projeção.xlsx")
print("shape:", pro.shape)
print()
# Check for total row at the end
print("last 2 rows Pedido:")
print(pro["Pedido"].tail(2).to_string())
print()
# Check distinct of Ped Cliente
print("Ped Cliente non-null:", pro["Ped Cliente"].notna().sum())
print()
# Check Dt. Agendamento vs Dt Entrega coverage
print("rows with both null (agend+entrega):", ((pro["Dt. Agendamento"].isna()) & (pro["Dt Entrega"].isna())).sum())
print("rows with agend non-null:", pro["Dt. Agendamento"].notna().sum())
print("rows with entrega non-null:", pro["Dt Entrega"].notna().sum())
print()
# Check Operação Produtiva nulls
print("Operação nulls:", pro["Operação Produtiva"].isna().sum())
print("Marca nulls:", pro["Marca"].isna().sum())
print("Status nulls:", pro["Sts do Pedido"].isna().sum())
print()
# Check Qtd * and Saldo Calc.
print("Qtd * sum:", pro["Qtd *"].sum())
print("Saldo Calc. sum:", pro["Saldo Calc."].sum())
print("Saldo Calc. nulls:", pro["Saldo Calc."].isna().sum())
print()
# Check Cód Prod nulls
print("Cód Prod nulls:", pro["Cód Prod"].isna().sum())
print("Cod. Produto nulls:", pro["Cod. Produto"].isna().sum())
