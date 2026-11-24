# Visualfil Reflex — versão paralela profissional

Versão paralela do Visualfil em **Reflex** (Python → React), focada em performance
e interface mais responsiva. Roda junto com o Streamlit, sem alterá-lo.

## Estrutura

```
reflex_app/
  run.bat                    # inicializador (configura Node + variáveis)
  config.example.env         # modelo de configuração
  rxconfig.py                # tema Radix (índigo) + plugins
  requirements.txt
  visualfil_reflex/
    visualfil_reflex.py      # estado, API e 4 páginas
```

## Como rodar (Windows)

1. Copie `config.example.env` para `.env` e preencha a URL do Web App e as credenciais.
2. Duplo clique em `run.bat` (ou `.\run.bat` no PowerShell).

O script já configura:
- `PATH` com Node.js (necessário para o frontend);
- `REACT_ROUTER_DEV_RESTARTED=true` (contorna bug do React Router no Node 26/Windows);
- variáveis `VFCLOUD_URL`, `VFCLOUD_USUARIO`, `VFCLOUD_SENHA`.

Abra `http://localhost:3000`.

## Telas

- **`/`** — login com usuário/senha do Visualfil Cloud + avisos de erro/sucesso.
- **`/kanban`** — Kanban online: seleção de demanda, KPIs e tabela de pedidos
  (código, item, confecção, marca do estoque, quantidades e status), com
  paginação, busca e ordenação no cliente.
- **`/compra`** — compra sugerida: total, resumo por confecção, tabela discriminada
  por item e botão para salvar a análise no banco online.
- **`/dashboards`** — KPIs e agregações por confecção, status e prioridade.
- **`/projecao`** — capacidade semanal por confecção (histórico online) e compra sugerida × capacidade.
- **`/admin`** (somente admin) — abas:
  - **Demandas**: criar demanda com nome/fonte (Remessa), selecionar demanda e
    enviar/atualizar XLSX (pedidos, estoque, producao, projecao) por drag-and-drop;
  - **Usuários**: criar/editar usuários e senhas, marcar admin;
  - **Permissões**: definir por usuário/página nível `visualizacao`, `total` ou `restrito`.

## Design

- Sidebar escura com navegação, tema índigo (Radix), cards de KPI, tabelas com
  Paginação/Busca/Ordenação nativas, callouts de feedback e spinner de carregamento.
- Layout responsivo via Flex/Stack do Reflex.

## Validação

`python -m reflex compile` → **App compiled successfully** (21/20).

## Diagnóstico de carregamento

O seletor de demanda agora mostra:
- botões **Testar conexão** (ping na API) e **Ver arquivos enviados**;
- uma linha de diagnóstico com o retorno da API/erro;
- badges com a contagem de linhas de `pedidos`, `estoque` e `produção`.

Cada arquivo é carregado de forma independente: se um falhar, os demais continuam
funcionando e o erro aparece no aviso.

> Causa raiz corrigida: a normalização de código removia o zero de `24539.0`
> (virava `245390`), enquanto o estoque tinha `24539`. Agora usa a mesma regra do
> Streamlit (`24539.0 → 24539`), então os pedidos voltam a casar com o estoque.

## Proteção de rotas e permissões

- Todas as páginas internas chamam `verificar_login()` no `on_load` e redirecionam
  para `/` quando não há sessão.
- `/admin` chama `verificar_admin()` e redireciona para `/kanban` se não for administrador.
- O backend Cloud guarda níveis por usuário/página (`visualizacao`, `total`, `restrito`);
  o painel Admin permite configurá-los. A aplicação desses níveis no Reflex é o
  próximo passo (hoje a proteção cobre login e admin).

| Item | Streamlit | Reflex |
|---|---|---|
| Interação | rerun do script | reatividade no cliente (React) |
| Tabelas | st.datadataframe | data_table com paginação no front |
| Login | tela própria | rota `/` com redirecionamento |
| Admin | página completa | painel com abas no app |
| Tema | CSS customizado | Radix theme + componentes |

## Próximos passos possíveis

- Proteger rotas por permissão no Reflex (hoje só admin é escondido);
- Portar Dashboards/Projeções;
- Deploy no Reflex Cloud ou container Docker;
- PWA/APK com shell nativo.
