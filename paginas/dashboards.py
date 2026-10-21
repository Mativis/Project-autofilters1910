"""
Dashboards de Pedidos
---------------------
Concentração de marca, concentração de código de confecção, volume de
pedidos e eficácia (Saldo ÷ Qtd), usando as mesmas planilhas do Kanban.
"""

import io
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nucleo import (
    CORES_PRIORIDADE,
    aplicar_estilo_comum,
    cabecalho,
    card,
    codigos_saldo2_negativo,
    cores_grafico,
    fmt_data,
    fmt_num,
    fmt_pct,
    preparar_estoque,
    preparar_pedidos,
    sidebar_arquivos,
    template_plotly,
)

st.set_page_config(
    page_title="Dashboards de Pedidos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_comum()

df_pedidos, df_estoque = sidebar_arquivos()

if df_pedidos is None:
    st.info(
        "👆 Faça o upload do arquivo de **Pedidos** na barra lateral para montar os dashboards. "
        "Se o arquivo de **Estoque** também for enviado, é possível restringir a análise aos itens "
        "que entram no Kanban (Saldo 2 negativo)."
    )
    st.stop()

df_pedidos = preparar_pedidos(df_pedidos)
df_estoque = preparar_estoque(df_estoque) if df_estoque is not None else None

cabecalho(
    "📊 Dashboards de Pedidos",
    "Concentração de marca e de código, volume de pedidos, eficácia (Saldo ÷ Qtd) "
    f"e detalhamento por confecção — data de referência: {date.today().strftime('%d/%m/%Y')}",
)

# ==================== FILTROS ====================

with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros")

    marcas_sel = st.multiselect(
        "Marca",
        options=sorted(df_pedidos["Marca"].unique().tolist()),
        default=sorted(df_pedidos["Marca"].unique().tolist()),
    )
    confeccoes_sel = st.multiselect(
        "Confecção",
        options=sorted(df_pedidos["Confecção"].unique().tolist()),
        default=sorted(df_pedidos["Confecção"].unique().tolist()),
    )
    status_sel = st.multiselect(
        "Status",
        options=sorted(df_pedidos["Status"].unique().tolist()),
        default=sorted(df_pedidos["Status"].unique().tolist()),
    )

    if "Dt Emissao" in df_pedidos.columns and df_pedidos["Dt Emissao"].notna().any():
        emissao = df_pedidos["Dt Emissao"].dropna()
        data_min = emissao.min().date()
        data_max = emissao.max().date()
        periodo = st.date_input(
            "Período de emissão",
            value=(data_min, data_max),
            min_value=data_min,
            max_value=data_max,
            format="DD/MM/YYYY",
        )
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            data_ini, data_fim = periodo
        else:
            data_ini, data_fim = data_min, data_max
    else:
        data_ini = data_fim = None

    top_n = st.slider("Top N nos rankings", min_value=5, max_value=30, value=15, step=1)

    usar_saldo2 = st.checkbox(
        "Restringir aos itens do Kanban (Saldo 2 < 0)",
        value=False,
        disabled=df_estoque is None,
        help=(
            "Mostra apenas os códigos de confecção que estão com Saldo 2 negativo no Estoque "
            "(os mesmos que aparecem no Kanban)."
        ),
    )

# ==================== FILTRAGEM ====================

df = df_pedidos.copy()
df = df[df["Marca"].isin(marcas_sel)]
df = df[df["Confecção"].isin(confeccoes_sel)]
df = df[df["Status"].isin(status_sel)]
if data_ini is not None and "Dt Emissao" in df.columns:
    df = df[
        (df["Dt Emissao"].dt.date >= data_ini) & (df["Dt Emissao"].dt.date <= data_fim)
    ]
if usar_saldo2 and df_estoque is not None:
    codigos = codigos_saldo2_negativo(df_estoque)
    df = df[df["Cód Confec_norm"].isin(codigos)]

if df.empty:
    st.warning("Nenhum pedido encontrado com os filtros selecionados.")
    st.stop()

# ==================== KPIs ====================

qtd_total = df["Qtd"].sum(min_count=1)
saldo_total = df["Saldo"].sum(min_count=1)
eficacia_global = (saldo_total / qtd_total) if qtd_total else np.nan
n_atrasados = int((df["Prioridade"] == "Atrasado").sum())

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    st.markdown(card("Pedidos", f"{fmt_num(len(df))}", "linhas de pedido"), unsafe_allow_html=True)
with k2:
    st.markdown(card("Unidades pedidas", fmt_num(qtd_total), "soma de Qtd"), unsafe_allow_html=True)
with k3:
    st.markdown(card("Saldo em aberto", fmt_num(saldo_total), "soma de Saldo"), unsafe_allow_html=True)
with k4:
    st.markdown(
        card("Eficácia", fmt_pct(eficacia_global), "Saldo ÷ Qtd", "#667eea"),
        unsafe_allow_html=True,
    )
with k5:
    st.markdown(card("Marcas", f"{df['Marca'].nunique()}", "marcas distintas"), unsafe_allow_html=True)
with k6:
    st.markdown(
        card("Atrasados", f"{n_atrasados}", "entrega vencida", "#b71c1c"),
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='db-aviso'>💡 <b>Eficácia</b> = Saldo ÷ Qtd — quanto do pedido continua em aberto. "
    "100% = nada foi entregue, 0% = pedido totalmente encerrado.</div>",
    unsafe_allow_html=True,
)

# ==================== 1. CONCENTRAÇÃO DE MARCA ====================

st.markdown('<div class="db-secao">🏷️ Concentração de marca</div>', unsafe_allow_html=True)

df_marca = (
    df.groupby("Marca")
    .agg(
        Pedidos=("Compra", "count"),
        Qtd=("Qtd", "sum"),
        Saldo=("Saldo", "sum"),
    )
    .reset_index()
)
df_marca["Eficácia"] = np.where(df_marca["Qtd"] > 0, df_marca["Saldo"] / df_marca["Qtd"], np.nan)
df_marca["% Pedido"] = df_marca["Qtd"] / df_marca["Qtd"].sum() if df_marca["Qtd"].sum() else 0
df_marca = df_marca.sort_values("Qtd", ascending=False).reset_index(drop=True)
df_marca["Acumulado %"] = df_marca["% Pedido"].cumsum()

top_marcas = df_marca.head(top_n).copy()

col_a, col_b = st.columns([1.25, 1])

with col_a:
    fig = px.bar(
        top_marcas.sort_values("Qtd"),
        x="Qtd",
        y="Marca",
        orientation="h",
        text=top_marcas["% Pedido"].map(lambda v: f"{v * 100:.1f}%"),
        color="% Pedido",
        color_continuous_scale=["#dfe6fb", "#667eea"],
        labels={"Qtd": "Unidades pedidas", "Marca": "", "% Pedido": "% do total"},
        title=f"Top {len(top_marcas)} marcas por volume pedido",
        template=template_plotly(),
    )
    fig.update_layout(height=420, coloraxis_showscale=False, margin=dict(t=50, l=10, r=10, b=10))
    fig.update_traces(textposition="outside", cliponaxis=False)
    st.plotly_chart(fig, width="stretch")

with col_b:
    fig = px.treemap(
        df_marca,
        path=["Marca"],
        values="Qtd",
        color="% Pedido",
        color_continuous_scale=["#dfe6fb", "#667eea"],
        title="Participação das marcas no volume pedido",
        template=template_plotly(),
    )
    fig.update_layout(height=420, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

with st.expander("📋 Tabela — concentração por marca"):
    st.dataframe(
        df_marca.rename(
            columns={
                "Marca": "Marca",
                "Pedidos": "Pedidos",
                "Qtd": "Qtd",
                "Saldo": "Saldo",
                "Eficácia": "Eficácia",
                "% Pedido": "% do volume",
                "Acumulado %": "% acumulado",
            }
        )[
            ["Marca", "Pedidos", "Qtd", "Saldo", "Eficácia", "% do volume", "% acumulado"]
        ].style.format(
            {"Eficácia": "{:.1%}", "% do volume": "{:.1%}", "% acumulado": "{:.1%}"}
        ),
        width="stretch",
        hide_index=True,
    )

# ==================== 2. CONCENTRAÇÃO DE CÓD CONFEC ====================

st.markdown(
    '<div class="db-secao">🔢 Concentração de código de confecção (Cód Confec)</div>',
    unsafe_allow_html=True,
)

df_cod = (
    df.groupby(["Cód Confec", "Confeccionado"])
    .agg(
        Pedidos=("Compra", "count"),
        Qtd=("Qtd", "sum"),
        Saldo=("Saldo", "sum"),
        Confecoes=("Confecção", "nunique"),
    )
    .reset_index()
)
df_cod["Eficácia"] = np.where(df_cod["Qtd"] > 0, df_cod["Saldo"] / df_cod["Qtd"], np.nan)
df_cod["% Pedido"] = df_cod["Qtd"] / df_cod["Qtd"].sum() if df_cod["Qtd"].sum() else 0
df_cod = df_cod.sort_values("Qtd", ascending=False).reset_index(drop=True)
df_cod["Acumulado %"] = df_cod["% Pedido"].cumsum()

top_cod = df_cod.head(top_n).copy()

fig = go.Figure()
fig.add_bar(
    x=top_cod["Cód Confec"].astype(str),
    y=top_cod["Qtd"],
    name="Qtd",
    marker_color="#667eea",
    hovertemplate="Cód %{x}<br>Qtd: %{y}<extra></extra>",
)
fig.add_scatter(
    x=top_cod["Cód Confec"].astype(str),
    y=top_cod["Acumulado %"] * 100,
    name="% acumulado",
    yaxis="y2",
    mode="lines+markers",
    line=dict(color="#f44336", width=2),
    hovertemplate="Cód %{x}<br>Acumulado: %{y:.1f}%<extra></extra>",
)
fig.update_layout(
    template=template_plotly(),
    height=430,
    title=f"Pareto — top {len(top_cod)} códigos por volume pedido",
    xaxis_title="Cód Confec",
    yaxis_title="Unidades pedidas",
    yaxis2=dict(title="% acumulado", overlaying="y", side="right", range=[0, 105], showgrid=False),
    legend=dict(orientation="h", y=1.12),
    margin=dict(t=60, l=10, r=10, b=10),
)
st.plotly_chart(fig, width="stretch")

with st.expander("📋 Tabela — concentração por código"):
    st.dataframe(
        df_cod[
            ["Cód Confec", "Confeccionado", "Confecoes", "Pedidos", "Qtd", "Saldo", "Eficácia", "% Pedido", "Acumulado %"]
        ].rename(
            columns={
                "Cód Confec": "Cód Confec",
                "Confeccionado": "Descrição",
                "Confecoes": "Confecções",
                "Pedidos": "Pedidos",
                "Qtd": "Qtd",
                "Saldo": "Saldo",
                "Eficácia": "Eficácia",
                "% Pedido": "% do volume",
                "Acumulado %": "% acumulado",
            }
        ).style.format(
            {"Eficácia": "{:.1%}", "% do volume": "{:.1%}", "% acumulado": "{:.1%}"}
        ),
        width="stretch",
        hide_index=True,
    )

# ==================== 3. PEDIDOS ====================

st.markdown('<div class="db-secao">🧾 Pedidos</div>', unsafe_allow_html=True)

col_c, col_d = st.columns([1.3, 1])

with col_c:
    if "Dt Emissao" in df.columns and df["Dt Emissao"].notna().any():
        df_mes = (
            df.dropna(subset=["Dt Emissao"])
            .groupby(df["Dt Emissao"].dt.to_period("M").dt.to_timestamp())
            .agg(Qtd=("Qtd", "sum"), Pedidos=("Compra", "count"))
            .reset_index()
            .rename(columns={"Dt Emissao": "Mês"})
        )
        fig = px.area(
            df_mes,
            x="Mês",
            y="Qtd",
            color_discrete_sequence=["#667eea"],
            title="Evolução do volume pedido por mês de emissão",
            template=template_plotly(),
        )
        fig.update_layout(height=380, margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("O arquivo de Pedidos não possui a coluna `Dt Emissao`.")

with col_d:
    df_status = df.groupby("Status").agg(Qtd=("Qtd", "sum")).reset_index()
    fig = px.pie(
        df_status,
        names="Status",
        values="Qtd",
        color_discrete_sequence=cores_grafico(),
        hole=0.45,
        title="Participação por status do pedido",
        template=template_plotly(),
    )
    fig.update_layout(height=380, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

df_conf = (
    df.groupby("Confecção")
    .agg(
        Pedidos=("Compra", "count"),
        Códigos=("Cód Confec_norm", "nunique"),
        Marcas=("Marca", "nunique"),
        Qtd=("Qtd", "sum"),
        Saldo=("Saldo", "sum"),
        Atrasados=("Prioridade", lambda serie: int((serie == "Atrasado").sum())),
        PróximaEntrega=("Dt Entrega", "min"),
    )
    .reset_index()
    .sort_values("Qtd", ascending=False)
    .reset_index(drop=True)
)
df_conf["Entregue"] = df_conf["Qtd"] - df_conf["Saldo"]
df_conf["Eficácia"] = np.where(df_conf["Qtd"] > 0, df_conf["Saldo"] / df_conf["Qtd"], np.nan)
df_conf["% do volume"] = (
    df_conf["Qtd"] / df_conf["Qtd"].sum() if df_conf["Qtd"].sum() else 0
)

fig = px.bar(
    df_conf.head(top_n).sort_values("Qtd"),
    x="Qtd",
    y="Confecção",
    orientation="h",
    color="Saldo",
    color_continuous_scale=["#e8f5e9", "#2e7d32"],
    labels={"Qtd": "Unidades pedidas", "Confecção": "", "Saldo": "Saldo em aberto"},
    title=f"Top {min(top_n, len(df_conf))} confecções por volume pedido",
    template=template_plotly(),
)
fig.update_layout(height=420, coloraxis_showscale=False, margin=dict(t=50, l=10, r=10, b=10))
st.plotly_chart(fig, width="stretch")

# ==================== 4. EFICÁCIA ====================

st.markdown('<div class="db-secao">📈 Eficácia dos pedidos (Saldo ÷ Qtd)</div>', unsafe_allow_html=True)

FAIXAS = [
    ("🔴 Sem saldo (0%)", 0.0, 0.0001),
    ("🟠 Quase encerrado (0-25%)", 0.0001, 0.25),
    ("🟡 Parcial (25-50%)", 0.25, 0.5),
    ("🟢 Maior parte aberta (50-75%)", 0.5, 0.75),
    ("🔵 Integralmente aberto (75-100%)", 0.75, 1.0001),
    ("⚫ Acima de 100%", 1.0001, np.inf),
]


def classificar_eficacia(valor):
    if pd.isna(valor):
        return "Sem dados"
    for nome, ini, fim in FAIXAS:
        if ini <= valor < fim:
            return nome
    return "Sem dados"


df["Faixa"] = df["Eficacia"].apply(classificar_eficacia)
ordem_faixas = [f[0] for f in FAIXAS] + ["Sem dados"]
df_faixa = (
    df.groupby("Faixa")
    .agg(Pedidos=("Compra", "count"), Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"))
    .reindex([f for f in ordem_faixas if f in df["Faixa"].unique()])
    .reset_index()
    .fillna(0)
)

col_e, col_f = st.columns(2)

with col_e:
    fig = px.bar(
        df_faixa,
        x="Faixa",
        y="Pedidos",
        color="Saldo",
        color_continuous_scale=["#fdecea", "#c62828"],
        labels={"Faixa": "", "Pedidos": "Pedidos"},
        title="Distribuição dos pedidos por faixa de eficácia",
        template=template_plotly(),
    )
    fig.update_layout(height=400, coloraxis_showscale=False, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

with col_f:
    ef_marca = (
        df.groupby("Marca")
        .agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"))
        .reset_index()
    )
    ef_marca["Eficácia"] = np.where(ef_marca["Qtd"] > 0, ef_marca["Saldo"] / ef_marca["Qtd"], np.nan)
    ef_marca = ef_marca.dropna(subset=["Eficácia"]).sort_values("Eficácia", ascending=False)
    fig = px.bar(
        ef_marca,
        x="Eficácia",
        y="Marca",
        orientation="h",
        color="Eficácia",
        color_continuous_scale=["#2e7d32", "#ff9800", "#c62828"],
        labels={"Eficácia": "Eficácia (Saldo ÷ Qtd)", "Marca": ""},
        title="Eficácia média por marca",
        template=template_plotly(),
    )
    fig.update_layout(height=400, coloraxis_showscale=False, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

itens_baixa = (
    df.dropna(subset=["Eficacia"])
    .groupby(["Cód Confec", "Confeccionado"])
    .agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"), Pedidos=("Compra", "count"))
    .reset_index()
)
itens_baixa["Eficácia"] = np.where(
    itens_baixa["Qtd"] > 0, itens_baixa["Saldo"] / itens_baixa["Qtd"], np.nan
)
itens_baixa = itens_baixa.dropna(subset=["Eficácia"]).sort_values("Eficácia")
itens_baixa["Descrição"] = (
    itens_baixa["Confeccionado"].astype(str).str.slice(0, 42) + "…"
)

fig = px.bar(
    itens_baixa.head(top_n),
    x="Eficácia",
    y="Descrição",
    orientation="h",
    color="Eficácia",
    color_continuous_scale=["#c62828", "#ff9800", "#2e7d32"],
    labels={"Eficácia": "Eficácia (Saldo ÷ Qtd)", "Descrição": ""},
    title=f"itens com menor eficácia (Top {min(top_n, len(itens_baixa))})",
    template=template_plotly(),
)
fig.update_layout(height=430, coloraxis_showscale=False, margin=dict(t=50, l=10, r=10, b=10))
st.plotly_chart(fig, width="stretch")

# ==================== 5. DETALHAMENTO POR CONFECÇÃO ====================

st.markdown('<div class="db-secao">🏭 Detalhamento por confecção</div>', unsafe_allow_html=True)

st.caption(
    "Primeiro o comparativo entre todas as confecções do filtro atual; "
    "abaixo, o detalhe da confecção selecionada."
)

# --- 5.1 Comparativo entre confecções ---
_conf_ord = df_conf.sort_values("Qtd")

fig = go.Figure()
fig.add_bar(
    y=_conf_ord["Confecção"],
    x=_conf_ord["Entregue"],
    name="Entregue (Qtd − Saldo)",
    orientation="h",
    marker_color="#2e7d32",
    hovertemplate="%{y}<br>Entregue: %{x:,.0f}<extra></extra>",
)
fig.add_bar(
    y=_conf_ord["Confecção"],
    x=_conf_ord["Saldo"],
    name="Saldo em aberto",
    orientation="h",
    marker_color="#ff9800",
    hovertemplate="%{y}<br>Saldo em aberto: %{x:,.0f}<extra></extra>",
)
fig.update_layout(
    template=template_plotly(),
    height=max(240, 46 * len(_conf_ord) + 100),
    barmode="stack",
    title="Volume por confecção — entregue × saldo em aberto",
    xaxis_title="Unidades",
    legend=dict(orientation="h", y=1.12),
    margin=dict(t=60, l=10, r=10, b=10),
)
st.plotly_chart(fig, width="stretch")

_conf_tab = df_conf.copy()
_conf_tab["Próxima entrega"] = _conf_tab["PróximaEntrega"].map(fmt_data)

st.dataframe(
    _conf_tab[
        [
            "Confecção",
            "Pedidos",
            "Códigos",
            "Marcas",
            "Qtd",
            "Entregue",
            "Saldo",
            "Eficácia",
            "% do volume",
            "Atrasados",
            "Próxima entrega",
        ]
    ].style.format(
        {
            "Eficácia": "{:.1%}",
            "% do volume": "{:.1%}",
            "Qtd": "{:,.0f}",
            "Entregue": "{:,.0f}",
            "Saldo": "{:,.0f}",
        }
    ),
    width="stretch",
    hide_index=True,
)

# --- 5.2 Detalhe da confecção selecionada ---
st.markdown("#### 🔎 Detalhe por confecção")

conf_sel = st.selectbox(
    "Confecção",
    options=df_conf["Confecção"].tolist(),
    index=0,
    help="Selecione a confecção para ver os indicadores e os gráficos detalhados.",
)

dfc = df[df["Confecção"] == conf_sel].copy()

d_qtd = dfc["Qtd"].sum(min_count=1)
d_saldo = dfc["Saldo"].sum(min_count=1)
d_efic = (d_saldo / d_qtd) if d_qtd else np.nan
d_atras = int((dfc["Prioridade"] == "Atrasado").sum())

d1, d2, d3, d4, d5, d6 = st.columns(6)
with d1:
    st.markdown(card("Pedidos", fmt_num(len(dfc)), "linhas de pedido"), unsafe_allow_html=True)
with d2:
    st.markdown(card("Unidades pedidas", fmt_num(d_qtd), "soma de Qtd"), unsafe_allow_html=True)
with d3:
    st.markdown(
        card("Entregue", fmt_num(d_qtd - d_saldo), "Qtd − Saldo", "#2e7d32"),
        unsafe_allow_html=True,
    )
with d4:
    st.markdown(card("Saldo em aberto", fmt_num(d_saldo), "soma de Saldo"), unsafe_allow_html=True)
with d5:
    st.markdown(
        card("Eficácia", fmt_pct(d_efic), "Saldo ÷ Qtd", "#667eea"),
        unsafe_allow_html=True,
    )
with d6:
    st.markdown(
        card("Atrasados", f"{d_atras}", "entrega vencida", "#b71c1c"),
        unsafe_allow_html=True,
    )

col_g, col_h = st.columns(2)

with col_g:
    dfc_marca = (
        dfc.groupby("Marca")
        .agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"))
        .reset_index()
    )
    dfc_marca["Entregue"] = dfc_marca["Qtd"] - dfc_marca["Saldo"]
    dfc_marca = dfc_marca.sort_values("Qtd")

    fig = go.Figure()
    fig.add_bar(
        y=dfc_marca["Marca"],
        x=dfc_marca["Entregue"],
        name="Entregue",
        orientation="h",
        marker_color="#2e7d32",
        hovertemplate="%{y}<br>Entregue: %{x:,.0f}<extra></extra>",
    )
    fig.add_bar(
        y=dfc_marca["Marca"],
        x=dfc_marca["Saldo"],
        name="Saldo em aberto",
        orientation="h",
        marker_color="#ff9800",
        hovertemplate="%{y}<br>Saldo: %{x:,.0f}<extra></extra>",
    )
    fig.update_layout(
        template=template_plotly(),
        height=360,
        barmode="stack",
        title="Volume por marca nesta confecção",
        xaxis_title="Unidades",
        legend=dict(orientation="h", y=1.12),
        margin=dict(t=60, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

with col_h:
    dfc["Faixa"] = dfc["Eficacia"].apply(classificar_eficacia)
    dfc_faixa = (
        dfc.groupby("Faixa")
        .agg(Pedidos=("Compra", "count"), Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"))
        .reindex([f for f in ordem_faixas if f in dfc["Faixa"].unique()])
        .reset_index()
        .fillna(0)
    )
    fig = px.bar(
        dfc_faixa,
        x="Faixa",
        y="Pedidos",
        color="Saldo",
        color_continuous_scale=["#fdecea", "#c62828"],
        labels={"Faixa": "", "Pedidos": "Pedidos"},
        title="Pedidos por faixa de eficácia nesta confecção",
        template=template_plotly(),
    )
    fig.update_layout(
        height=360,
        coloraxis_showscale=False,
        margin=dict(t=50, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

col_i, col_j = st.columns(2)

with col_i:
    dfc_cod = (
        dfc.groupby(["Cód Confec", "Confeccionado"])
        .agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"), Pedidos=("Compra", "count"))
        .reset_index()
    )
    dfc_cod["Eficácia"] = np.where(
        dfc_cod["Qtd"] > 0, dfc_cod["Saldo"] / dfc_cod["Qtd"], np.nan
    )
    dfc_cod = dfc_cod.sort_values("Saldo", ascending=False).head(10)
    dfc_cod["Rótulo"] = (
        dfc_cod["Cód Confec"].astype(str)
        + " · "
        + dfc_cod["Confeccionado"].astype(str).str.slice(0, 26)
    )
    fig = px.bar(
        dfc_cod.sort_values("Saldo"),
        x="Saldo",
        y="Rótulo",
        orientation="h",
        color="Eficácia",
        color_continuous_scale=["#2e7d32", "#ff9800", "#c62828"],
        labels={"Saldo": "Saldo em aberto", "Rótulo": "", "Eficácia": "Eficácia"},
        title="Top 10 códigos com maior saldo em aberto",
        template=template_plotly(),
    )
    fig.update_layout(
        height=360,
        coloraxis_showscale=False,
        margin=dict(t=50, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

with col_j:
    if "Dt Emissao" in dfc.columns and dfc["Dt Emissao"].notna().any():
        dfc_mes = (
            dfc.dropna(subset=["Dt Emissao"])
            .groupby(dfc["Dt Emissao"].dt.to_period("M").dt.to_timestamp())
            .agg(Qtd=("Qtd", "sum"), Pedidos=("Compra", "count"))
            .reset_index()
            .rename(columns={"Dt Emissao": "Mês"})
        )
        fig = px.area(
            dfc_mes,
            x="Mês",
            y="Qtd",
            color_discrete_sequence=["#667eea"],
            title="Evolução do volume pedido por mês de emissão",
            template=template_plotly(),
        )
        fig.update_layout(height=360, margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        dfc_prio = (
            dfc.groupby("Prioridade")
            .agg(Pedidos=("Compra", "count"), Saldo=("Saldo", "sum"))
            .reindex(["Atrasado", "Alta", "Média", "Baixa"])
            .dropna(how="all")
            .reset_index()
        )
        fig = px.bar(
            dfc_prio,
            x="Prioridade",
            y="Pedidos",
            color="Prioridade",
            color_discrete_map={k: v for k, v in CORES_PRIORIDADE.items()},
            title="Pedidos por prioridade",
            template=template_plotly(),
        )
        fig.update_layout(height=360, showlegend=False, margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig, width="stretch")

with st.expander(f"📋 Pedidos da confecção — {conf_sel}"):
    colunas_pedido = [
        "Compra",
        "Cód Confec",
        "Confeccionado",
        "Marca",
        "Qtd",
        "Saldo",
        "Eficacia",
        "Dt Entrega",
        "Prioridade",
        "Status",
    ]
    dfc_tab = (
        dfc[colunas_pedido]
        .sort_values("Dt Entrega", na_position="last")
        .copy()
    )
    dfc_tab["Dt Entrega"] = dfc_tab["Dt Entrega"].map(fmt_data)
    st.dataframe(
        dfc_tab.style.format(
            {
                "Qtd": "{:,.0f}",
                "Saldo": "{:,.0f}",
                "Eficacia": "{:.1%}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "📥 Baixar CSV — pedidos desta confecção",
        data=dfc_tab.to_csv(index=False, encoding="utf-8-sig"),
        file_name=(
            f"pedidos_{conf_sel.split()[0].lower()}_"
            f"{date.today().strftime('%Y-%m-%d')}.csv"
        ),
        mime="text/csv",
        width="stretch",
    )

# ==================== EXPORTAÇÃO ====================

st.markdown("---")
st.markdown("### 📥 Exportar os agregados do dashboard")

df_conf_marca = (
    df.groupby(["Confecção", "Marca"])
    .agg(Pedidos=("Compra", "count"), Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"))
    .reset_index()
    .sort_values(["Confecção", "Qtd"], ascending=[True, False])
)
df_conf_marca["Entregue"] = df_conf_marca["Qtd"] - df_conf_marca["Saldo"]
df_conf_marca["Eficácia"] = np.where(
    df_conf_marca["Qtd"] > 0, df_conf_marca["Saldo"] / df_conf_marca["Qtd"], np.nan
)

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_marca.to_excel(writer, index=False, sheet_name="Por Marca")
    df_cod.to_excel(writer, index=False, sheet_name="Por Cod Confec")
    df_conf.to_excel(writer, index=False, sheet_name="Por Confeccao")
    df_conf_marca.to_excel(writer, index=False, sheet_name="Confeccao x Marca")
    df_faixa.to_excel(writer, index=False, sheet_name="Eficacia")
    df[["Marca", "Confecção", "Status", "Compra", "Cód Confec", "Confeccionado", "Qtd", "Saldo",
        "Dt Entrega", "Prioridade", "Eficacia"]].to_excel(writer, index=False, sheet_name="Pedidos")

c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "📥 Baixar CSV — concentração por marca",
        data=df_marca.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"dashboard_marcas_{date.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        width="stretch",
    )
with c2:
    st.download_button(
        "📊 Baixar Excel — agregados do dashboard",
        data=buffer.getvalue(),
        file_name=f"dashboard_pedidos_{date.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
