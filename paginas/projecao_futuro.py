"""
Projeção Futuro
---------------
Planejamento de produção a partir da planilha **Projeção.xlsx**, cruzada com
os arquivos de Pedidos e Estoque já carregados no sistema.

Regras
------
* A data de necessidade de cada item é, em ordem de prioridade:
  ``Dt. Agendamento`` -> ``Dt Entrega`` -> ``Dt Pedido``.
* As chegadas de material são agrupadas em lotes semanais, respeitando um
  intervalo mínimo (padrão: 1 semana) entre uma chegada e a seguinte.
* Pedidos que já possuem confecção (cruzamento por ``Cód Confec`` com a
  planilha de Pedidos) são sinalizados e podem ser incluídos ou não no
  planejamento.
"""

import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from nucleo import (
    aplicar_estilo_comum,
    cabecalho,
    cores_grafico,
    fmt_data,
    fmt_num,
    load_excel,
    normalizar_cod,
    para_texto,
    sidebar_arquivos,
    template_plotly,
)

st.set_page_config(
    page_title="Projeção Futuro",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_comum()

df_pedidos_raw, df_estoque_raw = sidebar_arquivos()

# ==================== UPLOAD DA PROJEÇÃO ====================

CHAVES_PROJ = ("projecao_bytes", "projecao_nome", "projecao_sig")

with st.sidebar:
    st.markdown("---")
    st.header("📁 Projeção")
    nome_proj = st.session_state.get("projecao_nome")
    if nome_proj:
        st.markdown(
            f'<div class="db-file-ok">✅ <b>Projeção</b>'
            f'<span class="db-file-name">{nome_proj}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 Trocar projeção", key="btn_trocar_projecao"):
            for chave in CHAVES_PROJ:
                st.session_state.pop(chave, None)
            st.rerun()
    else:
        upload = st.file_uploader(
            "Arquivo **Projeção** (.xlsx)",
            type=["xlsx", "xls"],
            key="upload_projecao",
            help="Planilha com a demanda futura (Pedido, Cód Prod, Qtd *, Saldo Pedido, "
            "Dt. Agendamento, Dt Entrega, Operação Produtiva...).",
        )
        if upload is not None:
            st.session_state["projecao_bytes"] = upload.getvalue()
            st.session_state["projecao_nome"] = upload.name
            st.rerun()

dados_proj = st.session_state.get("projecao_bytes")

cabecalho(
    "📅 Projeção Futuro",
    "Planejamento de produção por lotes semanais, priorizando a data de "
    f"agendamento e garantindo intervalo mínimo entre chegadas de material — "
    f"referência: {date.today().strftime('%d/%m/%Y')}",
)

if not dados_proj:
    st.info(
        "👆 Envie a planilha **Projeção.xlsx** na barra lateral para gerar o planejamento. "
        "Os arquivos de **Pedidos** e **Estoque** já carregados são usados no cruzamento."
    )
    st.stop()

try:
    bruto = load_excel(dados_proj)
except Exception as erro:  # noqa: BLE001
    st.error(f"Não foi possível ler a planilha de Projeção: {erro}")
    st.stop()

if bruto is None or bruto.empty:
    st.warning("A planilha de Projeção está vazia.")
    st.stop()

# ==================== NORMALIZAÇÃO ====================


def localizar_coluna(df, *nomes):
    """Encontra o nome real de uma coluna, ignorando maiúsculas/espaços."""
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes:
        if nome in df.columns:
            return nome
        chave = str(nome).strip().lower()
        if chave in mapa:
            return mapa[chave]
    return None


def coluna_texto(df, *nomes, padrao=""):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series([padrao] * len(df), index=df.index, dtype="object")
    return para_texto(df[coluna]).str.strip().replace("", padrao)


def coluna_numero(df, *nomes):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[coluna], errors="coerce")


def coluna_data(df, *nomes):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    return pd.to_datetime(df[coluna], errors="coerce")


proj = pd.DataFrame(index=bruto.index)
proj["Pedido"] = coluna_texto(bruto, "Pedido", "Ped Cliente").map(normalizar_cod)
proj["Cód Confec"] = para_texto(coluna_texto(bruto, "Cód Prod", "Cod. Produto", "Cód Confec")).map(
    normalizar_cod
)
proj["Produto"] = coluna_texto(bruto, "Produto", "Descrição", padrao="Sem descrição")
proj["Cliente"] = coluna_texto(bruto, "Cliente", padrao="—")
proj["Marca"] = coluna_texto(bruto, "Marca", padrao="Sem Marca")
proj["Grupo"] = coluna_texto(bruto, "Grupo do Cliente", padrao="Sem Grupo")
proj["Coleção"] = coluna_texto(bruto, "Coleção", padrao="Sem Coleção")
proj["Operação"] = coluna_texto(bruto, "Operação Produtiva", "Ope. produtiva", padrao="Sem Operação")
proj["Status"] = coluna_texto(bruto, "Sts do Pedido", "Status", padrao="Sem Status")
proj["Status Entrega"] = coluna_texto(bruto, "Status da Entrega", padrao="—")
proj["Segmento"] = coluna_texto(bruto, "Segmento", padrao="")

# Remove linhas de total/resumo da planilha (sem Pedido ou sem Cód Prod)
proj = proj[(proj["Pedido"].str.strip() != "") & (proj["Cód Confec"].str.strip() != "")]
proj = proj.reset_index(drop=True)
proj["Qtd"] = coluna_numero(bruto, "Qtd *", "Qtd").fillna(0.0)
proj["Saldo Calc."] = coluna_numero(bruto, "Saldo Calc.").fillna(0.0)
proj["Em Trânsito"] = coluna_numero(bruto, "Em Trânsito").fillna(0.0)
# Saldo em aberto = ((Qtd* - Saldo Calc.) - Em Trânsito), limitado a 0
proj["Saldo"] = ((proj["Qtd"] - proj["Saldo Calc."]) - proj["Em Trânsito"]).clip(lower=0)
proj["Dt Agendamento"] = coluna_data(bruto, "Dt. Agendamento", "Dt Agendamento")
proj["Dt Entrega"] = coluna_data(bruto, "Dt Entrega", "Dt. Entrega")
proj["Dt Pedido"] = coluna_data(bruto, "Dt Pedido", "Dt. Pedido")

# Data de necessidade: agendamento -> entrega -> pedido
proj["Data Necessidade"] = (
    proj["Dt Agendamento"]
    .fillna(proj["Dt Entrega"])
    .fillna(proj["Dt Pedido"])
)
# Material pré-disposto no mínimo 5 dias antes da data de entrega/agendamento
proj["Data Necessidade"] = proj["Data Necessidade"] - pd.Timedelta(days=5)
proj["Origem da Data"] = np.select(
    [
        proj["Dt Agendamento"].notna(),
        proj["Dt Entrega"].notna(),
    ],
    ["Agendamento", "Entrega"],
    default="Pedido",
)

# ==================== CRUZAMENTO COM PEDIDOS (EM CONFECÇÃO) ====================

proj["Confecções"] = ""
proj["Em Confecção"] = False
proj["Qtd em Produção"] = 0.0
producao_por_codigo = pd.Series(dtype="float64")

if df_pedidos_raw is not None and not df_pedidos_raw.empty:
    ped = df_pedidos_raw.copy()
    col_cod_ped = localizar_coluna(ped, "Cód Confec", "Cod Confec")
    col_conf_ped = localizar_coluna(ped, "Confecção", "Confeccao")
    if col_cod_ped is not None and col_conf_ped is not None:
        codigos_ped = para_texto(ped[col_cod_ped]).map(normalizar_cod)
        nomes_conf = para_texto(ped[col_conf_ped]).str.strip()
        col_saldo_ped = localizar_coluna(ped, "Saldo")
        if col_saldo_ped is not None:
            saldo_ped = pd.to_numeric(ped[col_saldo_ped], errors="coerce").fillna(0.0)
        else:
            saldo_ped = pd.Series(0.0, index=ped.index)

        em_producao = nomes_conf.str.len() > 0
        em_producao &= ~nomes_conf.str.upper().str.startswith("SEM")

        if em_producao.any():
            tabela_conf = (
                pd.DataFrame(
                    {
                        "codigo": codigos_ped[em_producao],
                        "confecao": nomes_conf[em_producao],
                        "saldo": saldo_ped[em_producao],
                    }
                )
                .query("codigo != ''")
                .groupby("codigo", as_index=True)
                .agg(
                    Confecções=("confecao", lambda s: ", ".join(sorted(set(s)))),
                    Qtd=("saldo", "sum"),
                )
            )
            producao_por_codigo = tabela_conf["Qtd"]
            proj["Confecções"] = proj["Cód Confec"].map(tabela_conf["Confecções"]).fillna("")
            proj["Qtd em Produção"] = (
                proj["Cód Confec"].map(producao_por_codigo).fillna(0.0).astype(float)
            )
            proj["Em Confecção"] = proj["Confecções"].str.len() > 0

# ==================== FILTROS ====================


def opcoes(coluna):
    return sorted(valor for valor in proj[coluna].dropna().unique() if str(valor).strip())


with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros da Projeção")

    somente_abertos = st.checkbox(
        "Somente com necessidade de material (Saldo > 0)",
        value=True,
        help="Saldo = ((Qtd* - Saldo Calc.) - Em Trânsito). Exclui itens já cobertos.",
    )
    somente_com_data = st.checkbox(
        "Desconsiderar pedidos sem data de agendamento ou entrega",
        value=True,
        help="Remove itens que não possuem Dt. Agendamento nem Dt Entrega.",
    )
    qtd_min_item_pf = st.number_input(
        "Quantidade mínima por item (un.)",
        min_value=0, max_value=100000, value=100, step=10, key="pf_qtd_min",
        help="Itens com necessidade abaixo desse valor são ignorados no planejamento.",
    )
    descontar_producao = st.checkbox(
        "Descontar produção já em confecção",
        value=True,
        help="Abate do saldo em aberto a quantidade que já está em produção na planilha de "
        "Pedidos (cruzamento por Cód Confec). Os itens totalmente cobertos saem do plano.",
    )
    intervalo_semanas = st.number_input(
        "Intervalo mínimo entre chegadas (semanas)",
        min_value=1,
        max_value=8,
        value=1,
        step=1,
    )
    capacidade_entrega = st.number_input(
        "Capacidade por entrega (unidades)",
        min_value=1000,
        max_value=100000,
        value=23000,
        step=1000,
        help="Limite máximo de unidades por entrega.",
    )
    pct_cameba = st.number_input(
        "Limite CAMEBA por entrega (%)",
        min_value=1,
        max_value=100,
        value=25,
        step=1,
        help="Percentual da capacidade destinado ao segmento CAMEBA.",
    )

    inicio = st.date_input(
        "Início do planejamento",
        value=date.today(),
        help="Datas anteriores são reagendadas a partir desta data.",
    )

    filtros = {}
    for rotulo, coluna in (
        ("Status", "Status"),
        ("Marca", "Marca"),
        ("Operação Produtiva", "Operação"),
        ("Grupo do Cliente", "Grupo"),
        ("Coleção", "Coleção"),
    ):
        valores = opcoes(coluna)
        if 1 < len(valores) <= 200:
            filtros[coluna] = st.multiselect(rotulo, valores, default=valores, key=f"flt_{coluna}")

df = proj.copy()
if somente_abertos:
    df = df[df["Saldo"] > 0]
if somente_com_data:
    df = df[df["Dt Agendamento"].notna() | df["Dt Entrega"].notna()]
for coluna, selecionados in filtros.items():
    if selecionados:
        df = df[df[coluna].isin(selecionados)]

if df.empty:
    st.warning("Nenhum item encontrado com os filtros selecionados.")
    st.stop()

# ==================== NECESSIDADE LÍQUIDA ====================
# A produção já em andamento cobre primeiro os itens mais urgentes de cada código.

df = df.sort_values(
    ["Cód Confec", "Data Necessidade", "Pedido"], kind="stable"
).reset_index(drop=True)
df["Produção Disponível"] = (
    df["Cód Confec"].map(producao_por_codigo).fillna(0.0).astype(float)
)
acumulado_antes = df.groupby("Cód Confec")["Saldo"].cumsum() - df["Saldo"]
df["Coberto pela Produção"] = np.minimum(
    (df["Produção Disponível"] - acumulado_antes).clip(lower=0), df["Saldo"]
)
df["Necessidade"] = (df["Saldo"] - df["Coberto pela Produção"]).clip(lower=0)

if descontar_producao:
    df = df[df["Necessidade"] > 0].copy()
else:
    df["Necessidade"] = df["Saldo"]

if df.empty:
    st.info(
        "Toda a demanda filtrada já está coberta por pedidos em produção. "
        "Desmarque **Descontar produção já em confecção** para ver o plano bruto."
    )
    st.stop()

# Filtra itens com necessidade abaixo do mínimo por item
df = df[df["Necessidade"] >= float(qtd_min_item_pf)]
if df.empty:
    st.info("Nenhum item atinge a quantidade mínima por item configurada.")
    st.stop()

# ==================== ENTREGAS COM CAPACIDADE E INTERVALO MÍNIMO ====================

hoje = pd.Timestamp(inicio) if inicio else pd.Timestamp(date.today())
df["Data Necessidade"] = df["Data Necessidade"].fillna(hoje)
df["Data Base"] = df["Data Necessidade"].where(df["Data Necessidade"] >= hoje, hoje)
df["Semana Demanda"] = df["Data Base"].dt.normalize() - pd.to_timedelta(
    df["Data Base"].dt.weekday, unit="D"
)

df["_is_cameba"] = df["Segmento"].astype(str).str.strip().str.upper() == "CAMEBA"
df["_vol"] = pd.to_numeric(df["Necessidade"], errors="coerce").fillna(0.0)

capacidade_entrega = float(capacidade_entrega)
capacidade_cameba = capacidade_entrega * (float(pct_cameba) / 100.0)
intervalo = pd.Timedelta(weeks=int(intervalo_semanas))

# Empacotamento por semana: respeita capacidade total e limite CAMEBA
entregas = []  # cada: items, week, total, cameba
for semana in sorted(df["Semana Demanda"].dropna().unique()):
    itens_semana = df[df["Semana Demanda"] == semana].sort_values("_vol", ascending=False)
    for _, linha in itens_semana.iterrows():
        colocado = False
        for entrega in entregas:
            if entrega["week"] != semana:
                continue
            if (entrega["total"] + float(linha["_vol"]) <= capacidade_entrega and
                    (not bool(linha["_is_cameba"]) or
                     entrega["cameba"] + float(linha["_vol"]) <= capacidade_cameba)):
                entrega["items"].append(linha.name)
                entrega["total"] += float(linha["_vol"])
                if bool(linha["_is_cameba"]):
                    entrega["cameba"] += float(linha["_vol"])
                colocado = True
                break
        if not colocado:
            entregas.append({
                "items": [linha.name],
                "week": semana,
                "total": float(linha["_vol"]),
                "cameba": float(linha["_vol"]) if bool(linha["_is_cameba"]) else 0.0,
            })

# Agendamento com intervalo mínimo entre entregas, sem ultrapassar a data de necessidade
prev = None
entregas_atrasadas = 0
for entrega in entregas:
    candidato = pd.Timestamp(entrega["week"])
    if prev is not None and candidato < prev + intervalo:
        candidato = prev + intervalo
    # Prazo: data de necessidade mais cedo entre os itens da entrega
    prazo = pd.Timestamp(df.loc[entrega["items"], "Data Necessidade"].min())
    entrega["prazo"] = prazo
    if candidato > prazo:
        candidato = prazo
        entrega["atrasada"] = True
        entregas_atrasadas += 1
    else:
        entrega["atrasada"] = False
    entrega["agendada"] = candidato
    prev = candidato

mapa_item_entrega = {}
for idx_entrega, entrega in enumerate(entregas):
    for item in entrega["items"]:
        mapa_item_entrega[item] = idx_entrega

df["EntregaID"] = df.index.map(mapa_item_entrega)
df["Chegada Material"] = df["EntregaID"].map(lambda i: entregas[i]["agendada"])
df["Entrega Atrasada"] = df["EntregaID"].map(lambda i: entregas[i]["atrasada"])

df = df.sort_values(["Chegada Material", "Data Base", "Pedido"], kind="stable").reset_index(drop=True)

lotes_ordenados = sorted(df["Chegada Material"].dropna().unique())
rotulo_lote = {
    chegada: f"Entrega {indice + 1:02d} · {pd.Timestamp(chegada).strftime('%d/%m/%Y')}"
    for indice, chegada in enumerate(lotes_ordenados)
}
df["Lote"] = df["Chegada Material"].map(rotulo_lote).fillna("Sem data")

# Mantém flag CAMEBA para exibição/exportação
df["CAMEBA"] = df["Segmento"].astype(str).str.strip().str.upper() == "CAMEBA"
df["Nec CAMEBA"] = df["Necessidade"].where(df["CAMEBA"], 0.0)

# Limpa colunas auxiliares
df = df.drop(columns=["_is_cameba", "_vol"], errors="ignore")

# ==================== KPIs ====================

st.markdown("### 📈 Visão Geral do Planejamento")

qtd_total = float(df["Qtd"].sum())
saldo_total = float(df["Saldo"].sum())
coberto_total = float(df["Coberto pela Produção"].sum())
necessidade_total = float(df["Necessidade"].sum())
em_conf_itens = int(df["Em Confecção"].sum())
n_lotes = len(lotes_ordenados)
primeira = pd.Timestamp(lotes_ordenados[0]) if lotes_ordenados else pd.NaT
ultima = pd.Timestamp(lotes_ordenados[-1]) if lotes_ordenados else pd.NaT

colunas_kpi = st.columns(6)
with colunas_kpi[0]:
    with st.container(border=True):
        st.metric("🧾 Itens", fmt_num(len(df)), help="Linhas da projeção após os filtros")
with colunas_kpi[1]:
    with st.container(border=True):
        st.metric("📦 Qtd Pedida", fmt_num(qtd_total))
with colunas_kpi[2]:
    with st.container(border=True):
        st.metric("💰 Saldo em Aberto", fmt_num(saldo_total), help="((Qtd* - Saldo Calc.) - Em Trânsito)")
with colunas_kpi[3]:
    with st.container(border=True):
        st.metric(
            "🏭 Já em Produção",
            fmt_num(coberto_total),
            help="Quantidade coberta por pedidos que já possuem confecção na planilha de Pedidos",
        )
with colunas_kpi[4]:
    with st.container(border=True):
        st.metric(
            "🎯 Necessidade Líquida",
            fmt_num(necessidade_total),
            help="Saldo em aberto menos a produção já em andamento",
        )
with colunas_kpi[5]:
    with st.container(border=True):
        st.metric(
            "📅 Lotes",
            fmt_num(n_lotes),
            help=f"Intervalo mínimo de {intervalo_semanas} semana(s) entre chegadas",
        )

if pd.notna(primeira) and pd.notna(ultima):
    st.caption(
        f"🗓️ Horizonte planejado: **{primeira.strftime('%d/%m/%Y')}** → "
        f"**{ultima.strftime('%d/%m/%Y')}** · {em_conf_itens} itens já possuem confecção definida."
    )
    if entregas_atrasadas:
        st.warning(
            f"⚠️ {entregas_atrasadas} entrega(s) não couberam no intervalo e foram "
            "antecipadas para não ultrapassar a data de necessidade."
        )

# ==================== GRÁFICOS ====================

st.markdown("### 📊 Entregas Planejadas")

if lotes_ordenados:
    resumo = (
        df.groupby("Lote", sort=False)
        .agg(
            Itens=("Pedido", "count"),
            Qtd=("Qtd", "sum"),
            Saldo=("Saldo", "sum"),
            Necessidade=("Necessidade", "sum"),
            CAMEBA=("Nec CAMEBA", "sum"),
            EmConf=("Em Confecção", "sum"),
            Chegada=("Chegada Material", "first"),
        )
        .reset_index()
        .sort_values("Chegada")
    )

    with st.container(border=True):
        figura = go.Figure()
        figura.add_bar(
            x=resumo["Lote"],
            y=resumo["Necessidade"],
            name="Necessidade líquida",
            marker_color="#6366f1",
            hovertemplate="<b>%{x}</b><br>Necessidade: %{y:,.0f}<extra></extra>",
        )
        figura.add_bar(
            x=resumo["Lote"],
            y=resumo["Saldo"],
            name="Saldo em aberto",
            marker_color="#8b5cf6",
            hovertemplate="<b>%{x}</b><br>Saldo: %{y:,.0f}<extra></extra>",
        )
        figura.update_layout(
            template=template_plotly(),
            barmode="group",
            height=400,
            title="Necessidade por entrega",
            xaxis_title="",
            yaxis_title="Unidades",
            legend=dict(orientation="h", y=1.12),
            margin=dict(t=70, l=10, r=10, b=10),
        )
        st.plotly_chart(figura, width="stretch")

    with st.expander("📊 Gráficos detalhados", expanded=False):
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                por_operacao = (
                    df.groupby("Operação")
                    .agg(Necessidade=("Necessidade", "sum"))
                    .sort_values("Necessidade", ascending=False)
                    .reset_index()
                )
                if len(por_operacao) > 7:
                    resto = por_operacao.iloc[7:]["Necessidade"].sum()
                    por_operacao = pd.concat(
                        [
                            por_operacao.iloc[:7],
                            pd.DataFrame([{"Operação": "Outros", "Necessidade": resto}]),
                        ],
                        ignore_index=True,
                    )
                pizza = go.Figure(
                    go.Pie(
                        labels=por_operacao["Operação"],
                        values=por_operacao["Necessidade"],
                        hole=0.55,
                        marker=dict(colors=cores_grafico()),
                        textinfo="percent",
                    )
                )
                pizza.update_layout(
                    template=template_plotly(),
                    height=360,
                    title="Necessidade por operação",
                    showlegend=True,
                    legend=dict(orientation="v", font=dict(size=10)),
                    margin=dict(t=60, l=10, r=10, b=10),
                )
                st.plotly_chart(pizza, width="stretch")
        with g2:
            with st.container(border=True):
                top_ops = df["Operação"].value_counts().head(6).index.tolist()
                composicao = df.copy()
                composicao["Operação (agrupada)"] = np.where(
                    composicao["Operação"].isin(top_ops), composicao["Operação"], "Outras"
                )
                tabela_comp = (
                    composicao.pivot_table(
                        index="Lote",
                        columns="Operação (agrupada)",
                        values="Necessidade",
                        aggfunc="sum",
                        fill_value=0,
                    )
                    .reindex(resumo["Lote"])
                    .reset_index()
                )
                ordem_ops = [c for c in tabela_comp.columns if c != "Lote"]
                figura_comp = go.Figure()
                for indice, operacao in enumerate(ordem_ops):
                    figura_comp.add_bar(
                        x=tabela_comp["Lote"],
                        y=tabela_comp[operacao],
                        name=str(operacao),
                        marker_color=cores_grafico()[indice % len(cores_grafico())],
                    )
                figura_comp.update_layout(
                    template=template_plotly(),
                    barmode="stack",
                    height=360,
                    title="Composição por operação",
                    xaxis_title="",
                    yaxis_title="Unidades",
                    legend=dict(orientation="h", y=-0.25, font=dict(size=9)),
                    margin=dict(t=60, l=10, r=10, b=10),
                )
                st.plotly_chart(figura_comp, width="stretch")

    st.markdown("### 🗓️ Planejamento por Lote")
    with st.container(border=True):
        tabela_resumo = resumo.copy()
        tabela_resumo["Chegada"] = tabela_resumo["Chegada"].map(fmt_data)
        st.dataframe(
            tabela_resumo.rename(
                columns={
                    "Lote": "Lote",
                    "Chegada": "Chegada do material",
                    "Itens": "Itens",
                    "Qtd": "Qtd pedida",
                    "Saldo": "Saldo em aberto",
                    "Necessidade": "Necessidade líquida",
                    "CAMEBA": "CAMEBA (un.)",
                    "EmConf": "Itens já em confecção",
                }
            ),
            width="stretch",
            hide_index=True,
        )
else:
    st.info("Não há datas suficientes para montar os lotes de chegada de material.")

# ==================== DETALHAMENTO ====================

st.markdown("### 📋 Detalhamento do Planejamento")

colunas_detalhe = [
    "Lote",
    "Chegada Material",
    "Pedido",
    "Cód Confec",
    "Produto",
    "Cliente",
    "Marca",
    "Operação",
    "Qtd",
    "Saldo Calc.",
    "Em Trânsito",
    "Saldo",
    "Coberto pela Produção",
    "Necessidade",
    "Entrega Atrasada",
    "CAMEBA",
    "Data Necessidade",
    "Origem da Data",
    "Em Confecção",
    "Confecções",
]
colunas_detalhe = [c for c in colunas_detalhe if c in df.columns]

lotes_disponiveis = df["Lote"].unique().tolist()
selecao_lotes = st.multiselect(
    "Filtrar por lote",
    lotes_disponiveis,
    default=lotes_disponiveis,
    key="filtro_lotes",
)
detalhe = df[df["Lote"].isin(selecao_lotes)] if selecao_lotes else df

with st.container(border=True):
    st.dataframe(
        detalhe[colunas_detalhe]
        .rename(
            columns={
                "Chegada Material": "Chegada material",
                "Cód Confec": "Cód Confec",
                "Data Necessidade": "Data necessidade",
                "Origem da Data": "Origem",
                "Em Confecção": "Em confecção",
            }
        )
        .assign(
            **{
                "Chegada material": lambda d: d["Chegada material"].map(fmt_data),
                "Data necessidade": lambda d: d["Data necessidade"].map(fmt_data),
                "Qtd": lambda d: d["Qtd"].map(fmt_num),
                "Saldo Calc.": lambda d: d["Saldo Calc."].map(fmt_num),
                "Em Trânsito": lambda d: d["Em Trânsito"].map(fmt_num),
                "Saldo": lambda d: d["Saldo"].map(fmt_num),
                "Coberto pela Produção": lambda d: d["Coberto pela Produção"].map(fmt_num),
                "Necessidade": lambda d: d["Necessidade"].map(fmt_num),
            }
        ),
        width="stretch",
        hide_index=True,
        height=420,
    )

with st.expander("ℹ️ Como o planejamento é calculado", expanded=False):
    st.markdown(
        f"""
1. **Data de necessidade** de cada item: `Dt. Agendamento` → se vazia, `Dt Entrega` → se vazia, `Dt Pedido`.
2. O material é **pré-disposto 5 dias antes** dessa data.
3. O **saldo em aberto** é calculado por `((Qtd* - Saldo Calc.) - Em Trânsito)`.
4. A **necessidade líquida** desconta, por código, o saldo dos pedidos que já possuem
   confecção na planilha de Pedidos (os itens mais urgentes são cobertos primeiro).
5. Os itens são agrupados na semana da data de necessidade.
6. Cada **entrega** respeita **{int(capacidade_entrega):,} unidades** no total e no máximo
   **{int(capacidade_cameba):,} unidades** ({int(pct_cameba)}%) para o segmento **CAMEBA**.
7. As entregas são agendadas para **não ultrapassar a data de necessidade**
   (antecipadas quando necessário).
8. As entregas são espaçadas pelo intervalo mínimo configurado.
"""
    )

# ==================== EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar")


def montar_excel():
    buffer = io.BytesIO()
    demanda = df[
        [
            "Pedido",
            "Cód Confec",
            "Produto",
            "Cliente",
            "Marca",
            "Operação",
            "Qtd",
            "Saldo Calc.",
            "Em Trânsito",
            "Saldo",
            "Coberto pela Produção",
            "Necessidade",
            "CAMEBA",
            "Dt Agendamento",
            "Dt Entrega",
            "Dt Pedido",
            "Data Necessidade",
            "Origem da Data",
            "Lote",
            "Chegada Material",
            "Em Confecção",
            "Confecções",
        ]
    ].copy()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        demanda.to_excel(writer, index=False, sheet_name="Demanda")
        if lotes_ordenados:
            resumo_export = resumo.copy()
            resumo_export["Chegada"] = resumo_export["Chegada"].dt.strftime("%d/%m/%Y")
            resumo_export.to_excel(writer, index=False, sheet_name="Resumo por Lote")
        if em_conf_itens:
            df[df["Em Confecção"]][
                ["Pedido", "Cód Confec", "Produto", "Confecções", "Qtd", "Saldo"]
            ].to_excel(writer, index=False, sheet_name="Em Confecção")
    return buffer.getvalue()


colunas_export = st.columns(2)
with colunas_export[0]:
    st.download_button(
        "📥 Baixar CSV — Planejamento",
        data=detalhe[
            ["Lote", "Chegada Material", "Pedido", "Cód Confec", "Produto", "Qtd", "Saldo Calc.", "Em Trânsito", "Saldo", "Necessidade"]
        ].to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig"),
        file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        width="stretch",
    )
with colunas_export[1]:
    st.download_button(
        "📊 Baixar Excel — Projeção completa",
        data=montar_excel(),
        file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
