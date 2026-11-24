# Visualfil Reflex — versão paralela otimizada

Protótipo do Visualfil em **Reflex** (Python → React), criado para avaliar ganho de
performance e interface mais responsiva, sem alterar o sistema Streamlit atual.

## Estrutura

```
reflex_app/
  rxconfig.py                       # config (app_name = visualfil_reflex)
  requirements.txt                  # reflex, pandas, openpyxl, requests
  visualfil_reflex/
    __init__.py
    visualfil_reflex.py             # estado + páginas
```

## Pré-requisitos

- Python 3.10+ (testado em 3.13)
- Node.js LTS (necessário para o frontend do Reflex)

## Rodar local

```powershell
cd reflex_app
pip install -r requirements.txt
$env:VFCLOUD_URL = "https://script.google.com/macros/s/SEU_ID/exec"
python -m reflex run
```

Abra `http://localhost:3000`.

## O que já está implementado

- **Login** contra a mesma API do Visualfil Cloud (`appscript/VisualfilCloud.gs`);
- **Kanban online** (`/kanban`): lista demandas, lê `pedidos.xlsx` + `estoque.xlsx`
  do Drive e mostra os pedidos com Marca/classificação;
- **Compra sugerida** (`/compra`): card com total, resumo por confecção e tabela
  discriminada por item (`|Saldo 5| × 1,1 − Tec Faz "x" Confec`);
- Estado central em `rx.State`, com carregamento assíncrono e tabelas com
  paginação/busca/ordenação nativas do Reflex.

## Por que pode ser mais rápido

- Reflex compila para React: interações acontecem no cliente sem recarregar a página;
- apenas os dados necessários trafegam entre estado Python e interface;
- tabelas com paginação/ordenação no front evitam recomputar a página inteira.

## Limitações desta primeira entrega

- Somente leitura: Admin (usuários/permissões/upload de XLSX) continua no Streamlit;
- Autenticação usa a API do Cloud; ainda não há proteção de rota por permissão no Reflex;
- Visual ainda é o padrão Radix (sem o tema customizado do Visualfil).

## Compilação validada

`python -m reflex compile` concluiu com sucesso (18/17).
