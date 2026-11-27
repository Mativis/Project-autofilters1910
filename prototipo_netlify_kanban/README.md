# Protótipo Visualfil Kanban (Netlify) — Online via Google Sheets/Apps Script

Página estática (HTML/CSS/JS) no padrão do **Kanban de Confecção do Visualfil**, pronta para hospedar na Netlify e ler dados **online** do Google Sheets/Drive via Apps Script.

## Como funciona (rápido e estruturado)

1. **Visualfil Cloud (Apps Script + Google Sheets/Drive)** já recebe os XLSX por demanda e gera/salva a **pré-agregação** (`agregado_salvar`) com o kanban pronto.
2. O `index.html` na Netlify consulta o Apps Script por **GET**:
   - `?action=demandas` → lista demandas ativas
   - `?action=kanban&demanda_id=...` → retorna a pré-agregação da demanda
3. O front renderiza KPIs, filtros e quadro. Se a API não estiver configurada/disponível, faz fallback para `dados.js`/`dados.json` local.

Isso é rápido porque o front lê um JSON já agregado (não recalcula XLSX no navegador).

## Configuração

Edite o bloco `window.VISUALFIL_CONFIG` no `index.html`:

```js
window.VISUALFIL_CONFIG = {
  apiUrl: "https://script.google.com/macros/s/SEU_DEPLOY/exec",
  readToken: "",      // opcional; recomendado
  demandaId: "",      // opcional; vazio = primeira demanda ativa
  autoRefreshMs: 120000
};
```

### Apps Script

No `appscript/VisualfilCloud.gs` foi adicionado suporte a `doGet` para leitura pública controlada:

- `GET .../exec?action=demandas&token=...`
- `GET .../exec?action=kanban&demanda_id=...&token=...`

#### Token por confecção (recomendado)

Defina em **Script Properties**:

- `VF_READ_TOKEN` = token admin (vê tudo)
- `VF_CONF_TOKENS_JSON` = mapa JSON de tokens por confecção

Exemplo:

```json
{
  "tok_conf_abc123": "CONFECÇÃO A",
  "tok_conf_def456": { "confeccao": "CONFECÇÃO B", "ativo": true }
}
```

Com token de confecção, o Apps Script filtra `cards/pedidos/compra/capacidade/resumos` e recalcula KPIs apenas daquela confecção.

O front aceita token por `?token=...`, campo de login, ou `localStorage`. Para link direto por confecção, use:
`https://seu-site.netlify.app/?token=tok_conf_abc123`

Depois de alterar o Apps Script: **Implantar > Gerenciar implantações > Editar > Nova versão**.

## Publicar na Netlify

1. Deploy da pasta `prototipo_netlify_kanban/`.
2. Sem build. Entrada: `index.html`.
3. Configure `apiUrl` (e `readToken`) antes do deploy.

## Atualização dos dados reais

- **Online (recomendado):** no Visualfil, carregue/enviar demanda; o fluxo atual salva pré-agregado (`agregado_salvar`). A página Netlify passa a ler esse JSON.
- **Offline/local:** gerar `dados.js/dados.json` com:

```powershell
python prototipo_netlify_kanban\gerar_dados.py --pedidos "...\Pedidos.xlsx" --estoque "...\Estoque.xlsx" --saida "...prototipo_netlify_kanban"
```

## Segurança

Dados de produção não devem ficar públicos sem controle. Use ao menos `VF_READ_TOKEN`; idealmente publicar atrás de autenticação (Netlify Access/SSO/proxy) ou restringir por domínio/proxy.

## Geração de tokens pelo Admin

No Reflex, a página **Administração > Tokens Web** permite:
- informar a confecção;
- informar URL base da Netlify;
- gerar/atualizar token por confecção;
- listar/remover tokens.

Isso chama as ações admin do Apps Script: `tokens_web_listar`, `token_web_salvar`, `token_web_excluir`.
O token fica salvo em Script Property `VF_CONF_TOKENS_JSON`.
