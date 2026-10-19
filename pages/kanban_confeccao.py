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

# ==================== CSS DO KANBAN ====================
st.markdown(
    """
    <style>
        :root {
            --kb-primary: #667eea;
            --kb-secondary: #764ba2;
            --kb-alta: #f44336;
            --kb-media: #ff9800;
            --kb-baixa: #4caf50;
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
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 20px;
            padding: 0.35rem 0.9rem;
            font-size: 0.85rem;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .kb-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .kb-dot.alta { background: var(--kb-alta); }
        .kb-dot.media { background: var(--kb-media); }
        .kb-dot.baixa { background: var(--kb-baixa); }

        .kb-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.9rem;
            align-items: flex-start;
            padding-bottom: 0.5rem;
        }

        .kb-tab-summary {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%);
            border: 1px solid #dde2ee;
            border-radius: 10px;
            padding: 0.7rem 1rem;
            margin: 0.2rem 0 1rem 0;
            font-size: 0.88rem;
            color: #5a6172;
            font-weight: 600;
        }
        .kb-tab-summary b { color: #3d4455; }

        .kb-card {
            background: white;
            border-radius: 10px;
            padding: 0.85rem 0.9rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 5px solid #9e9e9e;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            flex: 1 1 330px;
            max-width: 440px;
        }
        .kb-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0,0,0,0.14);
        }
        .kb-card.alta { border-left-color: var(--kb-alta); }
        .kb-card.media { border-left-color: var(--kb-media); }
        .kb-card.baixa { border-left-color: var(--kb-baixa); }

        .kb-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .kb-pedido {
            font-weight: 800;
            font-size: 0.92rem;
            color: #4a4f5e;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .kb-badge {
            display: inline-block;
            padding: 0.18rem 0.6rem;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 700;
            color: white;
            white-space: nowrap;
        }
        .kb-badge.alta { background: var(--kb-alta); }
        .kb-badge.media { background: var(--kb-media); }
        .kb-badge.baixa { background: var(--kb-baixa); }

        .kb-cod {
            display: inline-block;
            background: #f0f2f8;
            border: 1px solid #dde2ee;
            color: #5a6172;
            border-radius: 6px;
            padding: 0.15rem 0.5rem;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }

        .kb-desc {
            font-size: 0.83rem;
            color: #3d4455;
            line-height: 1.35;
            margin-bottom: 0.5rem;
            word-break: break-word;
        }

        .kb-conf {
            display: block;
            font-size: 0.75rem;
            font-weight: 700;
            color: #667eea;
            background: #f2f4fc;
            border: 1px solid #dfe4f5;
            border-radius: 6px;
            padding: 0.18rem 0.5rem;
            margin-bottom: 0.55rem;
            word-break: break-word;
        }

        .kb-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            flex-wrap: wrap;
            border-top: 1px dashed #e3e6ef;
            padding-top: 0.5rem;
        }
        .kb-qtd, .kb-data {
            font-size: 0.8rem;
            color: #5a6172;
            font-weight: 600;
            white-space: nowrap;
        }
        .kb-qtd b { color: #3d4455; font-size: 0.9rem; }

        .kb-dias {
            margin-top: 0.4rem;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 6px;
            padding: 0.2rem 0.5rem;
            display: inline-block;
        }
        .kb-dias.alta { background: #fdecea; color: var(--kb-alta); }
        .kb-dias.media { background: #fff4e5; color: var(--kb-media); }
        .kb-dias.baixa { background: #e9f7ec; color: var(--kb-baixa); }

        .kb-empty-col {
            padding: 1.2rem 0.8rem;
            text-align: center;
            color: #9aa0b0;
            font-size: 0.85rem;
        }

        .kb-info-box {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            padding: 0.9rem 1rem;
            border-radius: 10px;
            border-left: 4px solid #2196f3;
            margin: 0.8rem 0;
            font-size: 0.92rem;
        }
    </style>
    """,
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
    - Faltar mais de 1 mês (> 30 dias)...........: Baixa
    - Entre 15 e 30 dias........................: Média
    - Menos de 15 dias (ou atrasado)............: Alta
    """
    if pd.isna(dt_entrega):
        return "Baixa"
    dias = (pd.Timestamp(dt_entrega).normalize().date() - date.today()).days
    if dias > 30:
        return "Baixa"
    if dias > 15:
        return "Média"
    return "Alta"


def classe_prioridade(prioridade):
    return {"Alta": "alta", "Média": "media", "Baixa": "baixa"}.get(prioridade, "baixa")


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
        help="Colunas: Compra, Cód Confec, Confeccionado, Saldo, Dt Entrega, Confecção",
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
            3. Os pedidos filtrados são **agrupados por Confecção** em colunas de um kanban.
            4. Cada card mostra informações vindas apenas do arquivo de **Pedidos**:
               - **Pedido** (coluna `Compra`)
               - **Cód Confec**
               - **Descrição** (coluna `Confeccionado`)
               - **Quantidade** (coluna `Saldo`)
               - **Data de entrega** (coluna `Dt Entrega`)
               - **Prioridade** (calculada pela data de entrega)

            ### Regra de prioridade (em relação ao dia de hoje):
            | Prazo até a entrega | Prioridade |
            |---|---|
            | Mais de 1 mês (> 30 dias) | 🟢 Baixa |
            | Menos de 1 mês e mais de 15 dias (16 a 30) | 🟠 Média |
            | Menos de 15 dias (ou atrasado) | 🔴 Alta |
        """)
    st.stop()

