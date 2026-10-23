"""
All for One — Projeção Consolidada
-----------------------------------
Une em uma única página todas as funções do sistema (Kanban, Dashboards,
Análise de Estoque e Projeção Futuro) para a projeção mais assertiva possível.

Cruza, por código de confecção:
  • Demanda (Pedidos + Projeção)
  • Estoque (Saldo 1..5, tecido, consumo unitário)
  • Produção em andamento (Pedidos em confecção)
  • Necessidade líquida, tecido sugerido e compra sugerida
  • Planejamento de entregas com capacidade e intervalo mínimo
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
    preparar_estoque,
    preparar_pedidos,
    sidebar_arquivos,
    template_plotly,
)

st.set_page_config(
    page_title="All for One",
    page_icon="🎯",
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
        if st.button("🔄 Trocar projeção", key="btn_trocar_proj_all"):
            for chave in CHAVES_PROJ:
                st.session_state.pop(chave, None)
            st.rerun()
    else:
        upload = st.file_uploader(
            "Arquivo **Projeção** (.xlsx)",
            type=["xlsx", "xls"],
            key="upload_projecao_all",
            help="Demanda futura (Pedido, Cód Prod, Qtd *, Saldo Calc., Datas, Segmento...).",
        )
        if upload is not None:
            st.session_state["projecao_bytes"] = upload.getvalue()
            st.session_state["projecao_nome"] = upload.name
            st.rerun()

dados_proj = st.session_state.get("projecao_bytes")

cabecalho(
    "🎯 All for One — Projeção Consolidada",
    "Visão unificada de Pedidos, Estoque e Projeção para o planejamento mais assertivo possível — "
    f"referência: {date.today().strftime('%d/%m/%Y')}",
)

# ==================== FILTROS GLOBAIS ====================

with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros")
    intervalo_semanas = st.number_input(
        "Intervalo mínimo entre entregas (semanas)",
        min_value=1, max_value=8, value=1, step=1, key="all_intervalo",
    )
    capacidade_entrega = st.number_input(
        "Capacidade por entrega (un.)",
        min_value=1000, max_value=100000, value=23000, step=1000, key="all_cap",
    )
    pct_cameba = st.number_input(
        "Limite CAMEBA por entrega (%)",
        min_value=1, max_value=100, value=25, step=1, key="all_pct",
    )
    qtd_min_item = st.number_input(
        "Quantidade mínima por item (un.)",
        min_value=0, max_value=100000, value=100, step=10, key="all_qtd_min",
        help="Itens com necessidade abaixo desse valor são ignorados no planejamento.",
    )
    inicio = st.date_input(
        "Início do planejamento",
        value=date.today(), key="all_inicio",
        help="Datas anteriores são reagendadas a partir desta data.",
    )
    somente_com_data = st.checkbox(
        "Desconsiderar pedidos sem data de agendamento ou entrega",
        value=True, key="all_com_data",
    )
    desconsiderar_atrasados_all = st.checkbox(
        "Desconsiderar atrasados",
        value=False, key="all_desc_atrasados",
        help="Remove itens cuja data de necessidade já passou.",
    )
    st.markdown("**Filtro de data de necessidade**")
    data_nec_de_all = st.date_input(
        "De", value=None, key="all_data_nec_de",
        help="Data de necessidade mínima (deixe vazio para não filtrar).",
    )
    data_nec_ate_all = st.date_input(
        "Até", value=None, key="all_data_nec_ate",
        help="Data de necessidade máxima (deixe vazio para não filtrar).",
    )
    descontar_producao = st.checkbox(
        "Descontar produção já em confecção",
        value=True, key="all_desc_prod",
        help="Abate do saldo a quantidade já em produção na planilha de Pedidos.",
    )

# ==================== LEITURA E NORMALIZAÇÃO ====================


def localizar_coluna(df, *nomes):
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


# ---- Pedidos ----
df_pedidos = preparar_pedidos(df_pedidos_raw) if df_pedidos_raw is not None else None

# ---- Estoque ----
df_estoque = preparar_estoque(df_estoque_raw) if df_estoque_raw is not None else None

# ---- Projeção ----
df_proj = None
if dados_proj:
    try:
        bruto = load_excel(dados_proj)
    except Exception as erro:  # noqa: BLE001
        st.error(f"Não foi possível ler a planilha de Projeção: {erro}")
        bruto = None
    if bruto is not None and not bruto.empty:
        proj = pd.DataFrame(index=bruto.index)
        proj["Pedido"] = coluna_texto(bruto, "Pedido", "Ped Cliente").map(normalizar_cod)
        proj["Cód Confec"] = para_texto(coluna_texto(bruto, "Cód Prod", "Cod. Produto", "Cód Confec")).map(normalizar_cod)
        proj["Produto"] = coluna_texto(bruto, "Produto", "Descrição", padrao="Sem descrição")
        proj["Cliente"] = coluna_texto(bruto, "Cliente", padrao="—")
        proj["Marca"] = coluna_texto(bruto, "Marca", padrao="Sem Marca")
        proj["Grupo"] = coluna_texto(bruto, "Grupo do Cliente", padrao="Sem Grupo")
        proj["Coleção"] = coluna_texto(bruto, "Coleção", padrao="Sem Coleção")
        proj["Operação"] = coluna_texto(bruto, "Operação Produtiva", "Ope. produtiva", padrao="Sem Operação")
        proj["Status"] = coluna_texto(bruto, "Sts do Pedido", "Status", padrao="Sem Status")
        proj["Segmento"] = coluna_texto(bruto, "Segmento", padrao="")
        proj["Qtd"] = coluna_numero(bruto, "Qtd *", "Qtd").fillna(0.0)
        proj["Saldo Calc."] = coluna_numero(bruto, "Saldo Calc.").fillna(0.0)
        proj["Em Trânsito"] = coluna_numero(bruto, "Em Trânsito").fillna(0.0)
        proj["Saldo"] = ((proj["Qtd"] - proj["Saldo Calc."]) - proj["Em Trânsito"]).clip(lower=0)
        proj["Dt Agendamento"] = coluna_data(bruto, "Dt. Agendamento", "Dt Agendamento")
        proj["Dt Entrega"] = coluna_data(bruto, "Dt Entrega", "Dt. Entrega")
        proj["Dt Pedido"] = coluna_data(bruto, "Dt Pedido", "Dt. Pedido")
        proj["Data Necessidade"] = (
            proj["Dt Agendamento"].fillna(proj["Dt Entrega"]).fillna(proj["Dt Pedido"])
        )
        proj["Origem da Data"] = np.select(
            [proj["Dt Agendamento"].notna(), proj["Dt Entrega"].notna()],
            ["Agendamento", "Entrega"], default="Pedido",
        )
        proj = proj[(proj["Pedido"].str.strip() != "") & (proj["Cód Confec"].str.strip() != "")]
        proj = proj.reset_index(drop=True)
        df_proj = proj

if df_pedidos is None and df_proj is None:
    st.info(
        "👆 Envie ao menos o arquivo de **Pedidos** ou **Projeção** na barra lateral para montar a projeção consolidada."
    )
    st.stop()

# ==================== CRUZAMENTO POR CÓDIGO ====================

# Demanda por código: Pedidos (Saldo) + Projeção (Saldo)
demanda_pedidos = {}
producao_pedidos = {}
confec_pedidos = {}
if df_pedidos is not None:
    for _, row in df_pedidos.iterrows():
        cod = row.get("Cód Confec_norm", "")
        if not cod:
            continue
        demanda_pedidos[cod] = demanda_pedidos.get(cod, 0.0) + float(row.get("Saldo", 0) or 0)
        conf = str(row.get("Confecção", "") or "").strip()
        if conf and not conf.upper().startswith("SEM"):
            producao_pedidos[cod] = producao_pedidos.get(cod, 0.0) + float(row.get("Saldo", 0) or 0)
            confec_pedidos.setdefault(cod, set()).add(conf)

# Estoque por código
estoque_por_codigo = {}
if df_estoque is not None:
    for _, row in df_estoque.iterrows():
        cod = row.get("Cód Confec_norm", "")
        if not cod:
            continue
        estoque_por_codigo[cod] = {
            "Saldo 1": float(row.get("Saldo 1", 0) or 0) if pd.notna(row.get("Saldo 1")) else 0.0,
            "Saldo 2": float(row.get("Saldo 2", 0) or 0) if pd.notna(row.get("Saldo 2")) else 0.0,
            "Saldo 3": float(row.get("Saldo 3", 0) or 0) if pd.notna(row.get("Saldo 3")) else 0.0,
            "Saldo 4": float(row.get("Saldo 4", 0) or 0) if pd.notna(row.get("Saldo 4")) else 0.0,
            "Saldo 5": float(row.get("Saldo 5", 0) or 0) if pd.notna(row.get("Saldo 5")) else 0.0,
            "Tec Faz x Confec": float(row.get('Tec Faz "x" Confec', 0) or 0) if pd.notna(row.get('Tec Faz "x" Confec')) else 0.0,
            "Cons. Unitário": float(row.get("Cons. Unitário", 0) or 0) if pd.notna(row.get("Cons. Unitário")) else 0.0,
            "Marca": str(row.get("Marca", "Sem Marca") or "Sem Marca"),
            "Descrição": str(row.get("Descrição", "") or ""),
        }

# Demanda da Projeção por código
demanda_proj_por_codigo = {}
if df_proj is not None:
    for _, row in df_proj.iterrows():
        cod = row.get("Cód Confec", "")
        if not cod:
            continue
        demanda_proj_por_codigo[cod] = demanda_proj_por_codigo.get(cod, 0.0) + float(row.get("Saldo", 0) or 0)

# ==================== BASE CONSOLIDADA ====================

codigos_todos = sorted(set(demanda_pedidos) | set(demanda_proj_por_codigo) | set(estoque_por_codigo))

linhas = []
for cod in codigos_todos:
    est = estoque_por_codigo.get(cod, {})
    dem_ped = demanda_pedidos.get(cod, 0.0)
    dem_proj = demanda_proj_por_codigo.get(cod, 0.0)
    prod = producao_pedidos.get(cod, 0.0)
    confecs = ", ".join(sorted(confec_pedidos.get(cod, set())))
    saldo2 = est.get("Saldo 2", 0.0)
    saldo5 = est.get("Saldo 5", 0.0)
    tec_faz = est.get("Tec Faz x Confec", 0.0)
    cons = est.get("Cons. Unitário", 0.0)
    # Necessidade líquida (demanda total - produção em andamento)
    dem_total = dem_ped + dem_proj
    nec_liq = max(0.0, dem_total - prod)
    # Tecido sugerido (se Saldo 5 < 0)
    tecido_sug = 0.0
    if saldo5 < 0:
        calc = saldo5 + tec_faz
        if calc < 0:
            tecido_sug = (abs(calc) * 1.10) * (cons if cons else 0.0)
    # Compra sugerida (se Saldo 5 < 0)
    compra_sug = 0.0
    if saldo5 < 0:
        compra_sug = min(abs(saldo5) * 1.10, tec_faz) if tec_faz else abs(saldo5) * 1.10
        compra_sug = __import__("math").ceil(compra_sug)
    linhas.append({
        "Cód Confec": cod,
        "Descrição": est.get("Descrição", ""),
        "Marca": est.get("Marca", "Sem Marca"),
        "Demanda Pedidos": dem_ped,
        "Demanda Projeção": dem_proj,
        "Demanda Total": dem_total,
        "Em Produção": prod,
        "Confecções": confecs,
        "Saldo 2 (est+trânsito)": saldo2,
        "Saldo 5": saldo5,
        "Tec Faz x Confec": tec_faz,
        "Cons. Unitário": cons,
        "Necessidade Líquida": nec_liq,
        "Tecido Sugerido (m)": round(tecido_sug, 3),
        "Compra Sugerida": compra_sug,
    })

df_all = pd.DataFrame(linhas)

# ==================== KPIs ====================

st.markdown("### 📈 Visão Consolidada")

dem_total_geral = float(df_all["Demanda Total"].sum())
prod_total = float(df_all["Em Produção"].sum())
nec_total = float(df_all["Necessidade Líquida"].sum())
tecido_total = float(df_all["Tecido Sugerido (m)"].sum())
compra_total = float(df_all["Compra Sugerida"].sum())
saldo2_total = float(df_all["Saldo 2 (est+trânsito)"].sum())
saldo5_neg = int((df_all["Saldo 5"] < 0).sum())
n_codigos = len(df_all)

k = st.columns(4)
with k[0]:
    with st.container(border=True):
        st.metric("🧾 Códigos", fmt_num(n_codigos))
with k[1]:
    with st.container(border=True):
        st.metric("📦 Demanda Total", fmt_num(dem_total_geral))
with k[2]:
    with st.container(border=True):
        st.metric("🏭 Em Produção", fmt_num(prod_total))
with k[3]:
    with st.container(border=True):
        st.metric("🎯 Necessidade Líquida", fmt_num(nec_total))
k2 = st.columns(3)
with k2[0]:
    with st.container(border=True):
        st.metric("🧵 Tecido Sugerido (m)", f"{tecido_total:,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
with k2[1]:
    with st.container(border=True):
        st.metric("🛒 Compra Sugerida", fmt_num(compra_total))
with k2[2]:
    with st.container(border=True):
        st.metric("📦 Saldo 2 (est+trânsito)", fmt_num(saldo2_total))

st.caption(
    f"📊 {saldo5_neg} código(s) com Saldo 5 negativo (requerem reposição de estoque)."
)

# ==================== TABELA CONSOLIDADA ====================

st.markdown("### 📋 Tabela Consolidada por Código")

with st.container(border=True):
    st.dataframe(
        df_all.sort_values("Necessidade Líquida", ascending=False).style.format(
            {
                "Demanda Pedidos": "{:,.0f}",
                "Demanda Projeção": "{:,.0f}",
                "Demanda Total": "{:,.0f}",
                "Em Produção": "{:,.0f}",
                "Saldo 2 (est+trânsito)": "{:,.0f}",
                "Saldo 5": "{:,.0f}",
                "Tec Faz x Confec": "{:,.0f}",
                "Cons. Unitário": "{:,.4f}",
                "Necessidade Líquida": "{:,.0f}",
                "Tecido Sugerido (m)": "{:,.3f}",
                "Compra Sugerida": "{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=460,
    )

# ==================== PLANEJAMENTO DE ENTREGAS ====================

st.markdown("### 📅 Planejamento de Entregas (Consolidado)")

# Base para planejamento: Projeção (se disponível) senão Pedidos
if df_proj is not None:
    df_plan_base = df_proj.copy()
    df_plan_base["Data Necessidade"] = df_plan_base["Data Necessidade"] - pd.Timedelta(days=5)
    df_plan_base["Necessidade"] = df_plan_base["Saldo"]
else:
    # Deriva da demanda dos Pedidos (sem datas → usa hoje)
    linhas_p = []
    for cod, dem in demanda_pedidos.items():
        linhas_p.append({
            "Pedido": cod,
            "Cód Confec": cod,
            "Produto": estoque_por_codigo.get(cod, {}).get("Descrição", ""),
            "Qtd": dem,
            "Saldo": dem,
            "Necessidade": max(0.0, dem - producao_pedidos.get(cod, 0.0)),
            "Dt Agendamento": pd.NaT,
            "Dt Entrega": pd.NaT,
            "Dt Pedido": pd.NaT,
            "Data Necessidade": pd.Timestamp(date.today()),
            "Segmento": "",
            "Operação": "",
        })
    df_plan_base = pd.DataFrame(linhas_p)

if df_plan_base is not None and not df_plan_base.empty:
    hoje = pd.Timestamp(inicio) if inicio else pd.Timestamp(date.today())
    df_plan_base["Data Necessidade"] = df_plan_base["Data Necessidade"].fillna(hoje)
    df_plan_base["Data Base"] = df_plan_base["Data Necessidade"].where(df_plan_base["Data Necessidade"] >= hoje, hoje)
    df_plan_base["Semana Demanda"] = df_plan_base["Data Base"].dt.normalize() - pd.to_timedelta(
        df_plan_base["Data Base"].dt.weekday, unit="D"
    )
    if somente_com_data and "Dt Agendamento" in df_plan_base.columns:
        df_plan_base = df_plan_base[
            df_plan_base["Dt Agendamento"].notna() | df_plan_base["Dt Entrega"].notna()
        ]
    if desconsiderar_atrasados_all:
        hoje_ref = pd.Timestamp(inicio) if inicio else pd.Timestamp(date.today())
        df_plan_base = df_plan_base[df_plan_base["Data Necessidade"] >= hoje_ref]
    if data_nec_de_all is not None:
        df_plan_base = df_plan_base[df_plan_base["Data Necessidade"] >= pd.Timestamp(data_nec_de_all)]
    if data_nec_ate_all is not None:
        df_plan_base = df_plan_base[df_plan_base["Data Necessidade"] <= pd.Timestamp(data_nec_ate_all)]
    # Filtra itens com necessidade abaixo do mínimo por item
    df_plan_base = df_plan_base[df_plan_base["Necessidade"] >= float(qtd_min_item)]
    if descontar_producao and "Necessidade" not in df_plan_base.columns:
        df_plan_base["Necessidade"] = df_plan_base["Saldo"]
    if "Necessidade" not in df_plan_base.columns:
        df_plan_base["Necessidade"] = df_plan_base["Saldo"]

    df_plan_base["_is_cameba"] = df_plan_base.get("Segmento", pd.Series("", index=df_plan_base.index)).astype(str).str.strip().str.upper() == "CAMEBA"
    df_plan_base["_vol"] = pd.to_numeric(df_plan_base["Necessidade"], errors="coerce").fillna(0.0)

    capacidade_entrega_f = float(capacidade_entrega)
    capacidade_cameba_f = capacidade_entrega_f * (float(pct_cameba) / 100.0)
    intervalo = pd.Timedelta(weeks=int(intervalo_semanas))

    entregas = []
    for semana in sorted(df_plan_base["Semana Demanda"].dropna().unique()):
        itens_semana = df_plan_base[df_plan_base["Semana Demanda"] == semana].sort_values("_vol", ascending=False)
        for _, linha in itens_semana.iterrows():
            colocado = False
            for entrega in entregas:
                if entrega["week"] != semana:
                    continue
                if (entrega["total"] + float(linha["_vol"]) <= capacidade_entrega_f and
                        (not bool(linha["_is_cameba"]) or
                         entrega["cameba"] + float(linha["_vol"]) <= capacidade_cameba_f)):
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

    prev = None
    entregas_atrasadas = 0
    for entrega in entregas:
        candidato = pd.Timestamp(entrega["week"])
        if prev is not None and candidato < prev + intervalo:
            candidato = prev + intervalo
        prazo = pd.Timestamp(df_plan_base.loc[entrega["items"], "Data Necessidade"].min())
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

    df_plan_base["EntregaID"] = df_plan_base.index.map(mapa_item_entrega)
    df_plan_base["Chegada Material"] = df_plan_base["EntregaID"].map(lambda i: entregas[i]["agendada"])
    df_plan_base["Entrega Atrasada"] = df_plan_base["EntregaID"].map(lambda i: entregas[i]["atrasada"])

    df_plan_base = df_plan_base.sort_values(["Chegada Material", "Data Base", "Pedido"], kind="stable").reset_index(drop=True)

    lotes_ordenados = sorted(df_plan_base["Chegada Material"].dropna().unique())
    rotulo_lote = {
        chegada: f"Entrega {indice + 1:02d} · {pd.Timestamp(chegada).strftime('%d/%m/%Y')}"
        for indice, chegada in enumerate(lotes_ordenados)
    }
    df_plan_base["Lote"] = df_plan_base["Chegada Material"].map(rotulo_lote).fillna("Sem data")

    # KPIs do planejamento
    n_entregas = len(lotes_ordenados)
    primeira = pd.Timestamp(lotes_ordenados[0]) if lotes_ordenados else pd.NaT
    ultima = pd.Timestamp(lotes_ordenados[-1]) if lotes_ordenados else pd.NaT
    nec_plan = float(df_plan_base["Necessidade"].sum())

    pk = st.columns(4)
    with pk[0]:
        with st.container(border=True):
            st.metric("📅 Entregas", fmt_num(n_entregas))
    with pk[1]:
        with st.container(border=True):
            st.metric("🎯 Necessidade Planejada", fmt_num(nec_plan))
    with pk[2]:
        with st.container(border=True):
            periodo = f"{primeira.strftime('%d/%m/%y')} → {ultima.strftime('%d/%m/%y')}" if pd.notna(primeira) and pd.notna(ultima) else "—"
            st.metric("🗓️ Horizonte", periodo)
    with pk[3]:
        with st.container(border=True):
            st.metric("⚠️ Atrasadas", fmt_num(entregas_atrasadas))

    if entregas_atrasadas:
        st.warning(f"⚠️ {entregas_atrasadas} entrega(s) antecipadas para não ultrapassar a data de necessidade.")

    # Resumo por entrega
    resumo_plan = (
        df_plan_base.groupby("Lote", sort=False)
        .agg(
            Itens=("Pedido", "count"),
            Qtd=("Qtd", "sum") if "Qtd" in df_plan_base.columns else ("Necessidade", "count"),
            Necessidade=("Necessidade", "sum"),
            CAMEBA=("Nec CAMEBA" if "Nec CAMEBA" in df_plan_base.columns else "Necessidade", "sum") if False else ("Necessidade", "count"),
            Chegada=("Chegada Material", "first"),
        )
        .reset_index()
        .sort_values("Chegada")
    )
    # Simplify: recompute CAMEBA properly
    df_plan_base["Nec CAMEBA"] = df_plan_base["Necessidade"].where(df_plan_base["_is_cameba"], 0.0)
    resumo_plan = (
        df_plan_base.groupby("Lote", sort=False)
        .agg(
            Itens=("Pedido", "count"),
            Necessidade=("Necessidade", "sum"),
            CAMEBA=("Nec CAMEBA", "sum"),
            Chegada=("Chegada Material", "first"),
        )
        .reset_index()
        .sort_values("Chegada")
    )

    with st.container(border=True):
        st.dataframe(
            resumo_plan.rename(columns={
                "Lote": "Lote",
                "Chegada": "Chegada do material",
                "Itens": "Itens",
                "Necessidade": "Necessidade",
                "CAMEBA": "CAMEBA (un.)",
            }).assign(**{"Chegada do material": lambda d: d["Chegada do material"].map(fmt_data)}),
            width="stretch",
            hide_index=True,
        )

    df_plan_base = df_plan_base.drop(columns=["_is_cameba", "_vol"], errors="ignore")

# ==================== TECIDO SUGERIDO ====================

st.markdown("### 🧵 Tecido Sugerido")

tecido_df = df_all[df_all["Tecido Sugerido (m)"] > 0].copy()
if tecido_df.empty:
    st.info("Não há itens com sugestão de tecido (Saldo 5 < 0).")
else:
    t1, t2, t3 = st.columns(3)
    with t1:
        with st.container(border=True):
            st.metric("Itens com sugestão", fmt_num(len(tecido_df)))
    with t2:
        with st.container(border=True):
            st.metric("Total Tecido Sugerido (m)", f"{tecido_df['Tecido Sugerido (m)'].sum():,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with t3:
        with st.container(border=True):
            st.metric("Códigos únicos", fmt_num(tecido_df["Cód Confec"].nunique()))
    with st.container(border=True):
        st.dataframe(
            tecido_df[["Cód Confec", "Descrição", "Marca", "Saldo 5", "Tec Faz x Confec", "Cons. Unitário", "Tecido Sugerido (m)"]]
            .sort_values("Tecido Sugerido (m)", ascending=False)
            .style.format({
                "Saldo 5": "{:,.0f}",
                "Tec Faz x Confec": "{:,.0f}",
                "Cons. Unitário": "{:,.4f}",
                "Tecido Sugerido (m)": "{:,.3f}",
            }),
            width="stretch",
            hide_index=True,
            height=320,
        )

# ==================== COMPRA SUGERIDA ====================

st.markdown("### 🛒 Compra Sugerida (Reposição de Estoque)")

compra_df = df_all[df_all["Compra Sugerida"] > 0].copy()
if compra_df.empty:
    st.info("Não há itens com compra sugerida (Saldo 5 < 0).")
else:
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.metric("Itens com compra sugerida", fmt_num(len(compra_df)))
    with c2:
        with st.container(border=True):
            st.metric("Total Compra Sugerida", fmt_num(compra_df["Compra Sugerida"].sum()))
    with st.container(border=True):
        st.dataframe(
            compra_df[["Cód Confec", "Descrição", "Marca", "Saldo 5", "Tec Faz x Confec", "Compra Sugerida"]]
            .sort_values("Compra Sugerida", ascending=False)
            .style.format({
                "Saldo 5": "{:,.0f}",
                "Tec Faz x Confec": "{:,.0f}",
                "Compra Sugerida": "{:,.0f}",
            }),
            width="stretch",
            hide_index=True,
            height=320,
        )

# ==================== EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_all.to_excel(writer, index=False, sheet_name="Consolidado")
    if df_proj is not None:
        df_proj.to_excel(writer, index=False, sheet_name="Projeção")
    if not tecido_df.empty:
        tecido_df.to_excel(writer, index=False, sheet_name="Tecido Sugerido")
    if not compra_df.empty:
        compra_df.to_excel(writer, index=False, sheet_name="Compra Sugerida")
    if "df_plan_base" in locals() and df_plan_base is not None and not df_plan_base.empty:
        df_plan_base.to_excel(writer, index=False, sheet_name="Planejamento")

c1e, c2e = st.columns(2)
with c1e:
    st.download_button(
        "📥 Baixar CSV — Consolidado",
        data=df_all.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig"),
        file_name=f"all_for_one_{date.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        width="stretch",
    )
with c2e:
    st.download_button(
        "📊 Baixar Excel — Completo",
        data=buffer.getvalue(),
        file_name=f"all_for_one_{date.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
