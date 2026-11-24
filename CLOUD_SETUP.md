# Visualfil Cloud — configuração

Sistema com usuários, demandas salvas online e atualização de XLSX via Google Sheets/Apps Script.

## 1. Publicar o backend

1. Abra o editor do Apps Script (https://script.google.com).
2. Crie um novo projeto e cole o conteúdo de `appscript/VisualfilCloud.gs`.
3. Vincule o projeto a uma planilha (ou, em projeto avulso, defina a propriedade
   de script `VF_SPREADSHEET_ID` com o ID da planilha).
4. **Implantar → Nova implantação → App da Web**:
   - Executar como: **Eu**
   - Quem tem acesso: **Qualquer pessoa**
4. Copie a URL terminada em `/exec`.

## 2. Inicializar planilhas e admin

No editor do Apps Script, execute a função `inicializar()` uma única vez. Ela cria:
`USUARIOS`, `PERMISSOES`, `DEMANDAS`, `CATALOGO`, `ANALISES`.

Cria também o usuário admin padrão `admin` / senha `admin`. **Troque a senha** no painel Admin.

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
   - Usuários: criar/editar usuários e senhas.
   - Permissões: por usuário, definir **visualização**, **total** ou **restrito** para cada página.
   - Demandas e XLSX: criar demanda com **nome** e **fonte (Remessa)**; enviar/atualizar
     `pedidos.xlsx`, `estoque.xlsx`, `producao.xlsx` e `projecao.xlsx`.
   - Catálogo por confecção: importar planilha de itens confeccionados (mesma ideia da
     aba “Por Confecção” da Projeção por Confecção) para alimentar a compra sugerida.
3. **☁️ Painel Online** — escolhe a demanda, lê os XLSX do Drive e mostra:
   - indicadores do quadro (pedidos, unidades, classificação, marca vinda do Estoque);
   - **compra sugerida por confecção** (Saldo 5 negativo × 1,1, limitado por
     `Tec Faz "x" Confec`) e capacidade semanal quando `producao.xlsx` existe;
   - botão para **salvar a análise** no banco online.

## 5. Páginas clássicas

O Kanban de Confecção e as demais páginas continuam disponíveis e continuam usando
os uploads locais da barra lateral (conforme solicitado).