# ==================== CARREGAMENTO E FILTRAGEM ====================

COLUNAS_PEDIDOS = ["Compra", "Cód Confec", "Confeccionado", "Saldo", "Dt Entrega", "Confecção"]

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
df_kanban["Prioridade"] = df_kanban["Dt Entrega"].apply(calcular_prioridade)
df_kanban["Confecção"] = (
    df_kanban["Confecção"].fillna("").astype(str).str.strip().replace("", "Sem Confecção")
)
df_kanban["Confeccionado"] = df_kanban["Confeccionado"].fillna("").astype(str).str.strip()
df_kanban["Cód Confec"] = df_kanban["Cód Confec_norm"]

if df_kanban.empty:
    st.warning("Nenhum pedido encontrado para os códigos com Saldo 2 negativo no Estoque.")
    st.stop()

# ==================== FILTROS LATERAIS ====================

with st.sidebar:
    st.markdown("---")
    st.markdown("## 🔍 Filtros")

    confeccoes_unicas = sorted(df_kanban["Confecção"].unique().tolist())
    confeccoes_sel = st.multiselect(
        "Confecção",
        options=confeccoes_unicas,
        default=confeccoes_unicas,
    )

    prioridades_sel = st.multiselect(
        "Prioridade",
        options=["Alta", "Média", "Baixa"],
        default=["Alta", "Média", "Baixa"],
    )

    termo_busca = st.text_input("Buscar por código ou descrição:", value="")

df_filtrado = df_kanban[df_kanban["Confecção"].isin(confeccoes_sel)].copy()
df_filtrado = df_filtrado[df_filtrado["Prioridade"].isin(prioridades_sel)]

if termo_busca.strip():
    termo = termo_busca.strip().lower()
    df_filtrado = df_filtrado[
        df_filtrado["Cód Confec"].str.lower().str.contains(termo, na=False)
        | df_filtrado["Confeccionado"].str.lower().str.contains(termo, na=False)
    ]

# ==================== MÉTRICAS ====================

st.markdown("---")

ordem_prioridade = {"Alta": 0, "Média": 1, "Baixa": 2}
contagem_prio = df_filtrado["Prioridade"].value_counts()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total de Pedidos", len(df_filtrado))
with col2:
    st.metric("Confecções", df_filtrado["Confecção"].nunique())
with col3:
    st.metric("🔴 Prioridade Alta", int(contagem_prio.get("Alta", 0)))
with col4:
    st.metric("🟠 Prioridade Média", int(contagem_prio.get("Média", 0)))
with col5:
    st.metric("🟢 Prioridade Baixa", int(contagem_prio.get("Baixa", 0)))

