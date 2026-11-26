# Visualfil Reflex

Versão paralela, em **Reflex (React + FastAPI)**, do Visualfil. Usa a mesma API do Google Apps Script (Google Sheets/Drive) para demandas online e também oferece o **Kanban de Confecção offline** com upload local dos XLSX.

## O que esta versão entrega

- **Front-end profissional refeito**: design system próprio, navegação lateral, KPIs, estados de carregamento/erro, responsividade.
- **Kanban de Confecção (offline)**: upload local de `Pedidos.xlsx` e `Estoque.xlsx`, quadro operacional com transições válidas, produção parcial, filtros, Q.E., rastreabilidade, resumo por confecção e exportação CSV/impressão.
- **Kanban online**: pedidos críticos por demanda (Remessa), lidos da nuvem.
- **Compra sugerida**: saldo 5 negativo × 1,1 − tecido em estoque, discriminada por item e por confecção.
- **Dashboards e projeção**: visão por confecção/prioridade e capacidade histórica.
- **Administração**: demandas, upload de XLSX online, usuários e permissões por página.
- **Segurança**: credenciais privadas no estado Reflex, login por usuário/senha, permissões aplicadas no cliente e no backend.

## Rodar localmente

```powershell
cd reflex_app
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.env .env
# edite .env com VFCLOUD_URL (URL /exec do Web App)
.\run.bat
```

Ou no PowerShell: `.\run.ps1`

Acesse `http://localhost:3000`.

## Variáveis de ambiente

- `VFCLOUD_URL` (obrigatória para área online): URL do Web App do Apps Script terminando em `/exec`.
- `VFCLOUD_USUARIO` / `VFCLOUD_SENHA` (opcionais): apenas fallback; o login normal usa as credenciais digitadas.

## Arquivos importantes

- `visualfil_reflex/visualfil_reflex.py`: estado, chamadas à API, rotas e páginas.
- `visualfil_reflex/tema.py`: design system/componentes visuais.
- `visualfil_reflex/dados.py`: regras offline (prioridade, rastreabilidade, Q.E., montagem do quadro).
- `rxconfig.py`: configuração do Reflex/tema base.
- `run.bat` / `run.ps1`: inicializadores Windows.

## Observações operacionais

- O Kanban offline **não envia** os XLSX para a nuvem; tudo fica na sessão do navegador/estado local.
- Para o online funcionar, o Apps Script deve estar implantado na versão atual (v1.4.0) com “Quem tem acesso: Qualquer pessoa”.
- Se o Streamlit Cloud estiver desatualizado, faça **Reboot app** no painel do Streamlit.
- Para compilar no Windows: `python -m reflex compile` com `PATH` incluindo `C:\Program Files\nodejs` e `REACT_ROUTER_DEV_RESTARTED=true`.
