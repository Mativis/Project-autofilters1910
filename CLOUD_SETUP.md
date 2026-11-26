# Visualfil Cloud — configuração (backend v1.4.0)

Sistema com usuários, permissões, demandas salvas online e atualização de XLSX via
Google Sheets / Apps Script.

## 1. Publicar o backend

1. Abra o editor do Apps Script (https://script.google.com).
2. Crie um novo projeto e cole o conteúdo de `appscript/VisualfilCloud.gs`.
3. Vincule o projeto a uma planilha (ou, em projeto avulso, defina a propriedade de
   script `VF_SPREADSHEET_ID` com o ID da planilha).
4. **Implantar → Gerenciar implantações → Nova versão** (ou **Nova implantação →
   App da Web**):
   - Executar como: **Eu**
   - Quem tem acesso: **Qualquer pessoa**
5. Copie a URL terminada em `/exec`.

> Após atualizar o código do Apps Script, é obrigatório criar uma **nova versão** da
> implantação para expor as actions novas (`permissoes_minhas`, `arquivos_ler`,
> `agregado_salvar`, `agregado_ler`, `demanda_arquivar`, etc.).

## 2. Inicializar planilhas e admin

No editor do Apps Script, execute a função `inicializar()` uma única vez. Ela cria:
`USUARIOS`, `PERMISSOES`, `DEMANDAS`, `CATALOGO`, `ANALISES`, `AGREGADOS` e também
acrescenta colunas novas em planilhas já existentes (migração 1.3 → 1.4).

Cria o usuário admin padrão `admin` / senha `admin`. **Troque a senha** no painel Admin.

`inicializar` **não** é mais aceito pelo Web App sem proteção. Se precisar inicializar
remotamente, defina a propriedade de script `VF_SETUP_SECRET` e envie `setup_secret`
com esse valor — somente enquanto a aba `USUARIOS` estiver vazia.

## 3. Configurar o Streamlit

No Streamlit Cloud (ou local), defina em `secrets.toml`:

```toml
vfcloud_url = "https://script.google.com/macros/s/SEU_ID/exec"
vfcloud_usuario = "admin"
vfcloud_senha = "admin"
```

Ou preencha URL/usuário/senha na própria tela de login (fica salvo na sessão).

## 4. Fluxo de uso

1. **🔐 Entrar** — login com usuário/senha.
2. **⚙️ Administração** (somente admin):
   - Usuários: criar/editar usuários e senhas (um admin não pode remover seu próprio
     acesso).
   - Permissões: por usuário, definir **visualização**, **total** ou **restrito**
     para cada página. As regras são aplicadas pelo backend e pelo menu do app.
   - Demandas e XLSX: criar demanda com **nome** e **fonte (Remessa)**; enviar/atualizar
     `pedidos.xlsx`, `estoque.xlsx`, `producao.xlsx` e `projecao.xlsx`; arquivar/desarquivar.
   - Catálogo por confecção: importar planilha de itens confeccionados para alimentar
     a compra sugerida.
3. **☁️ Painel Online** — escolhe a demanda, lê os arquivos e mostra indicadores,
   compra sugerida por confecção discriminada por item, capacidade semanal e botão
   para salvar a análise.

## 5. Páginas clássicas

O Kanban de Confecção e as demais páginas continuam disponíveis e usam os uploads
locais da barra lateral (conforme solicitado).

## 6. Performance

Ordem de carregamento no Streamlit e no Reflex:

`pré-agregação no servidor → cache em memória (TTL 5 min) → lote (1 chamada) → paralelo`

- `arquivos_ler` lê os tipos em uma única chamada.
- `agregado_salvar` / `agregado_ler` guardam o resultado processado como JSON em
  `AGREGADOS`, com `stamp` do `atualizado_em` da demanda. Se os XLSX mudarem, o
  agregado é invalidado no backend (upload, exclusão, arquivamento) e, mesmo que
  algum cliente antigo deixe de invalidar, o `stamp` força recálculo.
- O botão **🔄 Atualizar dados** ignora cache e pré-agregação.
- O cache do Reflex é por `(usuário, demanda)`, e o do Streamlit é invalidado no upload.

## 7. Armazenamento em planilhas + arquivamento

- No upload, além do XLSX no Drive, as linhas são escritas em **abas da planilha
  principal** (`D_<demanda>_<tipo>`). A leitura passa a ser direta do GSheets
  (rápida), sem baixar/converter o XLSX. Se a conversão falhar ou o arquivo for
  muito grande, a aba não é criada e o sistema faz fallback para o XLSX do Drive.
- **📦 Arquivar demanda**: copia as abas para uma planilha separada na pasta
  `VisualfilArquivado` do Drive, remove as abas da planilha principal e marca
  `arquivada = SIM`. Leitura mais lenta, mas o arquivo principal fica limpo.
- **↩️ Desarquivar demanda**: traz as abas de volta. A cópia arquivada é mantida
  como backup (não é descartada).

## 8. Segurança (v1.4.0)

- Todas as ações, exceto `ping` e `login`, exigem credenciais válidas.
- Ações administrativas exigem `admin`. Leituras exigem pelo menos uma página com
  nível `visualizacao`; escritas de agregado/análise exigem `total`.
- `permissoes_listar` e `usuarios_listar` são somente para admin; usuários comuns
  usam `permissoes_minhas`.
- Análises salvas registram o usuário; a exclusão por não-admin só funciona para
  análise própria.
- No app Reflex, usuário e senha são Vars privadas (não são enviadas ao navegador)
  e o login usa formulário, sem digitar a senha tecla a tecla no estado.
