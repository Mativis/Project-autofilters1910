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

## Performance — métodos de carregamento

Implementados para deixar o carregamento o mais rápido possível:

0. **Pré-agregação no servidor (mais rápido)**: ao processar uma demanda, o resultado
   já calculado (KPIs, tabelas e agregações) é salvo no Google Sheets via
   `agregado_salvar`. Nas próximas aberturas, `agregado_ler` devolve só esse JSON
   pequeno — **nenhum XLSX é baixado nem convertido**. Se não houver pré-agregação,
   o app cai automaticamente para o lote/paralelo.
1. **Chamada em lote (principal)**: `arquivos_ler` no Apps Script devolve os 3 XLSX
   de uma vez (1 ida ao servidor em vez de 3). O backend antigo é detectado
   automaticamente.
2. **Fallback paralelo**: se o backend não tiver `arquivos_ler`, as 3 leituras
   acontecem em paralelo (`ThreadPoolExecutor`), reduzindo o tempo total ao do
   arquivo mais lento.
3. **Cache em memória (TTL 5 min)**: após o primeiro carregamento, trocar entre
   Kanban / Compra / Dashboards / Projeção é **instantâneo** — os DataFrames e as
   agregações ficam em `CACHE_DADOS`, sem nova chamada à API.
4. **Invalidação inteligente**: enviar/atualizar qualquer XLSX limpa o cache da
   demanda; o botão **Atualizar** força recarregamento.
5. **Carregamento independente por arquivo**: se `producao.xlsx` faltar, pedidos e
   estoque continuam carregando e o erro aparece no diagnóstico.
6. **Feedback na tela**: badges com contagem de linhas e modo usado (`lote` ou
   `paralelo`), além do spinner durante o download.

> O backend precisa ser **reimplantado** para expor `arquivos_ler` e
> `agregado_salvar`/`agregado_ler` (versão 1.2.0). Sem isso, o app usa lote ou
> paralelo e recalcula localmente — também funciona.

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