st.markdown(
    f"<div class='kb-info-box'>📦 Quantidade total (Saldo): <b>{fmt_num(df_filtrado['Saldo'].sum())}</b> unidade(s) &nbsp;|&nbsp; "
    f"🔍 <b>{len(codigos_saldo2_neg)}</b> código(s) com Saldo 2 negativo no Estoque &nbsp;|&nbsp; "
    f"📅 Data de referência: <b>{date.today().strftime('%d/%m/%Y')}</b></div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ==================== RENDERIZAÇÃO DO KANBAN ====================

st.markdown("### 📌 Kanban por Confecção (abas)")

if df_filtrado.empty:
    st.warning("Nenhum pedido encontrado com os filtros selecionados.")
    st.stop()

# Ordenar cards por prioridade → data de entrega → compra
df_filtrado["_prio_ord"] = df_filtrado["Prioridade"].map(ordem_prioridade)
df_filtrado = df_filtrado.sort_values(
    ["_prio_ord", "Dt Entrega", "Compra"],
    ascending=[True, True, True],
)


def html_cards(df_col):
    """Monta o HTML dos cards (kanban) de uma confecção"""
    cards = ['<div class="kb-grid">']
    for _, row in df_col.iterrows():
        cls = classe_prioridade(row["Prioridade"])
        pedido = fmt_compra(row["Compra"])
        cod = html.escape(str(row["Cód Confec"]))
        desc_full = str(row["Confeccionado"]).strip()
        desc_curta = desc_full if len(desc_full) <= 140 else desc_full[:140] + "…"
        qtd = fmt_num(row["Saldo"])
        data = fmt_data(row["Dt Entrega"])
        prio = html.escape(str(row["Prioridade"]))
        dias_txt = html.escape(texto_dias(row["Dt Entrega"]))
        conf_esc = html.escape(str(row["Confecção"]))

        cards.append(
            f"""
            <div class="kb-card {cls}">
                <div class="kb-card-top">
                    <span class="kb-pedido" title="Pedido {html.escape(pedido)}">🛒 Pedido {html.escape(pedido)}</span>
                    <span class="kb-badge {cls}">{prio}</span>
                </div>
                <span class="kb-cod">Cód Confec: {cod}</span>
                <div class="kb-desc" title="{html.escape(desc_full)}">{html.escape(desc_curta)}</div>
                <span class="kb-conf">🏭 {conf_esc}</span>
                <div class="kb-footer">
                    <span class="kb-qtd">📦 Qtd: <b>{qtd}</b></span>
                    <span class="kb-data">📅 {data}</span>
                </div>
                <span class="kb-dias {cls}">{dias_txt}</span>
            </div>
            """
        )
    cards.append("</div>")
    return "".join(cards)


# Uma aba por confecção
confeccoes_abas = sorted(df_filtrado["Confecção"].unique().tolist())
abas = st.tabs([f"🏭 {conf[:30]}" for conf in confeccoes_abas])

for aba, confeccao in zip(abas, confeccoes_abas):
    with aba:
        df_col = df_filtrado[df_filtrado["Confecção"] == confeccao]
        total_qtd = df_col["Saldo"].sum()
        qtd_alta = int((df_col["Prioridade"] == "Alta").sum())
        qtd_media = int((df_col["Prioridade"] == "Média").sum())
        qtd_baixa = int((df_col["Prioridade"] == "Baixa").sum())

        st.markdown(
            f"""
            <div class="kb-tab-summary">
                🏭 <b>{html.escape(confeccao)}</b> &nbsp;·&nbsp;
                <b>{len(df_col)}</b> pedido(s) &nbsp;·&nbsp;
                📦 <b>{fmt_num(total_qtd)}</b> unidade(s) &nbsp;·&nbsp;
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
            st.markdown(html_cards(df_col), unsafe_allow_html=True)

# ==================== TABELA E EXPORTAÇÃO ====================

st.markdown("---")
st.markdown("### 📋 Detalhamento dos Pedidos (dados do kanban)")

df_tabela = df_filtrado[["Compra", "Cód Confec", "Confeccionado", "Saldo", "Dt Entrega", "Prioridade", "Confecção"]].copy()
df_tabela = df_tabela.rename(
    columns={
        "Compra": "Pedido",
        "Saldo": "Quantidade",
        "Dt Entrega": "Data de Entrega",
    }
).sort_values(["Confecção", "Prioridade", "Data de Entrega"])

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
        file_name=f"kanban_confeccao_{date.today().strftime('%d_%m_%Y')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_tabela.to_excel(writer, sheet_name="Kanban", index=False)
        resumo = (
            df_filtrado.groupby("Confecção")
            .agg(Pedidos=("Compra", "count"), Quantidade=("Saldo", "sum"))
            .reset_index()
        )
        resumo.to_excel(writer, sheet_name="Resumo_Confecções", index=False)
    st.download_button(
        "⬇️ Baixar Excel",
        data=buffer.getvalue(),
        file_name=f"kanban_confeccao_{date.today().strftime('%d_%m_%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
