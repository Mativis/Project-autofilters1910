"""
Análise de Estoque por item
---------------------------
Usa a planilha de Estoque e considera a composição dos saldos:

    Saldo 1 = Estoque físico
    Saldo 2 = Saldo 1 + Em trânsito
    Saldo 3 = Saldo 2 + Em confecção

Cruza com a demanda em aberto dos Pedidos (Saldo) para medir cobertura
e déficit de cada item.
"""

import io
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nucleo import (
    CORES_GRAFICO,
    TEMPLATE_PLOTLY,
    aplicar_estilo_comum,
    cabecalho,
    card,
    fmt_num,
    fmt_pct,
    preparar_estoque,
    preparar_pedidos,
    sidebar_arquivos,
)

st.set_page_config(
    page_title="Análise de Estoque",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_comum()

df_pedidos, df_estoque = sidebar_arquivos()

if df_estoque is None:
    st.info(
        "👆 Faça o upload do arquivo de **Estoque** na barra lateral para montar a análise por item. "
        "Se o arquivo de **Pedidos** também for enviado, a demanda em aberto entra no cálculo de cobertura."
    )
    st.stop()

df_estoque = preparar_estoque(df_estoque)
df_pedidos = preparar_pedidos(df_pedidos) if df_pedidos is not None else None

cabecalho(
    "🏭 Análise de Estoque por item",
    "Saldo 1 = físico · Saldo 2 = físico + em trânsito · Saldo 3 = físico + trânsito + em confecção — "
    f"data de referência: {date.today().strftime('%d/%m/%Y')}",
)

# ==================== FILTROS ====================

with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros")

    marcas_sel = st.multiselect(
        "Marca",
        options=sorted(df_estoque["Marca"].unique().tolist()),
        default=sorted(df_estoque["Marca"].unique().tolist()),
    )
    situacoes_sel = st.multiselect(
        "Situação",
        options=sorted(df_estoque["Situação"].unique().tolist()),
        default=sorted(df_estoque["Situação"].unique().tolist()),
    )
    colecoes_sel = st.multiselect(
        "Coleção",
        options=sorted(df_estoque["Coleção"].unique().tolist()),
        default=sorted(df_estoque["Coleção"].unique().tolist()),
    )
    top_n = st.slider("Top N nos gráficos", min_value=5, max_value=40, value=20, step=1)

    somente_negativos = st.checkbox(
        "Somente itens com Saldo 2 < 0",
        value=False,
        help="Mostra apenas os itens em que o físico + em trânsito é negativo (os que entram no Kanban).",
    )
    somente_sem_cobertura = st.checkbox(
        "Somente itens sem cobertura (Saldo 3 < 0)",
        value=False,
    )

# ==================== PREPARAÇÃO ====================

df = df_estoque.copy()
df = df[df["Marca"].isin(marcas_sel)]
df = df[df["Situação"].isin(situacoes_sel)]
df = df[df["Coleção"].isin(colecoes_sel)]

if somente_negativos:
    df = df[df["Saldo 2"] < 0]
if somente_sem_cobertura:
    df = df[df["Saldo 3"] < 0]

# Demanda em aberto vinda dos Pedidos
if df_pedidos is not None:
    demanda = (
        df_pedidos.groupby("Cód Confec_norm")
        .agg(
            Demanda=("Saldo", "sum"),
            Pedidos=("Compra", "count"),
            QtdPedida=("Qtd", "sum"),
        )
        .reset_index()
    )
    df = df.merge(demanda, on="Cód Confec_norm", how="left")
else:
    df["Demanda"] = np.nan
    df["Pedidos"] = np.nan
    df["QtdPedida"] = np.nan

df["Demanda"] = pd.to_numeric(df["Demanda"], errors="coerce").fillna(0)
df["Déficit"] = df["Saldo 3"] - df["Demanda"]
df["Cobertura"] = np.where(
    df["Demanda"] > 0, df["Saldo 3"] / df["Demanda"], np.nan
)


def classificar_item(row):
    """Situação de cobertura do item, conforme a composição dos saldos."""
    s1, s2, s3 = row["Saldo 1"], row["Saldo 2"], row["Saldo 3"]
    if pd.isna(s3):
        return "⚪ Sem dados"
    if s3 < 0:
        return "🔴 Sem cobertura"
    if s2 < 0:
        return "🟠 Só pela confecção"
    if s1 < 0:
        return "🟡 Só pelo trânsito"
    return "🟢 Coberto pelo físico"


df["Situação do item"] = df.apply(classificar_item, axis=1)

if df.empty:
    st.warning("Nenhum item encontrado com os filtros selecionados.")
    st.stop()

# ==================== KPIs ====================

n_itens = len(df)
s1 = df["Saldo 1"].sum()
s2 = df["Saldo 2"].sum()
s3 = df["Saldo 3"].sum()
em_transito = df["Em Trânsito"].sum()
em_confeccao = df["Em Confecção"].sum()
demanda = df["Demanda"].sum()
n_neg2 = int((df["Saldo 2"] < 0).sum())
n_sem_cob = int((df["Saldo 3"] < 0).sum())

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    st.markdown(card("Itens", f"{fmt_num(n_itens)}", "códigos no filtro"), unsafe_allow_html=True)
with k2:
    st.markdown(
        card("Saldo 1 (físico)", fmt_num(s1), "estoque físico", "#2e7d32"),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        card("Saldo 2 (+trânsito)", fmt_num(s2), f"trânsito: {fmt_num(em_transito)}", "#ef6c00"),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        card("Saldo 3 (+confecção)", fmt_num(s3), f"confecção: {fmt_num(em_confeccao)}", "#667eea"),
        unsafe_allow_html=True,
    )
with k5:
    st.markdown(
        card("Itens com Saldo 2 < 0", f"{n_neg2}", "entram no Kanban", "#b71c1c"),
        unsafe_allow_html=True,
    )
with k6:
    st.markdown(
        card("Demanda em aberto", fmt_num(demanda), "soma do Saldo dos pedidos", "#764ba2"),
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='db-aviso'>🏭 <b>Sem cobertura</b>: {n_sem_cob} item(ns) com Saldo 3 negativo — "
    "nem o físico, nem o trânsito, nem a produção em curso cobrem a posição de estoque.</div>",
    unsafe_allow_html=True,
)

# ==================== 1. COMPOSIÇÃO DO ESTOQUE ====================

st.markdown('<div class="db-secao">🧱 Composição do saldo por item</div>', unsafe_allow_html=True)

df_ord = df.reindex(
    df["Saldo 3"].abs().sort_values(ascending=False).index
).head(top_n).copy()
df_ord["Item"] = (
    df_ord["Descrição"].astype(str).str.slice(0, 40)
    + " ("
    + df_ord["Cód Confec"].astype(str)
    + ")"
)

fig = px.bar(
    df_ord.sort_values("Saldo 3"),
    x="Saldo 1",
    y="Item",
    orientation="h",
    title=f"Top {len(df_ord)} itens — físico (Saldo 1), trânsito e confecção",
    labels={"Saldo 1": "Saldo 1 (físico)", "Item": ""},
    template=TEMPLATE_PLOTLY,
)
fig.add_bar(
    x=df_ord.sort_values("Saldo 3")["Em Trânsito"],
    y=df_ord.sort_values("Saldo 3")["Item"],
    orientation="h",
    name="Em trânsito",
    marker_color="#ff9800",
    hovertemplate="Trânsito: %{x}<extra></extra>",
)
fig.add_bar(
    x=df_ord.sort_values("Saldo 3")["Em Confecção"],
    y=df_ord.sort_values("Saldo 3")["Item"],
    orientation="h",
    name="Em confecção",
    marker_color="#4caf50",
    hovertemplate="Confecção: %{x}<extra></extra>",
)
fig.update_layout(
    barmode="relative",
    height=max(420, 26 * len(df_ord)),
    legend=dict(orientation="h", y=1.1),
    margin=dict(t=60, l=10, r=10, b=10),
)
st.plotly_chart(fig, width="stretch")

# ==================== 2. SITUAÇÃO DOS ITENS ====================

col_a, col_b = st.columns([1, 1.4])

with col_a:
    cont = df.groupby("Situação do item").size().reset_index(name="Itens")
    fig = px.pie(
        cont,
        names="Situação do item",
        values="Itens",
        hole=0.45,
        color_discrete_sequence=CORES_GRAFICO,
        title="Itens por situação de cobertura",
        template=TEMPLATE_PLOTLY,
    )
    fig.update_layout(height=400, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

with col_b:
    df_marca = (
        df.groupby("Marca")
        .agg(
            Itens=("Cód Confec", "count"),
            Saldo1=("Saldo 1", "sum"),
            Saldo2=("Saldo 2", "sum"),
            Saldo3=("Saldo 3", "sum"),
        )
        .reset_index()
        .sort_values("Saldo3", ascending=False)
    )
    fig = px.bar(
        df_marca,
        x="Marca",
        y=["Saldo1", "Saldo2", "Saldo3"],
        barmode="group",
        labels={"value": "Unidades", "variable": ""},
        color_discrete_map={"Saldo1": "#2e7d32", "Saldo2": "#ff9800", "Saldo3": "#667eea"},
        title="Saldo 1, 2 e 3 por marca",
        template=TEMPLATE_PLOTLY,
    )
    fig.update_layout(height=400, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ==================== 3. COBERTURA DA DEMANDA ====================

st.markdown('<div class="db-secao">🎯 Cobertura da demanda (estoque × pedidos)</div>', unsafe_allow_html=True)

df_dem = df[df["Demanda"] > 0].copy()

if df_dem.empty:
    st.info("Não há demanda em aberto (Pedidos) para os itens selecionados.")
else:
    fig = px.scatter(
        df_dem,
        x="Saldo 3",
        y="Demanda",
        color="Marca",
        size="QtdPedida" if "QtdPedida" in df_dem else "Demanda",
        hover_name="Descrição",
        hover_data={"Saldo 3": ":,.0f", "Demanda": ":,.0f", "Cobertura": ":.2f"},
        labels={"Saldo 3": "Saldo 3 (estoque total)", "Demanda": "Demanda em aberto (pedidos)"},
        title="Cobertura por item — pontos abaixo da diagonal estão em déficit",
        template=TEMPLATE_PLOTLY,
    )
    limite = float(max(df_dem["Saldo 3"].max(), df_dem["Demanda"].max())) or 1
    fig.add_trace(
        go.Scatter(
            x=[0, limite],
            y=[0, limite],
            mode="lines",
            name="Saldo 3 = Demanda",
            line=dict(color="#b71c1c", dash="dash", width=2),
        )
    )
    fig.update_layout(height=470, margin=dict(t=55, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

    df_def = df_dem.sort_values("Déficit").copy()
    df_def["Item"] = (
        df_def["Descrição"].astype(str).str.slice(0, 40)
        + " ("
        + df_def["Cód Confec"].astype(str)
        + ")"
    )
    fig = px.bar(
        df_def.head(top_n).sort_values("Déficit"),
        x="Déficit",
        y="Item",
        orientation="h",
        color="Déficit",
        color_continuous_scale=["#c62828", "#e8f5e9"],
        labels={"Déficit": "Saldo 3 − Demanda", "Item": ""},
        title=f"Top {min(top_n, len(df_def))} itens em déficit",
        template=TEMPLATE_PLOTLY,
    )
    fig.update_layout(height=max(420, 26 * min(top_n, len(df_def))), coloraxis_showscale=False, margin=dict(t=55, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ==================== TABELA POR ITEM ====================

st.markdown("---")
st.markdown("### 📋 Análise por item")

colunas_tabela = [
    "Marca",
    "Cód Confec",
    "Descrição",
    "Saldo 1",
    "Em Trânsito",
    "Saldo 2",
    "Em Confecção",
    "Saldo 3",
    "Carteira sem Fat",
    "Demanda",
    "Déficit",
    "Situação do item",
    "Coleção",
    "Situação",
]

tabela = df[[c for c in colunas_tabela if c in df.columns]].copy()
tabela = tabela.sort_values("Saldo 3")

st.dataframe(
    tabela,
    width="stretch",
    hide_index=True,
    column_config={
        "Marca": st.column_config.TextColumn("Marca", width="small"),
        "Cód Confec": st.column_config.TextColumn("Cód Confec", width="small"),
        "Descrição": st.column_config.TextColumn("Descrição", width="large"),
        "Saldo 1": st.column_config.NumberColumn("Saldo 1 (físico)", format="%d"),
        "Em Trânsito": st.column_config.NumberColumn("Em Trânsito", format="%d"),
        "Saldo 2": st.column_config.NumberColumn("Saldo 2", format="%d"),
        "Em Confecção": st.column_config.NumberColumn("Em Confecção", format="%d"),
        "Saldo 3": st.column_config.NumberColumn("Saldo 3", format="%d"),
        "Carteira sem Fat": st.column_config.NumberColumn("Carteira sem Fat", format="%d"),
        "Demanda": st.column_config.NumberColumn("Demanda", format="%d"),
        "Déficit": st.column_config.NumberColumn("Déficit", format="%d"),
        "Situação do item": st.column_config.TextColumn("Situação", width="medium"),
        "Coleção": st.column_config.TextColumn("Coleção", width="small"),
        "Situação": st.column_config.TextColumn("Situação ERP", width="small"),
    },
)

# ==================== EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar a análise")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Por Item")
    (
        df.groupby(["Marca", "Situação do item"])
        .agg(
            Itens=("Cód Confec", "count"),
            Saldo1=("Saldo 1", "sum"),
            Saldo2=("Saldo 2", "sum"),
            Saldo3=("Saldo 3", "sum"),
            Demanda=("Demanda", "sum"),
        )
        .reset_index()
        .to_excel(writer, index=False, sheet_name="Resumo")
    )

c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "📥 Baixar CSV — análise por item",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"analise_estoque_{date.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        width="stretch",
    )
with c2:
    st.download_button(
        "📊 Baixar Excel — análise por item",
        data=buffer.getvalue(),
        file_name=f"analise_estoque_{date.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
