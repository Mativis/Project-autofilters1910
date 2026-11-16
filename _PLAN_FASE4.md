# Fase 4 — App mobile (Visual Kanban): lista por etapa com seleção

## Objetivo
Substituir a interação principal de **arrastar e soltar** (drag-and-drop) por um fluxo
mais dinâmico em telas touch: **lista por etapa com seleção em lote** (checkbox por
card + botões "Avançar/Concluir" em lote), mantendo o quadro (board) como opção.

## Motivação
- Drag-and-drop em WebView/Android é impreciso (scroll vs. arrastar).
- Botões e seleção em lote são mais rápidos no celular da confecção.
- A regra de negócio (movimentos permitidos) já existe em `movimentos(p)` e `mover()`.

## Escopo (repositório `visual_kanban/`, não este repo)

### Arquivos a alterar
- `visual_kanban/static/js/kanban.js`
  - `montarCardHtml(p)`: adicionar checkbox de seleção (quando em modo lista) e
    botões de ação já existentes (data-mover, data-parcial).
  - `render()`: adicionar modo "lista" (colunas empilhadas verticalmente, cards
    em lista) além do modo "board".
  - Nova função `renderLista()` ou ramificação em `render()`.
  - Barra de ações em lote (selecionar todos, avançar etapa, concluir).
  - Estado: `VK.state.viewMode = "board" | "lista"`.
- `visual_kanban/static/css/style.css`
  - Estilos para `.card.selected`, barra de lote (`.batch-bar`), modo lista
    (`.board.modo-lista`).
  - Alvos de toque >= 44px.
- `visual_kanban/static/index.html` / `app.html`
  - Toggle de modo (board/lista) no cabeçalho.
- `visual_kanban/android/`
  - Rebuild do APK (requer Android SDK + Gradle).
  - Atualizar versão/manifest OTA.

### Comportamento proposto
1. Toggle no cabeçalho: **Quadro** (board, atual) / **Lista** (novo).
2. Em modo Lista:
   - Cada etapa vira uma seção colapsável com título + contagem.
   - Cards em lista vertical, com checkbox à esquerda.
   - Botões por card: "Avançar" (próxima etapa permitida) e "Parcial" (já existe).
   - Barra fixa inferior: "Selecionar todos", "Mover selecionados para → [etapa]",
     "Limpar seleção".
3. Modo Board mantém drag-and-drop como fallback (não remover de imediato).
4. Persistir `viewMode` em `localStorage` (preferência do usuário).

### Reaproveitamento
- `movimentos(p)`, `mover(chave, novo)`, `abrirDetalhe`, `abrirParcial` já existem.
- `filtrados()`, `renderKpis()` reutilizáveis.
- Exportação (Excel/CSV) já usa `filtrosResumo()`.

### Riscos
- Caching de cards (`cacheCards`) precisa ser invalidado ao trocar de modo.
- Seleção em lote deve respeitar as regras de `movimentos()` (só mover para etapas
  permitidas; se misturar, desabilitar botão ou mostrar aviso).
- Performance: 1000+ cards em lista precisa de virtualização ou "carregar mais".

### Entregáveis
1. Patch dos arquivos JS/CSS (aplicado no repo `visual_kanban`).
2. Rebuild do APK + atualização OTA (`ota/manifest.json`).
3. Testes manuais em dispositivo/emulador.

### Status
- Este repositório (Visualfil/Streamlit) não contém o código do mobile em forma
  versionável (é um gitlink). A implementação deve ser feita no repositório
  `visual_kanban` e o ponteiro atualizado depois.
- Ambiente de build (Android SDK/Gradle) não disponível neste harness.

## Próximo passo recomendado
Clonar/atualizar o repositório `visual_kanban`, aplicar o patch e rebuildar o APK
em um ambiente com Android SDK. Posso gerar o patch (diff) dos arquivos JS/CSS
quando solicitado.
