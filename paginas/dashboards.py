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
    normalizar_cod,
    para_texto,
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

    st.markdown("---")
    st.header("🚫 Exclusões")
    if "Cód Confec_norm" in df_pedidos.columns:
        codigos_todos = sorted(
            {c for c in df_pedidos["Cód Confec_norm"].tolist() if c}
        )
        codigos_ignorar = st.multiselect(
            "Ignorar Cód Confec",
            options=codigos_todos,
            default=[],
            help="Remove os códigos selecionados da visualização em todos os gráficos e tabelas.",
        )
    else:
        codigos_ignorar = []

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
if codigos_ignorar:
    df = df[~df["Cód Confec_norm"].isin(set(codigos_ignorar))]

if df.empty:
    st.warning("Nenhum pedido encontrado com os filtros selecionados.")
    st.stop()

# ==================== KPIs ====================

qtd_total = df["Qtd"].sum(min_count=1)
saldo_total = df["Saldo"].sum(min_count=1)
eficacia_global = (saldo_total / qtd_total) if qtd_total else np.nan
n_atrasados = int((df["Prioridade"] == "Atrasado").sum())

# Modern KPI cards in a grid
st.markdown("### 📈 Visão Geral")
kpi_cols = st.columns(6)
with kpi_cols[0]:
    with st.container(border=True):
        st.metric(
            label="🧾 Pedidos",
            value=f"{fmt_num(len(df))}",
            help="Total de linhas de pedido",
        )
with kpi_cols[1]:
    with st.container(border=True):
        st.metric(
            label="📦 Unidades Pedidas",
            value=fmt_num(qtd_total),
            help="Soma da quantidade solicitada",
        )
with kpi_cols[2]:
    with st.container(border=True):
        st.metric(
            label="⏳ Saldo em Aberto",
            value=fmt_num(saldo_total),
            help="Quantidade ainda não entregue",
        )
with kpi_cols[3]:
    with st.container(border=True):
        st.metric(
            label="🎯 Eficácia",
            value=fmt_pct(eficacia_global),
            help="Saldo ÷ Qtd (menor = mais entregue)",
        )
with kpi_cols[4]:
    with st.container(border=True):
        st.metric(
            label="🏷️ Marcas",
            value=f"{df['Marca'].nunique()}",
            help="Marcas distintas no filtro",
        )
with kpi_cols[5]:
    with st.container(border=True):
        st.metric(
            label="⚠️ Atrasados",
            value=f"{n_atrasados}",
            help="Pedidos com entrega vencida",
        )

st.markdown(
    f"<div class='db-aviso'>💡 <b>Eficácia</b> = Saldo ÷ Qtd — quanto do pedido continua em aberto. "
    "100% = nada foi entregue, 0% = pedido totalmente encerrado.</div>",
    unsafe_allow_html=True,
)

# ==================== 1. CONCENTRAÇÃO POR MARCA ====================

st.markdown("### 🏷️ Top Marcas por Volume")

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

