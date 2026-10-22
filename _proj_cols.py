import pandas as pd
df = pd.read_excel(r'C:\Users\User\Downloads\CONSIDERAÇÕES\Projeção.xlsx')
print('shape:', df.shape)
print('cols:')
for c in df.columns:
    print(repr(c))
print()
print(df.head(15).to_string())
