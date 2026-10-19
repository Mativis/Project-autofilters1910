import streamlit as st
import pandas as pd
import numpy as np
import html
import io
from datetime import date

# Configurar página
st.set_page_config(
    page_title="Kanban de Confecção",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== TEMA (claro / escuro) ====================
try:
    _tema_atual = st.context.theme.type
except Exception:
    _tema_atual = None
TEMA_ESCURO = _tema_atual == "dark"

if TEMA_ESCURO:
    PALETA = """
            --kb-surface: #1a2332;
            --kb-surface-2: #202b3d;
            --kb-row-alt: #1c2635;
            --kb-row-hover: #243044;
            --kb-head-from: #243044;
            --kb-head-to: #1d2739;
            --kb-sum-from: #1f2937;
            --kb-sum-to: #243044;
            --kb-border: #2d3a4f;
            --kb-border-soft: #2a3648;
            --kb-text: #e7ecf3;
            --kb-text-soft: #a9b8cf;
            --kb-chip-bg: #243044;
            --kb-chip-border: #33415c;
            --kb-shadow: rgba(0, 0, 0, 0.55);
            --kb-info-from: #10314b;
            --kb-info-to: #0b2233;
            --kb-info-text: #d6ecff;
"""
else:
    PALETA = """
            --kb-surface: #ffffff;
            --kb-surface-2: #f8fafd;
            --kb-row-alt: #fbfcfe;
            --kb-row-hover: #f3f6fd;
            --kb-head-from: #f5f7fa;
            --kb-head-to: #e9edf6;
            --kb-sum-from: #f5f7fa;
            --kb-sum-to: #e4e9f2;
            --kb-border: #d9dfec;
            --kb-border-soft: #eef1f7;
            --kb-text: #3d4455;
            --kb-text-soft: #5a6172;
            --kb-chip-bg: #f0f2f8;
            --kb-chip-border: #dde2ee;
            --kb-shadow: rgba(0, 0, 0, 0.06);
            --kb-info-from: #e3f2fd;
            --kb-info-to: #bbdefb;
            --kb-info-text: #0d3c61;
"""

# ==================== CSS DO KANBAN ====================
st.markdown(
    """
    <style>
        :root {
            --kb-primary: #667eea;
            --kb-secondary: #764ba2;
            --kb-atrasado: #b71c1c;
            --kb-alta: #f44336;
            --kb-media: #ff9800;
            --kb-baixa: #4caf50;
/*__PALETA__*/
        }

        .kb-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.8rem 2.2rem;
            border-radius: 15px;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
            position: relative;
            overflow: hidden;
        }
        .kb-header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 280px;
            height: 280px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
        }
        .kb-header h1 { margin: 0; font-size: 2.1rem; font-weight: 800; position: relative; z-index: 1; }
        .kb-header p { margin: 0.6rem 0 0 0; opacity: 0.95; font-size: 1.05rem; position: relative; z-index: 1; }

        .kb-legend {
            display: flex;
            gap: 0.8rem;
            flex-wrap: wrap;
            margin-bottom: 1.2rem;
        }
        .kb-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: var(--kb-surface);
            border: 1px solid var(--kb-border);
            color: var(--kb-text);
            border-radius: 20px;
            padding: 0.35rem 0.9rem;
            font-size: 0.85rem;
            font-weight: 600;
            box-shadow: 0 2px 8px var(--kb-shadow);
        }
        .kb-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .kb-dot.atrasado { background: var(--kb-atrasado); }
        .kb-dot.alta { background: var(--kb-alta); }
        .kb-dot.media { background: var(--kb-media); }
        .kb-dot.baixa { background: var(--kb-baixa); }

        .kb-tab-summary {
            background: linear-gradient(135deg, var(--kb-sum-from) 0%, var(--kb-sum-to) 100%);
            border: 1px solid var(--kb-border);
            border-radius: 10px;
            padding: 0.7rem 1rem;
            margin: 0.2rem 0 1rem 0;
            font-size: 0.88rem;
            color: var(--kb-text-soft);
            font-weight: 600;
        }
        .kb-tab-summary b { color: var(--kb-text); }

        .kb-badge {
            display: inline-block;
            padding: 0.18rem 0.6rem;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 700;
            color: white;
            white-space: nowrap;
        }
        .kb-badge.atrasado { background: var(--kb-atrasado); }
        .kb-badge.alta { background: var(--kb-alta); }
        .kb-badge.media { background: var(--kb-media); }
        .kb-badge.baixa { background: var(--kb-baixa); }

        /* Planilha — uma linha por item */
        .kb-sheet-wrap {
            overflow-x: auto;
            background: var(--kb-surface);
            border: 1px solid var(--kb-border);
            border-radius: 12px;
            box-shadow: 0 2px 12px var(--kb-shadow);
            margin-bottom: 0.4rem;
        }
        table.kb-sheet {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        table.kb-sheet thead th {
            position: sticky;
            top: 0;
            z-index: 2;
            background: linear-gradient(135deg, var(--kb-head-from) 0%, var(--kb-head-to) 100%);
            color: var(--kb-text-soft);
            text-align: left;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 800;
            padding: 0.7rem 0.8rem;
            border-bottom: 2px solid var(--kb-border);
            white-space: nowrap;
        }
        table.kb-sheet tbody td {
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid var(--kb-border-soft);
            color: var(--kb-text);
            vertical-align: middle;
        }
        table.kb-sheet tbody tr:nth-child(even) { background: var(--kb-row-alt); }
        table.kb-sheet tbody tr:hover { background: var(--kb-row-hover); }
        table.kb-sheet td.kb-num { text-align: right; font-weight: 700; white-space: nowrap; }
        table.kb-sheet td.kb-date { white-space: nowrap; }
        table.kb-sheet td.kb-desc-cell { min-width: 280px; }
        table.kb-sheet td.kb-conf-cell { color: var(--kb-text-soft); white-space: nowrap; }
        table.kb-sheet tr.row-atrasado td:first-child { box-shadow: inset 5px 0 0 var(--kb-atrasado); }
        table.kb-sheet tr.row-alta td:first-child { box-shadow: inset 4px 0 0 var(--kb-alta); }
        table.kb-sheet tr.row-media td:first-child { box-shadow: inset 4px 0 0 var(--kb-media); }
        table.kb-sheet tr.row-baixa td:first-child { box-shadow: inset 4px 0 0 var(--kb-baixa); }
        table.kb-sheet tfoot td {
            padding: 0.65rem 0.8rem;
            border-top: 2px solid var(--kb-border);
            background: var(--kb-surface-2);
            color: var(--kb-text);
            font-weight: 800;
        }
        .kb-sheet-wrap .kb-cod {
            display: inline-block;
            background: var(--kb-chip-bg);
            border: 1px solid var(--kb-chip-border);
            color: var(--kb-text-soft);
            border-radius: 6px;
            padding: 0.1rem 0.45rem;
            font-size: 0.78rem;
            font-weight: 700;
        }

        .kb-info-box {
            background: linear-gradient(135deg, var(--kb-info-from) 0%, var(--kb-info-to) 100%);
            color: var(--kb-info-text);
            padding: 0.9rem 1rem;
            border-radius: 10px;
            border-left: 4px solid #2196f3;
            margin: 0.8rem 0;
            font-size: 0.92rem;
        }
    </style>
    """.replace("/*__PALETA__*/", PALETA),
    unsafe_allow_html=True,
)

# ==================== FUNÇÕES AUXILIARES ====================

@st.cache_data
def load_excel(file):
    """Carrega um arquivo Excel com cache"""
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()
    return df


def normalizar_cod(valor):
    """Normaliza o código da confecção para string comparável (ex.: 23012.0 -> '23012')"""
    if pd.isna(valor):
        return ""
    try:
        num = float(valor)
        if num == int(num):
            return str(int(num))
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def calcular_prioridade(dt_entrega):
    """
    Define a prioridade com base na data de entrega:
    - Data de entrega já vencida.................: Atrasado
    - Faltar mais de 1 mês (> 30 dias)..........: Baixa
    - Entre 15 e 30 dias........................: Média
    - Menos de 15 dias..........................: Alta
    """
    if pd.isna(dt_entrega):
        return "Baixa"
    dias = (pd.Timestamp(dt_entrega).normalize().date() - date.today()).days
    if dias < 0:
        return "Atrasado"
    if dias > 30:
        return "Baixa"
    if dias > 15:
        return "Média"
    return "Alta"


# Ordem de exibição (mais urgente primeiro)
ORDEM_PRIORIDADE = {"Atrasado": 0, "Alta": 1, "Média": 2, "Baixa": 3}


def classe_prioridade(prioridade):
    return {
        "Atrasado": "atrasado",
        "Alta": "alta",
        "Média": "media",
        "Baixa": "baixa",
    }.get(prioridade, "baixa")


def texto_dias(dt_entrega):
    """Texto informativo sobre o prazo de entrega"""
    if pd.isna(dt_entrega):
        return "⏰ Sem data de entrega"
    dias = (pd.Timestamp(dt_entrega).normalize().date() - date.today()).days
    if dias < 0:
        return f"⚠️ Atrasado há {-dias} dia(s)"
    if dias == 0:
        return "⏰ Entrega hoje!"
    return f"⏰ Faltam {dias} dia(s)"


def fmt_num(valor):
    """Formata número no padrão brasileiro (milhar com ponto)"""
    try:
        if pd.isna(valor):
            return "—"
        return f"{float(valor):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def fmt_compra(valor):
    """Formata o número da compra sem casas decimais"""
    try:
        if pd.isna(valor):
            return "—"
        num = float(valor)
        return str(int(num)) if num == int(num) else str(num)
    except (TypeError, ValueError):
        return str(valor)


def fmt_data(valor):
    if pd.isna(valor):
        return "—"
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


# ==================== INTERFACE PRINCIPAL ====================

st.markdown(
    """
    <div class="kb-header">
        <h1>📌 Kanban de Confecção — Pedidos sem Estoque</h1>
        <p>Itens do Estoque com <b>Saldo 2 negativo</b>, localizados nos Pedidos pelo <b>Cód Confec</b> e agrupados por confecção</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="kb-legend">
        <span class="kb-legend-item"><span class="kb-dot atrasado"></span> ⚠️ Atrasado — data de entrega vencida</span>
        <span class="kb-legend-item"><span class="kb-dot alta"></span> 🔴 Alta — entrega em até 15 dias</span>
        <span class="kb-legend-item"><span class="kb-dot media"></span> 🟠 Média — entrega em 16 a 30 dias</span>
        <span class="kb-legend-item"><span class="kb-dot baixa"></span> 🟢 Baixa — entrega em mais de 1 mês</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar: upload dos arquivos
with st.sidebar:
    st.header("📁 Arquivos")
    uploaded_pedidos = st.file_uploader(
        "Arquivo de **Pedidos** (.xlsx)",
        type=["xlsx", "xls"],
        key="kanban_file_pedidos",
        help="Colunas: Compra, Cód Confec, Confeccionado, Qtd, Saldo, Dt Entrega, Confecção",
    )
    uploaded_estoque = st.file_uploader(
        "Arquivo de **Estoque** (.xlsx)",
        type=["xlsx", "xls"],
        key="kanban_file_estoque",
        help="Colunas: Cód Confec, Saldo 2 (usadas apenas para filtrar)",
    )

if uploaded_pedidos is None or uploaded_estoque is None:
    st.info("👆 Faça o upload dos arquivos de **Pedidos** e **Estoque** na barra lateral para montar o kanban.")
    with st.expander("ℹ️ Como funciona esta página"):
        st.markdown("""
            1. O sistema lê o arquivo de **Estoque** e identifica todos os itens com **Saldo 2 negativo**.
            2. Esses códigos (`Cód Confec`) são usados para **filtrar os Pedidos**.
            3. Os pedidos filtrados são **agrupados por Confecção** em abas, com os itens em formato de **planilha (uma linha por item)**.
            4. Cada linha mostra informações vindas apenas do arquivo de **Pedidos**:
               - **Pedido** (coluna `Compra`)
               - **Cód Confec**
               - **Descrição** (coluna `Confeccionado`)
               - **Quantidade** (coluna `Saldo`)
               - **Data de entrega** (coluna `Dt Entrega`)
               - **Prioridade** (calculada pela data de entrega)

            ### Regra de prioridade (em relação ao dia de hoje):
            | Prazo até a entrega | Prioridade |
            |---|---|
            | Data de entrega já vencida | ⚠️ Atrasado |
            | Mais de 1 mês (> 30 dias) | 🟢 Baixa |
            | Menos de 1 mês e mais de 15 dias (16 a 30) | 🟠 Média |
            | Menos de 15 dias | 🔴 Alta |

            ### Regra de quantidade:
            - 🚫 Linhas em que o **Saldo** é **igual ou menor que 4% da Qtd** são desconsideradas
              (ex.: Qtd = 100 → Saldo ≤ 4 é descartado). Pode ser desativada na barra lateral.
        """)
    st.stop()

# ==================== CARREGAMENTO E FILTRAGEM ====================

COLUNAS_PEDIDOS = ["Compra", "Cód Confec", "Confeccionado", "Qtd", "Saldo", "Dt Entrega", "Confecção"]

try:
    df_pedidos = load_excel(uploaded_pedidos)
    df_estoque = load_excel(uploaded_estoque)
except Exception as e:
    st.error(f"Erro ao ler os arquivos: {e}")
    st.stop()

# Validação de colunas
faltando_pedidos = [c for c in COLUNAS_PEDIDOS if c not in df_pedidos.columns]
faltando_estoque = [c for c in ["Cód Confec", "Saldo 2"] if c not in df_estoque.columns]

if faltando_pedidos:
    st.error(f"❌ Colunas ausentes no arquivo de **Pedidos**: {', '.join(faltando_pedidos)}")
    st.stop()
if faltando_estoque:
    st.error(f"❌ Colunas ausentes no arquivo de **Estoque**: {', '.join(faltando_estoque)}")
    st.stop()

# 1) Códigos com Saldo 2 negativo no Estoque
df_estoque["Saldo 2"] = pd.to_numeric(df_estoque["Saldo 2"], errors="coerce")
codigos_saldo2_neg = set(
    df_estoque.loc[df_estoque["Saldo 2"] < 0, "Cód Confec"].map(normalizar_cod)
) - {""}

# 2) Filtrar Pedidos pelo Cód Confec
df_pedidos["Cód Confec_norm"] = df_pedidos["Cód Confec"].map(normalizar_cod)
df_kanban = df_pedidos[df_pedidos["Cód Confec_norm"].isin(codigos_saldo2_neg)].copy()

# 3) Preparar colunas exibidas no kanban (dados somente de Pedidos)
df_kanban["Dt Entrega"] = pd.to_datetime(df_kanban["Dt Entrega"], errors="coerce")
df_kanban["Saldo"] = pd.to_numeric(df_kanban["Saldo"], errors="coerce")
df_kanban["Qtd"] = pd.to_numeric(df_kanban["Qtd"], errors="coerce")
df_kanban["Prioridade"] = df_kanban["Dt Entrega"].apply(calcular_prioridade)
df_kanban["Confecção"] = (
    df_kanban["Confecção"].fillna("").astype(str).str.strip().replace("", "Sem Confecção")
)
df_kanban["Confeccionado"] = df_kanban["Confeccionado"].fillna("").astype(str).str.strip()
df_kanban["Cód Confec"] = df_kanban["Cód Confec_norm"]

if df_kanban.empty:
    st.warning("Nenhum pedido encontrado para os códigos com Saldo 2 negativo no Estoque.")
    st.stop()

# ==================== BARRA LATERAL: FILTROS ====================

with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros")

    confeccoes_sel = st.multiselect(
        "Confecção",
        options=sorted(df_kanban["Confecção"].unique().tolist()),
        default=sorted(df_kanban["Confecção"].unique().tolist()),
    )

    prioridades_sel = st.multiselect(
        "Prioridade",
        options=["Atrasado", "Alta", "Média", "Baixa"],
        default=["Atrasado", "Alta", "Média", "Baixa"],
    )

    termo_busca = st.text_input("Buscar por código ou descrição:", value="")

    st.markdown("---")
    desconsiderar_saldo_baixo = st.checkbox(
        "Desconsiderar Saldo ≤ 4% da Qtd",
        value=True,
        help="Remove as linhas em que o Saldo é igual ou menor que 4% da Qtd.",
    )

# ==================== REGRA: Saldo ≤ 4% da Qtd ====================

df_base = df_kanban.copy()
linhas_descartadas = 0

if desconsiderar_saldo_baixo:
    mask_saldo_baixo = (df_base["Qtd"] > 0) & (df_base["Saldo"] <= df_base["Qtd"] * 0.04)
    linhas_descartadas = int(mask_saldo_baixo.sum())
    df_base = df_base[~mask_saldo_baixo].copy()

df_filtrado = df_base[df_base["Confecção"].isin(confeccoes_sel)].copy()
df_filtrado = df_filtrado[df_filtrado["Prioridade"].isin(prioridades_sel)]

if termo_busca.strip():
    termo = termo_busca.strip().lower()
    df_filtrado = df_filtrado[
        df_filtrado["Cód Confec"].str.lower().str.contains(termo, na=False)
        | df_filtrado["Confeccionado"].str.lower().str.contains(termo, na=False)
    ]

if desconsiderar_saldo_baixo and linhas_descartadas > 0:
    st.info(
        f"ℹ️ {linhas_descartadas} linha(s) desconsiderada(s) por terem "
        f"Saldo ≤ 4% da Qtd (dados apenas de Pedidos)."
    )


# ==================== MÉTRICAS ====================

st.markdown("---")

contagem_prio = df_filtrado["Prioridade"].value_counts()

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("Total de Pedidos", len(df_filtrado))
with col2:
    st.metric("Confecções", df_filtrado["Confecção"].nunique())
with col3:
    st.metric("⚠️ Atrasado", int(contagem_prio.get("Atrasado", 0)))
with col4:
    st.metric("🔴 Alta", int(contagem_prio.get("Alta", 0)))
with col5:
    st.metric("🟠 Média", int(contagem_prio.get("Média", 0)))
with col6:
    st.metric("🟢 Baixa", int(contagem_prio.get("Baixa", 0)))

st.markdown(
    f"<div class='kb-info-box'>📦 Quantidade total (Saldo): <b>{fmt_num(df_filtrado['Saldo'].sum())}</b> unidade(s) &nbsp;|&nbsp; "
    f"🔍 <b>{len(codigos_saldo2_neg)}</b> código(s) com Saldo 2 negativo no Estoque &nbsp;|&nbsp; "
    f"📅 Data de referência: <b>{date.today().strftime('%d/%m/%Y')}</b></div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ==================== RENDERIZAÇÃO DO KANBAN ====================

st.markdown("### 📌 Pedidos por Confecção — planilha (uma linha por item)")

if df_filtrado.empty:
    st.warning("Nenhum pedido encontrado com os filtros selecionados.")
    st.stop()

# Ordenar por prioridade → data de entrega → compra
df_filtrado["_prio_ord"] = df_filtrado["Prioridade"].map(ORDEM_PRIORIDADE)
df_filtrado = df_filtrado.sort_values(
    ["_prio_ord", "Dt Entrega", "Compra"],
    ascending=[True, True, True],
)


def html_sheet(df_col):
    """Monta o HTML de uma planilha (uma linha por item) de uma confecção"""
    linhas = []
    for _, row in df_col.iterrows():
        cls = classe_prioridade(row["Prioridade"])
        pedido = html.escape(fmt_compra(row["Compra"]))
        cod = html.escape(str(row["Cód Confec"]))
        desc = html.escape(str(row["Confeccionado"]).strip())
        conf = html.escape(str(row["Confecção"]))
        qtd = fmt_num(row["Saldo"])
        data = fmt_data(row["Dt Entrega"])
        prio = html.escape(str(row["Prioridade"]))
        prio_txt = ("⚠️ " if row["Prioridade"] == "Atrasado" else "") + prio
        dias_txt = html.escape(texto_dias(row["Dt Entrega"]))

        linhas.append(
            f'<tr class="row-{cls}">'
            f'<td class="kb-pedido-cell">{pedido}</td>'
            f'<td><span class="kb-cod">{cod}</span></td>'
            f'<td class="kb-desc-cell">{desc}</td>'
            f'<td class="kb-conf-cell">{conf}</td>'
            f'<td class="kb-num">{qtd}</td>'
            f'<td class="kb-date" title="{dias_txt}">{data}</td>'
            f'<td><span class="kb-badge {cls}">{prio_txt}</span></td>'
            "</tr>"
        )

    return (
        '<div class="kb-sheet-wrap">'
        '<table class="kb-sheet">'
        "<thead><tr>"
        "<th>Pedido</th>"
        "<th>Cód Confec</th>"
        "<th>Descrição</th>"
        "<th>Confecção</th>"
        '<th style="text-align:right">Quantidade</th>'
        "<th>Data de Entrega</th>"
        "<th>Prioridade</th>"
        "</tr></thead>"
        "<tbody>" + "".join(linhas) + "</tbody>"
        "<tfoot><tr>"
        f'<td colspan="4">Total ({len(df_col)} item(ns))</td>'
        f'<td class="kb-num">{fmt_num(df_col["Saldo"].sum())}</td>'
        '<td colspan="2"></td>'
        "</tr></tfoot>"
        "</table></div>"
    )


# Uma aba por confecção
confeccoes_abas = sorted(df_filtrado["Confecção"].unique().tolist())
abas = st.tabs([f"🏭 {conf[:30]}" for conf in confeccoes_abas])

for aba, confeccao in zip(abas, confeccoes_abas):
    with aba:
        df_col = df_filtrado[df_filtrado["Confecção"] == confeccao]
        total_qtd = df_col["Saldo"].sum()
        qtd_atrasado = int((df_col["Prioridade"] == "Atrasado").sum())
        qtd_alta = int((df_col["Prioridade"] == "Alta").sum())
        qtd_media = int((df_col["Prioridade"] == "Média").sum())
        qtd_baixa = int((df_col["Prioridade"] == "Baixa").sum())

        st.markdown(
            f"""
            <div class="kb-tab-summary">
                🏭 <b>{html.escape(confeccao)}</b> &nbsp;·&nbsp;
                <b>{len(df_col)}</b> pedido(s) &nbsp;·&nbsp;
                📦 <b>{fmt_num(total_qtd)}</b> unidade(s) &nbsp;·&nbsp;
                ⚠️ <b>{qtd_atrasado}</b> atrasado(s) &nbsp;·&nbsp;
                🔴 <b>{qtd_alta}</b> alta(s) &nbsp;·&nbsp;
                🟠 <b>{qtd_media}</b> média(s) &nbsp;·&nbsp;
                🟢 <b>{qtd_baixa}</b> baixa(s)
            </div>
            """,
            unsafe_allow_html=True,
        )

        if df_col.empty:
            st.info("Nenhum pedido nesta confecção com os filtros atuais.")
        else:
            st.markdown(html_sheet(df_col), unsafe_allow_html=True)

# ==================== TABELA E EXPORTAÇÃO ====================

st.markdown("---")
st.markdown("### 📋 Detalhamento e exportação")

df_tabela = df_filtrado[["Compra", "Cód Confec", "Confeccionado", "Saldo", "Dt Entrega", "Prioridade", "Confecção"]].copy()
df_tabela = df_tabela.rename(
    columns={
        "Compra": "Pedido",
        "Saldo": "Quantidade",
        "Dt Entrega": "Data de Entrega",
    }
).sort_values(["Confecção", "Data de Entrega"])

with st.expander("📋 Ver tabela completa e interativa (todos os registros)"):
    st.dataframe(
        df_tabela,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pedido": st.column_config.TextColumn("Pedido", width="small"),
            "Cód Confec": st.column_config.TextColumn("Cód Confec", width="small"),
            "Confeccionado": st.column_config.TextColumn("Descrição", width="large"),
            "Quantidade": st.column_config.NumberColumn("Quantidade", format="%d"),
            "Data de Entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"),
            "Prioridade": st.column_config.TextColumn("Prioridade", width="small"),
            "Confecção": st.column_config.TextColumn("Confecção", width="large"),
        },
    )

col1, col2 = st.columns(2)

with col1:
    csv = df_tabela.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 Baixar CSV",
        data=csv,
        file_name=f"kanban_confeccao_{date.today().strftime('%Y-%m-%d')}.csv",
        use_container_width=True,
    )

with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_tabela.to_excel(writer, index=False, sheet_name="Kanban")
        resumo = (
            df_filtrado.groupby("Confecção")
            .agg(Pedidos=("Compra", "count"), Quantidade=("Saldo", "sum"))
            .reset_index()
        )
        resumo.to_excel(writer, index=False, sheet_name="Resumo")
    st.download_button(
        "📊 Baixar Excel",
        data=buffer.getvalue(),
        file_name=f"kanban_confeccao_{date.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