chart_cols = st.columns([1.6, 1])
with chart_cols[0]:
    with st.container(border=True):
        fig = go.Figure()
        fig.add_bar(
            y=top_marcas["Marca"],
            x=top_marcas["Qtd"],
            name="Unidades Pedidas",
            orientation="h",
            marker=dict(
                color=top_marcas["Qtd"],
                colorscale=[[0, "rgba(99, 102, 241, 0.4)"], [1, "#6366f1"]],
                showscale=False,
            ),
            text=top_marcas["Qtd"].apply(lambda v: f"{fmt_num(v)}"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Unidades: %{x:,.0f}<br>Participação: %{customdata:.1%}<extra></extra>",
            customdata=top_marcas["% Pedido"],
        )
        fig.update_layout(
            template=template_plotly(),
            height=max(420, 32 * len(top_marcas) + 80),
            title=f"Ranking Top {len(top_marcas)} Marcas por Volume",
            xaxis_title="Unidades Pedidas",
            yaxis_title="",
            margin=dict(t=70, l=10, r=80, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

with chart_cols[1]:
    with st.container(border=True):
        fig = px.pie(
            df_marca.head(min(top_n, 10)),
            names="Marca",
            values="Qtd",
            color_discrete_sequence=cores_grafico(),
            hole=0.6,
            title="Distribuição Top 10 Marcas",
            template=template_plotly(),
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>Qtd: %{value:,.0f}<br>Participação: %{percent}<extra></extra>",
        )
        fig.update_layout(height=max(420, 32 * len(top_marcas) + 80), margin=dict(t=70, l=10, r=10, b=10))
        st.plotly_chart(fig, width="stretch")

with st.expander("📋 Ver tabela detalhada por marca", expanded=False):
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

st.markdown("### 🔢 Concentração por Código de Confecção")

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

with st.container(border=True):
    fig = go.Figure()
    fig.add_bar(
        x=top_cod["Cód Confec"],
        y=top_cod["Qtd"],
        name="Qtd",
        marker_color="#667eea",
        hovertemplate="Cód %{x}<br>Qtd: %{y}<extra></extra>",
    )
    fig.add_scatter(
        x=top_cod["Cód Confec"],
        y=top_cod["Acumulado %"] * 100,
        name="% acumulado",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color="#f44336", width=3),
        marker=dict(size=8),
        hovertemplate="Cód %{x}<br>Acumulado: %{y:.1f}%<extra></extra>",
    )
    fig.update_layout(
        template=template_plotly(),
        height=450,
        title=f"Análise de Pareto — Top {len(top_cod)} Códigos",
        xaxis_title="Cód Confec",
        yaxis_title="Unidades pedidas",
        yaxis2=dict(title="% acumulado", overlaying="y", side="right", range=[0, 105], showgrid=False),
        legend=dict(orientation="h", y=1.12),
        margin=dict(t=70, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

with st.expander("📋 Ver tabela detalhada por código de confecção", expanded=False):
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

# ==================== 3. EVOLUÇÃO E STATUS ====================

st.markdown("### 🧾 Evolução e Status dos Pedidos")

chart_cols2 = st.columns([1.4, 1])
with chart_cols2[0]:
    with st.container(border=True):
        if "Dt Emissao" in df.columns and df["Dt Emissao"].notna().any():
            df_mes = (
                df.dropna(subset=["Dt Emissao"])
                .groupby(df["Dt Emissao"].dt.to_period("M").dt.to_timestamp())
                .agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum"), Pedidos=("Compra", "count"))
                .reset_index()
                .rename(columns={"Dt Emissao": "Mês"})
            )
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df_mes["Mês"],
                    y=df_mes["Qtd"],
                    mode="lines+markers",
                    name="Qtd Pedida",
                    line=dict(color="#6366f1", width=3),
                    marker=dict(size=8),
                    fill="tozeroy",
                    fillcolor="rgba(99, 102, 241, 0.08)",
                    hovertemplate="<b>%{x|%m/%Y}</b><br>Qtd: %{y:,.0f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=df_mes["Mês"],
                    y=df_mes["Saldo"],
                    mode="lines+markers",
                    name="Saldo em Aberto",
                    line=dict(color="#f59e0b", width=3),
                    marker=dict(size=8),
                    hovertemplate="<b>%{x|%m/%Y}</b><br>Saldo: %{y:,.0f}<extra></extra>",
                )
            )
            fig.update_layout(
                template=template_plotly(),
                height=400,
                title="Evolução Mensal — Qtd Pedida x Saldo em Aberto",
                xaxis_title="Mês",
                yaxis_title="Unidades",
                legend=dict(orientation="h", y=1.12),
                margin=dict(t=70, l=10, r=10, b=10),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("O arquivo de Pedidos não possui a coluna `Dt Emissao`.")

with chart_cols2[1]:
    with st.container(border=True):
        df_status = (
            df.groupby("Status")
            .agg(Qtd=("Qtd", "sum"), Pedidos=("Compra", "count"))
            .reset_index()
            .sort_values("Qtd", ascending=False)
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=df_status["Status"],
                x=df_status["Qtd"],
                orientation="h",
                marker=dict(
                    color=df_status["Qtd"],
                    colorscale=[[0, "rgba(99, 102, 241, 0.4)"], [1, "#6366f1"]],
                    showscale=False,
                ),
                text=df_status.apply(lambda r: f"{fmt_num(r['Qtd'])} ({r['Pedidos']} ped.)", axis=1),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Qtd: %{x:,.0f}<br>Pedidos: %{customdata}<extra></extra>",
                customdata=df_status["Pedidos"],
            )
        )
        fig.update_layout(
            template=template_plotly(),
            height=400,
            title="Distribuição por Status",
            xaxis_title="Unidades",
            yaxis_title="",
            margin=dict(t=70, l=10, r=90, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

# Top Confecções
with st.container(border=True):
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
        title=f"Top {min(top_n, len(df_conf))} Confecções por Volume",
        template=template_plotly(),
    )
    fig.update_layout(height=450, coloraxis_showscale=False, margin=dict(t=60, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ==================== 4. ANÁLISE DE EFICÁCIA ====================

st.markdown("### 📈 Análise de Eficácia (Saldo ÷ Qtd)")

FAIXAS = [
    ("Sem saldo (0%)", 0.0, 0.0001),
    ("Quase encerrado (0-25%)", 0.0001, 0.25),
    ("Parcial (25-50%)", 0.25, 0.5),
    ("Maior parte aberta (50-75%)", 0.5, 0.75),
    ("Integralmente aberto (75-100%)", 0.75, 1.0001),
    ("Acima de 100%", 1.0001, np.inf),
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

with st.container(border=True):
    cores_faixa = ["#22c55e", "#84cc16", "#f59e0b", "#f97316", "#ef4444", "#dc2626", "#94a3b8"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_faixa["Faixa"],
            y=df_faixa["Pedidos"],
            name="Pedidos",
            marker=dict(color=cores_faixa[:len(df_faixa)]),
            text=df_faixa["Pedidos"].apply(lambda v: f"{fmt_num(v)}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Pedidos: %{y:,.0f}<br>Qtd: %{customdata[0]:,.0f}<br>Saldo: %{customdata[1]:,.0f}<extra></extra>",
            customdata=np.column_stack((df_faixa["Qtd"], df_faixa["Saldo"])),
        )
    )
    fig.update_layout(
        template=template_plotly(),
        height=420,
        title="Distribuição dos Pedidos por Faixa de Eficácia",
        xaxis_title="",
        yaxis_title="Nº de Pedidos",
        margin=dict(t=70, l=10, r=10, b=80),
        showlegend=False,
    )
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, width="stretch")

# ==================== 5. DETALHAMENTO POR CONFECÇÃO ====================

st.markdown("### 🏭 Detalhamento por Confecção")

st.caption(
    "Comparativo entre todas as confecções do filtro atual e detalhe da confecção selecionada."
)

with st.container(border=True):
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
        height=max(280, 48 * len(_conf_ord) + 110),
        barmode="stack",
        title="Volume por Confecção — Entregue × Saldo em Aberto",
        xaxis_title="Unidades",
        legend=dict(orientation="h", y=1.12),
        margin=dict(t=70, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

with st.expander("📋 Ver tabela comparativa por confecção", expanded=False):
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

st.markdown("#### 🔎 Drill-down por Confecção")

with st.container(border=True):
    conf_sel = st.selectbox(
        "Selecione a confecção para análise detalhada",
        options=df_conf["Confecção"].tolist(),
        index=0,
        help="Visualize KPIs, distribuição por marca, faixas e pedidos desta confecção.",
    )

    dfc = df[df["Confecção"] == conf_sel].copy()

    d_qtd = dfc["Qtd"].sum(min_count=1)
    d_saldo = dfc["Saldo"].sum(min_count=1)
    d_efic = (d_saldo / d_qtd) if d_qtd else np.nan
    d_atras = int((dfc["Prioridade"] == "Atrasado").sum())

    dkpi = st.columns(6)
    with dkpi[0]:
        st.metric("Pedidos", f"{fmt_num(len(dfc))}", help="Linhas de pedido")
    with dkpi[1]:
        st.metric("Unidades Pedidas", fmt_num(d_qtd), help="Soma de Qtd")
    with dkpi[2]:
        st.metric("Entregue", fmt_num(d_qtd - d_saldo), help="Qtd - Saldo")
    with dkpi[3]:
        st.metric("Saldo em Aberto", fmt_num(d_saldo), help="Soma de Saldo")
    with dkpi[4]:
        st.metric("Eficácia", fmt_pct(d_efic), help="Saldo ÷ Qtd")
    with dkpi[5]:
        st.metric("Atrasados", f"{d_atras}", help="Entrega vencida")

    dcols1 = st.columns(2)
    with dcols1[0]:
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
            title="Volume por Marca",
            xaxis_title="Unidades",
            legend=dict(orientation="h", y=1.12),
            margin=dict(t=60, l=10, r=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")

    with dcols1[1]:
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
            title="Pedidos por Faixa de Eficácia",
            template=template_plotly(),
        )
        fig.update_layout(
            height=360,
            coloraxis_showscale=False,
            margin=dict(t=60, l=10, r=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")

    dcols2 = st.columns(2)
    with dcols2[0]:
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
            para_texto(dfc_cod["Cód Confec"])
            + " · "
            + para_texto(dfc_cod["Confeccionado"]).str.slice(0, 26)
        )
        fig = px.bar(
            dfc_cod.sort_values("Saldo"),
            x="Saldo",
            y="Rótulo",
            orientation="h",
            color="Eficácia",
            color_continuous_scale=["#2e7d32", "#ff9800", "#c62828"],
            labels={"Saldo": "Saldo em aberto", "Rótulo": "", "Eficácia": "Eficácia"},
            title="Top 10 Códigos com Maior Saldo",
            template=template_plotly(),
        )
        fig.update_layout(
            height=360,
            coloraxis_showscale=False,
            margin=dict(t=60, l=10, r=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")

    with dcols2[1]:
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
                title="Evolução Mensal por Emissão",
                template=template_plotly(),
            )
            fig.update_layout(height=360, margin=dict(t=60, l=10, r=10, b=10))
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
                title="Pedidos por Prioridade",
                template=template_plotly(),
            )
            fig.update_layout(height=360, showlegend=False, margin=dict(t=60, l=10, r=10, b=10))
            st.plotly_chart(fig, width="stretch")

    with st.expander(f"📋 Listagem completa — {conf_sel}", expanded=False):
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

# ==================== 6. TECIDO SUGERIDO ====================

st.markdown("### 🧵 Tecido Sugerido")

tec_col = 'Tec Faz "x" Confec'
df_tecido = None

if df_estoque is not None:
    df_estoque_tecido = df_estoque.copy()
    df_estoque_tecido["Cód Confec_norm"] = df_estoque_tecido["Cód Confec"].map(normalizar_cod)
    for coluna_t in (tec_col, "Saldo 5", "Cons. Unitário"):
        if coluna_t not in df_estoque_tecido.columns:
            df_estoque_tecido[coluna_t] = np.nan
        df_estoque_tecido[coluna_t] = pd.to_numeric(
            df_estoque_tecido[coluna_t], errors="coerce"
        )
    if "Descrição" not in df_estoque_tecido.columns:
        df_estoque_tecido["Descrição"] = ""

    codigos_estoque = set(df_estoque_tecido["Cód Confec_norm"].dropna())
    codigos_pedidos_filtrados = set(df["Cód Confec_norm"].dropna())
    codigos_considerar = codigos_estoque.intersection(codigos_pedidos_filtrados)

    df_tecido_base = df_estoque_tecido[df_estoque_tecido["Cód Confec_norm"].isin(codigos_considerar)].copy()
    df_tecido_base = df_tecido_base[df_tecido_base["Saldo 5"] < 0].copy()

    if codigos_ignorar:
        df_tecido_base = df_tecido_base[
            ~df_tecido_base["Cód Confec_norm"].isin(set(codigos_ignorar))
        ]

    def calc_tecido(row):
        s5 = row.get("Saldo 5")
        if pd.isna(s5) or s5 >= 0:
            return 0.0
        tfx = row.get(tec_col)
        cons = row.get("Cons. Unitário")
        if pd.isna(tfx):
            tfx = 0
        calc = float(s5) + float(tfx)
        if calc >= 0:
            return 0.0
        tecido = (abs(calc) * 1.10) * (float(cons) if pd.notna(cons) else 0.0)
        if tecido < 0:
            tecido = 0.0
        return round(tecido, 3)

    if not df_tecido_base.empty:
        df_tecido_base["Calc (Saldo5 + Tec Faz x Confec)"] = df_tecido_base.apply(lambda r: float(r["Saldo 5"]) + float(r[tec_col]) if pd.notna(r.get(tec_col)) else float(r["Saldo 5"]), axis=1)
        df_tecido_base["Tecido Sugerido (m)"] = df_tecido_base.apply(calc_tecido, axis=1)
        df_tecido = df_tecido_base[df_tecido_base["Tecido Sugerido (m)"] > 0].copy()
    else:
        df_tecido = pd.DataFrame()
else:
    df_tecido = pd.DataFrame()

if df_tecido is None or df_tecido.empty:
    st.info("Não há itens com Saldo 5 negativo nos códigos filtrados para cálculo de tecido sugerido.")
else:
    tk1, tk2, tk3 = st.columns(3)
    with tk1:
        with st.container(border=True):
            st.metric("Itens com sugestão", f"{len(df_tecido)}", help="Itens com Saldo 5 < 0")
    with tk2:
        with st.container(border=True):
            st.metric("Total Tecido Sugerido (m)", f"{df_tecido['Tecido Sugerido (m)'].sum():,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with tk3:
        with st.container(border=True):
            st.metric("Códigos únicos", f"{df_tecido['Cód Confec_norm'].nunique()}")

    chart_cols_t = st.columns([1.6, 1])
    with chart_cols_t[0]:
        with st.container(border=True):
            df_tecido_g = df_tecido.copy()
            df_tecido_g["Label"] = (
                para_texto(df_tecido_g["Cód Confec"])
                + " - "
                + para_texto(df_tecido_g["Descrição"]).str.slice(0, 30)
            )
            df_tecido_g = df_tecido_g.sort_values("Tecido Sugerido (m)", ascending=True).tail(top_n)
            fig = go.Figure()
            fig.add_bar(
                y=df_tecido_g["Label"],
                x=df_tecido_g["Tecido Sugerido (m)"],
                orientation="h",
                marker=dict(color=df_tecido_g["Tecido Sugerido (m)"], colorscale=[[0, "rgba(99, 102, 241, 0.4)"], [1, "#6366f1"]], showscale=False),
                text=df_tecido_g["Tecido Sugerido (m)"].apply(lambda v: f"{v:,.3f} m".replace(",", "X").replace(".", ",").replace("X", ".")),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Tecido: %{x:.3f} m<extra></extra>",
            )
            fig.update_layout(
                template=template_plotly(),
                height=max(420, 32 * len(df_tecido_g) + 80),
                title=f"Top {len(df_tecido_g)} Itens - Tecido Sugerido",
                xaxis_title="Metros",
                yaxis_title="",
                margin=dict(t=70, l=10, r=90, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

    with chart_cols_t[1]:
        with st.container(border=True):
            st.markdown("**Critério aplicado**")
            st.caption(f"Se Saldo 5 < 0: ( (|Saldo 5 + {tec_col}|) * 1,10 ) * Cons. Unitário, quando (Saldo 5 + {tec_col}) < 0")

    with st.expander("📋 Ver tabela detalhada - Tecido Sugerido", expanded=False):
        cols_t = ["Cód Confec", "Descrição", "Saldo 5", tec_col, "Cons. Unitário", "Calc (Saldo5 + Tec Faz x Confec)", "Tecido Sugerido (m)"]
        cols_t = [c for c in cols_t if c in df_tecido.columns]
        st.dataframe(
            df_tecido[cols_t].sort_values("Tecido Sugerido (m)", ascending=False).style.format(
                {
                    "Saldo 5": "{:,.0f}",
                    tec_col: "{:,.0f}",
                    "Cons. Unitário": "{:,.4f}",
                    "Calc (Saldo5 + Tec Faz x Confec)": "{:,.0f}",
                    "Tecido Sugerido (m)": "{:,.3f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )

# ==================== EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar Dados")

with st.container(border=True):
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
        if df_tecido is not None and not df_tecido.empty:
            cols_t_exp = ["Cód Confec", "Descrição", "Saldo 5", tec_col, "Cons. Unitário", "Calc (Saldo5 + Tec Faz x Confec)", "Tecido Sugerido (m)"]
            cols_t_exp = [c for c in cols_t_exp if c in df_tecido.columns]
            df_tecido[cols_t_exp].to_excel(writer, index=False, sheet_name="Tecido Sugerido")

    exp_cols = st.columns(2)
    with exp_cols[0]:
        st.download_button(
            "📥 Baixar CSV — Concentração por Marca",
            data=df_marca.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"dashboard_marcas_{date.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            width="stretch",
        )
    with exp_cols[1]:
        st.download_button(
            "📊 Baixar Excel — Todos os Agregados",
            data=buffer.getvalue(),
            file_name=f"dashboard_pedidos_{date.today().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
