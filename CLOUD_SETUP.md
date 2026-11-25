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

## 7. Armazenamento em planilhas + arquivamento (backend 1.3.0)

- No upload, além do XLSX no Drive, as linhas são escritas em **abas da planilha
  principal** (`D_<demanda>_<tipo>`). A leitura passa a ser direta do GSheets
  (rápida), sem baixar/converter o XLSX.
- O painel **Administração → Demandas** tem os botões **📦 Arquivar demanda** e
  **↩️ Desarquivar demanda**:
  - **Arquivar** copia as abas para uma planilha separada na pasta `VisualfilArquivado`
    do Drive, remove as abas da planilha principal e marca `arquivada = SIM`.
    Leitura mais lenta, mas mantém o histórico fora do arquivo principal.
  - **Desarquivar** traz as abas de volta para o GSheets principal.

## 6. Performance (versão do backend 1.2.0)

O backend expõe `arquivos_ler` (lote), `agregado_salvar` e `agregado_ler`
(pré-agregação). O Painel Online e o app Reflex seguem esta ordem:
pré-agregação → cache em memória → lote → paralelo. Ao enviar/atualizar XLSX,
o cache é invalidado automaticamente.

## 5. Páginas clássicas

O Kanban de Confecção e as demais páginas continuam disponíveis e continuam usando
os uploads locais da barra lateral (conforme solicitado).
