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

import html
import io
import math
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from nucleo import (
    aplicar_estilo_comum,
    cabecalho,
    card,
    cores_grafico,
    extrair_tamanho,
    fmt_num,
    fmt_pct,
    ordenar_tamanhos,
    para_texto,
    preparar_estoque,
    preparar_pedidos,
    sidebar_arquivos,
    template_plotly,
)


def _pdf_texto(valor):
    """Texto seguro para o PDF: remove emojis e escapa caracteres do ReportLab."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    texto = texto.encode("latin-1", "ignore").decode("latin-1").strip()
    return html.escape(texto)


def _pdf_numero(valor):
    """Número no padrão brasileiro para as células do PDF."""
    try:
        if pd.isna(valor):
            return "-"
        numero = float(valor)
    except (TypeError, ValueError):
        return _pdf_texto(valor) or "-"
    if numero == int(numero):
        return f"{int(numero):,}".replace(",", ".")
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(show_spinner=False, max_entries=8)
def gerar_pdf_compra_sugerida(df_pdf, data_referencia=None):
    """Gera a listagem de compra sugerida em PDF (A4 paisagem)."""
    data_referencia = data_referencia or date.today().strftime("%d/%m/%Y")
    colunas = [
        ("Marca", "Marca", 18, "texto"),
        ("Cód Confec", "Código", 17, "texto"),
        ("Descrição", "Descrição", None, "texto"),
        ("Tamanho", "Tamanho", 20, "texto"),
        ("Saldo 5", "Saldo 5", 14, "numero"),
        ('Tec Faz "x" Confec', "Teto", 14, "numero"),
        ("Compra Sugerida Bruta", "Bruta", 16, "numero"),
        ("Compra Sugerida", "Sugerida", 17, "numero"),
        ("Saldo 1", "Saldo 1", 12, "numero"),
        ("Saldo 2", "Saldo 2", 12, "numero"),
        ("Saldo 3", "Saldo 3", 12, "numero"),
        ("Demanda", "Demanda", 14, "numero"),
        ("Situação do item", "Situação", 20, "texto"),
    ]
    colunas = [coluna for coluna in colunas if coluna[0] in df_pdf.columns]

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title="Compra Sugerida - Análise de Estoque",
        author="Sistema de Confecção",
    )

    estilo_titulo = ParagraphStyle(
        "pdf_titulo",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_subtitulo = ParagraphStyle(
        "pdf_subtitulo",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )
    estilo_cabecalho = ParagraphStyle(
        "pdf_cabecalho",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_celula = ParagraphStyle(
        "pdf_celula",
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
    )

    total_sugerida = pd.to_numeric(
        df_pdf.get("Compra Sugerida"), errors="coerce"
    ).fillna(0).sum()
    total_bruta = pd.to_numeric(
        df_pdf.get("Compra Sugerida Bruta"), errors="coerce"
    ).fillna(0).sum()
    resumo = (
        f"{len(df_pdf)} item(ns) com sugestão · "
        f"Total sugerido: {_pdf_numero(total_sugerida)} un. · "
        f"Total bruto: {_pdf_numero(total_bruta)} un."
    )

    dados = [[Paragraph(titulo, estilo_cabecalho) for _, titulo, _, _ in colunas]]
    for _, linha_df in df_pdf.iterrows():
        linha = []
        for coluna, _, _, tipo in colunas:
            valor = linha_df.get(coluna)
            if tipo == "numero":
                linha.append(_pdf_numero(valor))
            else:
                linha.append(Paragraph(_pdf_texto(valor), estilo_celula))
        dados.append(linha)

    if len(df_pdf) == 0:
        vazio = [Paragraph("Nenhum item com compra sugerida nos filtros atuais.", estilo_celula)]
        vazio.extend([""] * (len(colunas) - 1))
        dados.append(vazio)

    largura_fixa = sum(largura for _, _, largura, _ in colunas if largura) * mm
    largura_descricao = max(45 * mm, documento.width - largura_fixa)
    larguras = [
        largura * mm if largura else largura_descricao
        for _, _, largura, _ in colunas
    ]

    estilo_tabela = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    for indice, (_, _, _, tipo) in enumerate(colunas):
        if tipo == "numero":
            estilo_tabela.add("ALIGN", (indice, 1), (indice, -1), "RIGHT")

    tabela = Table(dados, colWidths=larguras, repeatRows=1, splitByRow=1)
    tabela.setStyle(estilo_tabela)

    story = [
        Paragraph("Compra Sugerida", estilo_titulo),
        Paragraph(
            f"Análise de Estoque · Data de referência: {data_referencia}",
            estilo_subtitulo,
        ),
        Paragraph(resumo, estilo_subtitulo),
        Spacer(1, 4 * mm),
        tabela,
    ]

    def rodape(canvas, _documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(12 * mm, 8 * mm, "Sistema de Confecção - Análise de Estoque")
        canvas.drawRightString(
            landscape(A4)[0] - 12 * mm,
            8 * mm,
            f"Página {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    documento.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()

st.set_page_config(
    page_title="Análise de Estoque",
    page_icon="📦",
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
df_estoque["Tamanho"] = df_estoque["Descrição"].map(extrair_tamanho)
df_pedidos = preparar_pedidos(df_pedidos) if df_pedidos is not None else None

cabecalho(
    "📦 Análise de Estoque por item",
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
    tamanhos_opcoes = ordenar_tamanhos(df_estoque["Tamanho"])
    tamanhos_sel = st.multiselect(
        "Tamanho (da descrição)",
        options=tamanhos_opcoes,
        default=tamanhos_opcoes,
        help=(
            "Tamanho inferido da Descrição do item (ex.: 'CAMISETA BASIC P', "
            "'TAM: M', 'CALÇA JEANS 42', 'CORTINA 2,40X1,70'). Também reconhece "
            "faixas como 'De 1,40X1,90 até 1,60X2,00'. Itens sem tamanho "
            "reconhecido ficam em 'Sem tamanho'."
        ),
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
df = df[df["Tamanho"].isin(tamanhos_sel)]

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

# ==================== ANÁLISE DE COMPRA SUGERIDA ====================

tec_col = 'Tec Faz "x" Confec'
df[tec_col] = pd.to_numeric(df.get(tec_col), errors="coerce") if tec_col in df.columns else np.nan
df["Saldo 5"] = pd.to_numeric(df.get("Saldo 5"), errors="coerce")

def calcular_compra_sugerida(row):
    s5 = row.get("Saldo 5")
    if pd.isna(s5):
        return 0
    if s5 >= 0:
        return 0
    # Saldo 5 negativo: sugestão = |Saldo 5| * 1,1
    sug_bruta = abs(float(s5)) * 1.1
    # arredondar para cima como na Q.E?
    sug_bruta = math.ceil(sug_bruta)
    teto = row.get(tec_col)
    if pd.notna(teto) and float(teto) >= 0:
        teto_val = float(teto)
        if teto_val < sug_bruta:
            sug_bruta = teto_val
    if sug_bruta < 0:
        sug_bruta = 0
    return int(max(0, sug_bruta))

df["Compra Sugerida"] = df.apply(calcular_compra_sugerida, axis=1)
df["Compra Sugerida Bruta"] = np.where(
    df["Saldo 5"] < 0,
    np.ceil(np.abs(df["Saldo 5"]) * 1.1),
    0,
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
    para_texto(df_ord["Descrição"]).str.slice(0, 40)
    + " ("
    + para_texto(df_ord["Cód Confec"])
    + ")"
)

fig = px.bar(
    df_ord.sort_values("Saldo 3"),
    x="Saldo 1",
    y="Item",
    orientation="h",
    title=f"Top {len(df_ord)} itens — físico (Saldo 1), trânsito e confecção",
    labels={"Saldo 1": "Saldo 1 (físico)", "Item": ""},
    template=template_plotly(),
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
        color_discrete_sequence=cores_grafico(),
        title="Itens por situação de cobertura",
        template=template_plotly(),
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
        template=template_plotly(),
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
        template=template_plotly(),
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
        para_texto(df_def["Descrição"]).str.slice(0, 40)
        + " ("
        + para_texto(df_def["Cód Confec"])
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
        template=template_plotly(),
    )
    fig.update_layout(height=max(420, 26 * min(top_n, len(df_def))), coloraxis_showscale=False, margin=dict(t=55, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ==================== 4. ANÁLISE DE COMPRA SUGERIDA ====================

st.markdown("---")
st.markdown('<div class="db-secao">🛒 Análise de compra sugerida (Saldo 5)</div>', unsafe_allow_html=True)

st.caption(
    "Quando o Saldo 5 estiver negativo, a sugestão é |Saldo 5| × 1,1, arredondada para cima (ceil), "
    f'limitada pelo valor de "Tec Faz \"x\" Confec" (nunca maior que esse teto).'
)

tec_col = 'Tec Faz "x" Confec'
df_compra = df.copy()
df_compra["Compra Sugerida"] = df_compra.apply(calcular_compra_sugerida, axis=1)
df_compra["Compra Sugerida Bruta"] = np.where(
    df_compra["Saldo 5"] < 0,
    np.ceil(np.abs(df_compra["Saldo 5"]) * 1.1),
    0,
)

qtd_itens_sug = int((df_compra["Compra Sugerida"] > 0).sum())
total_sug = float(df_compra["Compra Sugerida"].sum())

c1k, c2k, c3k = st.columns(3)
with c1k:
    st.markdown(card("Itens com sugestão", f"{fmt_num(qtd_itens_sug)}", "Saldo 5 < 0"), unsafe_allow_html=True)
with c2k:
    st.markdown(card("Total sugerido", fmt_num(total_sug), "compra sugerida aplicada ao teto"), unsafe_allow_html=True)
with c3k:
    st.markdown(card('Teto "Tec Faz x Confec"', "aplicado quando menor que |S5|×1,1", "regra conforme solicitação"), unsafe_allow_html=True)

if qtd_itens_sug == 0:
    st.info("Não há itens com Saldo 5 negativo no filtro atual.")
else:
    df_sug = df_compra[df_compra["Compra Sugerida"] > 0].copy()
    df_sug = df_sug.sort_values("Compra Sugerida", ascending=False)
    df_sug["Item"] = (
        para_texto(df_sug["Descrição"]).str.slice(0, 40)
        + " ("
        + para_texto(df_sug["Cód Confec"])
        + ")"
    )

    fig = px.bar(
        df_sug.head(top_n).sort_values("Compra Sugerida"),
        x="Compra Sugerida",
        y="Item",
        orientation="h",
        color="Compra Sugerida",
        color_continuous_scale=["#fff3e0", "#ef6c00"],
        labels={"Compra Sugerida": "Compra sugerida", "Item": ""},
        title=f"Top {min(top_n, len(df_sug))} itens com maior compra sugerida",
        template=template_plotly(),
    )
    fig.update_layout(height=max(420, 26 * min(top_n, len(df_sug))), coloraxis_showscale=False, margin=dict(t=55, l=10, r=10, b=10))
    st.plotly_chart(fig, width="stretch")

    colunas_sug = [
        "Marca",
        "Cód Confec",
        "Descrição",
        "Tamanho",
        "Saldo 5",
        tec_col if tec_col in df_sug.columns else None,
        "Compra Sugerida Bruta",
        "Compra Sugerida",
        "Saldo 1",
        "Saldo 2",
        "Saldo 3",
        "Demanda",
        "Situação do item",
    ]
    colunas_sug = [c for c in colunas_sug if c is not None and c in df_sug.columns]
    tabela_sug = df_sug[colunas_sug].copy()

    coluna_config_sug = {
        "Marca": st.column_config.TextColumn("Marca", width="small"),
        "Cód Confec": st.column_config.TextColumn("Cód Confec", width="small"),
        "Descrição": st.column_config.TextColumn("Descrição", width="large"),
        "Tamanho": st.column_config.TextColumn("Tamanho", width="small"),
        "Saldo 5": st.column_config.NumberColumn("Saldo 5 (projetado)", format="%d"),
        "Compra Sugerida Bruta": st.column_config.NumberColumn("|Saldo 5| × 1,1 (ceil)", format="%d"),
        "Compra Sugerida": st.column_config.NumberColumn("Compra Sugerida", format="%d"),
        "Saldo 1": st.column_config.NumberColumn("Saldo 1", format="%d"),
        "Saldo 2": st.column_config.NumberColumn("Saldo 2", format="%d"),
        "Saldo 3": st.column_config.NumberColumn("Saldo 3", format="%d"),
        "Demanda": st.column_config.NumberColumn("Demanda", format="%d"),
        "Situação do item": st.column_config.TextColumn("Situação", width="medium"),
    }
    if tec_col in tabela_sug.columns:
        coluna_config_sug[tec_col] = st.column_config.NumberColumn('Tec Faz "x" Confec" (teto)', format="%d")

    st.dataframe(
        tabela_sug,
        width="stretch",
        hide_index=True,
        column_config=coluna_config_sug,
    )

    st.caption(
        "O PDF abaixo lista **todos** os itens com compra sugerida no filtro atual "
        "(não apenas o Top N do gráfico)."
    )
    st.download_button(
        "📄 Baixar PDF — listagem de compra sugerida",
        data=gerar_pdf_compra_sugerida(
            df_sug, date.today().strftime("%d/%m/%Y")
        ),
        file_name=f"compra_sugerida_{date.today().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf",
        width="stretch",
    )

# ==================== TABELA POR ITEM ====================

st.markdown("---")
st.markdown("### 📋 Análise por item")

colunas_tabela = [
    "Marca",
    "Cód Confec",
    "Descrição",
    "Tamanho",
    "Saldo 1",
    "Em Trânsito",
    "Saldo 2",
    "Em Confecção",
    "Saldo 3",
    "Saldo 5",
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
        "Tamanho": st.column_config.TextColumn("Tamanho", width="small"),
        "Saldo 1": st.column_config.NumberColumn("Saldo 1 (físico)", format="%d"),
        "Em Trânsito": st.column_config.NumberColumn("Em Trânsito", format="%d"),
        "Saldo 2": st.column_config.NumberColumn("Saldo 2", format="%d"),
        "Em Confecção": st.column_config.NumberColumn("Em Confecção", format="%d"),
        "Saldo 3": st.column_config.NumberColumn("Saldo 3", format="%d"),
        "Saldo 5": st.column_config.NumberColumn("Saldo 5 (projetado)", format="%d"),
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

# Garante as colunas de sugestão no export
df_export = df.copy()
df_export["Compra Sugerida"] = df_export.apply(calcular_compra_sugerida, axis=1)
df_export["Compra Sugerida Bruta"] = np.where(
    df_export["Saldo 5"] < 0,
    np.ceil(np.abs(df_export["Saldo 5"]) * 1.1),
    0,
)

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_export.to_excel(writer, index=False, sheet_name="Por Item")
    (
        df_export.groupby(["Marca", "Situação do item"])
        .agg(
            Itens=("Cód Confec", "count"),
            Saldo1=("Saldo 1", "sum"),
            Saldo2=("Saldo 2", "sum"),
            Saldo3=("Saldo 3", "sum"),
            Saldo5=("Saldo 5", "sum"),
            CompraSugerida=("Compra Sugerida", "sum"),
            Demanda=("Demanda", "sum"),
        )
        .reset_index()
        .to_excel(writer, index=False, sheet_name="Resumo")
    )
    df_export[df_export["Compra Sugerida"] > 0].to_excel(
        writer, index=False, sheet_name="Compra Sugerida"
    )

c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "📥 Baixar CSV — análise por item",
        data=df_export.to_csv(index=False, encoding="utf-8-sig"),
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
