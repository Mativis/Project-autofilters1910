"""
Projeção Futuro
---------------
Planejamento de produção a partir da planilha **Projeção.xlsx**, cruzada com
os arquivos de Pedidos e Estoque já carregados no sistema.
"""

import io
import math
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
    page_title="Projeção Futuro",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_comum()

df_pedidos_raw, df_estoque_raw = sidebar_arquivos()

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
        if st.button("🔄 Trocar projeção", key="btn_trocar_proj_pf3"):
            for chave in CHAVES_PROJ:
                st.session_state.pop(chave, None)
            st.rerun()
    else:
        upload = st.file_uploader(
            "Arquivo **Projeção** (.xlsx)",
            type=["xlsx", "xls"],
            key="upload_projecao_pf3",
            help="Planilha com a demanda futura.",
        )
        if upload is not None:
            st.session_state["projecao_bytes"] = upload.getvalue()
            st.session_state["projecao_nome"] = upload.name
            st.rerun()

dados_proj = st.session_state.get("projecao_bytes")
df_proj = None

cabecalho(
    "📅 Projeção Futuro",
    "Planejamento de produção por entregas — "
    f"referência: {date.today().strftime('%d/%m/%Y')}",
)

if not dados_proj:
    st.info("👆 Envie a planilha **Projeção.xlsx** na barra lateral.")
    st.stop()

# ==================== NORMALIZAÇÃO ====================


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


try:
    bruto = load_excel(dados_proj)
except Exception as erro:  # noqa: BLE001
    st.error(f"Não foi possível ler a planilha de Projeção: {erro}")
    st.stop()

if bruto is None or bruto.empty:
    st.warning("A planilha de Projeção está vazia.")
    st.stop()

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
proj["Status Entrega"] = coluna_texto(bruto, "Status da Entrega", padrao="—")
proj["Segmento"] = coluna_texto(bruto, "Segmento", padrao="")
proj["Qtd"] = coluna_numero(bruto, "Qtd *", "Qtd").fillna(0.0)
proj["Saldo Calc."] = coluna_numero(bruto, "Saldo Calc.").fillna(0.0)
proj["Em Trânsito"] = coluna_numero(bruto, "Em Trânsito").fillna(0.0)
proj["Saldo"] = ((proj["Qtd"] - proj["Saldo Calc."]) - proj["Em Trânsito"]).clip(lower=0)
proj["Dt Agendamento"] = coluna_data(bruto, "Dt. Agendamento", "Dt Agendamento")
proj["Dt Entrega"] = coluna_data(bruto, "Dt Entrega", "Dt. Entrega")
proj["Dt Pedido"] = coluna_data(bruto, "Dt Pedido", "Dt. Pedido")
proj["Data Necessidade"] = (proj["Dt Agendamento"].fillna(proj["Dt Entrega"]).fillna(proj["Dt Pedido"])) - pd.Timedelta(days=5)
proj["Origem da Data"] = np.select([proj["Dt Agendamento"].notna(), proj["Dt Entrega"].notna()], ["Agendamento", "Entrega"], default="Pedido")

estoque_lookup = {}
if df_estoque_raw is not None:
    est_prep = preparar_estoque(df_estoque_raw)
    for _, row in est_prep.iterrows():
        cod = row.get("Cód Confec_norm", "")
        if cod:
            estoque_lookup[cod] = {"Saldo 5": row.get("Saldo 5"), "Tec Faz x Confec": row.get('Tec Faz "x" Confec'), "Cons. Unitário": row.get("Cons. Unitário")}
proj["Saldo 5"] = proj["Cód Confec"].map(lambda c: estoque_lookup.get(c, {}).get("Saldo 5"))
proj["Tec Faz x Confec"] = proj["Cód Confec"].map(lambda c: estoque_lookup.get(c, {}).get("Tec Faz x Confec"))
proj["Cons. Unitário"] = proj["Cód Confec"].map(lambda c: estoque_lookup.get(c, {}).get("Cons. Unitário"))

proj = proj[(proj["Pedido"].str.strip() != "") & (proj["Cód Confec"].str.strip() != "")]
proj = proj.reset_index(drop=True)
df_proj = proj

# ==================== CRUZAMENTO COM PEDIDOS ====================

proj["Confecções"] = ""
proj["Em Confecção"] = False
proj["Qtd em Produção"] = 0.0
producao_por_codigo = pd.Series(dtype="float64")

df_pedidos = preparar_pedidos(df_pedidos_raw) if df_pedidos_raw is not None else None

if df_pedidos is not None and not df_pedidos.empty:
    ped = df_pedidos.copy()
    col_cod_ped = localizar_coluna(ped, "Cód Confec", "Cod Confec")
    col_conf_ped = localizar_coluna(ped, "Confecção", "Confeccao")
    if col_cod_ped is not None and col_conf_ped is not None:
        codigos_ped = para_texto(ped[col_cod_ped]).map(normalizar_cod)
        nomes_conf = para_texto(ped[col_conf_ped]).str.strip()
        col_saldo_ped = localizar_coluna(ped, "Saldo")
        saldo_ped = pd.to_numeric(ped[col_saldo_ped], errors="coerce").fillna(0.0) if col_saldo_ped else pd.Series(0.0, index=ped.index)
        em_producao = (nomes_conf.str.len() > 0) & (~nomes_conf.str.upper().str.startswith("SEM"))
        if em_producao.any():
            tabela_conf = pd.DataFrame({"codigo": codigos_ped[em_producao], "confecao": nomes_conf[em_producao], "saldo": saldo_ped[em_producao]}).query("codigo != ''").groupby("codigo").agg(Confecções=("confecao", lambda s: ", ".join(sorted(set(s)))), Qtd=("saldo", "sum"))
            producao_por_codigo = tabela_conf["Qtd"]
            proj["Confecções"] = proj["Cód Confec"].map(tabela_conf["Confecções"]).fillna("")
            proj["Qtd em Produção"] = proj["Cód Confec"].map(producao_por_codigo).fillna(0.0).astype(float)
            proj["Em Confecção"] = proj["Confecções"].str.len() > 0

df_proj = proj

if df_pedidos is None and df_proj is None:
    st.info("👆 Envie ao menos o arquivo de **Pedidos** ou **Projeção**.")
    st.stop()

# ==================== FILTROS ====================


def opcoes(coluna):
    return sorted(v for v in proj[coluna].dropna().unique() if str(v).strip())


with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros da Projeção")
    somente_abertos = st.checkbox("Somente com necessidade de material (Saldo > 0)", value=True, key="pf_abertos", help="Saldo = ((Qtd* - Saldo Calc.) - Em Trânsito).")
    somente_com_data = st.checkbox("Desconsiderar pedidos sem data de agendamento ou entrega", value=True, key="pf_com_data")
    desconsiderar_atrasados = st.checkbox("Desconsiderar atrasados", value=False, key="pf_desc_atrasados")
    qtd_min_item_pf = st.number_input("Quantidade mínima por item (un.)", min_value=0, max_value=100000, value=100, step=10, key="pf_qtd_min", help="Itens com necessidade total (somada por Cód Confec) abaixo desse valor são exibidos separadamente.")
    semanas_distribuir = st.number_input("Semanas para distribuir a demanda", min_value=1, max_value=52, value=4, step=1, key="pf_semanas_dist", help="A demanda de cada item é dividida igualmente por esse número de semanas. Cada semana vira uma entrega.")
    descontar_producao = st.checkbox("Descontar produção já em confecção", value=True, key="pf_desc_prod")
    desconsiderar_sem_tecido = st.checkbox("Desconsiderar itens sem tecido disponível", value=False, key="pf_desc_tecido")
    intervalo_semanas = st.number_input("Intervalo mínimo entre chegadas (semanas)", min_value=1, max_value=8, value=1, step=1, key="pf_intervalo")
    capacidade_entrega = st.number_input("Capacidade por entrega (unidades)", min_value=1000, max_value=100000, value=23000, step=1000, key="pf_cap")
    pct_cameba = st.number_input("Limite CAMEBA por entrega (%)", min_value=1, max_value=100, value=25, step=1, key="pf_pct")
    inicio = st.date_input("Início do planejamento", value=date.today(), key="pf_inicio")
    busca_cliente = st.text_input("Buscar cliente", value="", key="pf_busca")
    st.markdown("**Filtro de data de necessidade**")
    data_nec_de = st.date_input("De", value=None, key="pf_nec_de")
    data_nec_ate = st.date_input("Até", value=None, key="pf_nec_ate")
    filtros = {}
    for rotulo, coluna in (("Status", "Status"), ("Marca", "Marca"), ("Operação Produtiva", "Operação"), ("Grupo do Cliente", "Grupo"), ("Coleção", "Coleção")):
        valores = opcoes(coluna)
        if 1 < len(valores) <= 200:
            filtros[coluna] = st.multiselect(rotulo, valores, default=valores, key=f"pf_flt_{coluna}")

# ==================== PREPARAÇÃO DO DF ====================

df = proj.copy()
if somente_abertos:
    df = df[df["Saldo"] > 0]
if somente_com_data:
    df = df[df["Dt Agendamento"].notna() | df["Dt Entrega"].notna()]
if desconsiderar_atrasados:
    hoje_ref = pd.Timestamp(inicio) if inicio else pd.Timestamp(date.today())
    df = df[df["Data Necessidade"] >= hoje_ref]
if data_nec_de is not None:
    df = df[df["Data Necessidade"] >= pd.Timestamp(data_nec_de)]
if data_nec_ate is not None:
    df = df[df["Data Necessidade"] <= pd.Timestamp(data_nec_ate)]
for coluna, selecionados in filtros.items():
    if selecionados:
        df = df[df[coluna].isin(selecionados)]
if busca_cliente.strip():
    df = df[df["Cliente"].str.contains(busca_cliente.strip(), case=False, na=False)]
if desconsiderar_sem_tecido:
    def _tem_tecido(row):
        s5 = row.get("Saldo 5")
        cons = row.get("Cons. Unitário")
        nec = row.get("Necessidade", row.get("Saldo", 0))
        if pd.isna(s5):
            return False
        if pd.isna(cons) or cons == 0:
            return True
        return float(s5) >= float(nec) * float(cons)
    df = df[df.apply(_tem_tecido, axis=1)]

if df.empty:
    st.warning("Nenhum item encontrado com os filtros selecionados.")
    st.stop()

# ==================== NECESSIDADE LÍQUIDA ====================

df = df.sort_values(["Cód Confec", "Data Necessidade", "Pedido"], kind="stable").reset_index(drop=True)
df["Produção Disponível"] = df["Cód Confec"].map(producao_por_codigo).fillna(0.0).astype(float)
acumulado_antes = df.groupby("Cód Confec")["Saldo"].cumsum() - df["Saldo"]
df["Coberto pela Produção"] = np.minimum((df["Produção Disponível"] - acumulado_antes).clip(lower=0), df["Saldo"])
df["Necessidade"] = (df["Saldo"] - df["Coberto pela Produção"]).clip(lower=0)

if descontar_producao:
    df = df[df["Necessidade"] > 0].copy()
else:
    df["Necessidade"] = df["Saldo"]

if df.empty:
    st.info("Toda a demanda filtrada já está coberta por pedidos em produção.")
    st.stop()

# ==================== SEPARA ITENS PEQUENOS (< min) ====================

totais_por_item = df.groupby("Cód Confec")["Necessidade"].sum()
limite_min = qtd_min_item_pf if qtd_min_item_pf else 100
itens_pequenos_cod = set(totais_por_item[totais_por_item < float(limite_min)].index)
df_pequenos = df[df["Cód Confec"].isin(itens_pequenos_cod)].copy()
df = df[~df["Cód Confec"].isin(itens_pequenos_cod)].copy()

if df.empty and df_pequenos.empty:
    st.warning("Nenhum item encontrado com os filtros selecionados.")
    st.stop()

lotes_ordenados = []
resumo = None
entregas_atrasadas = 0

# ==================== PLANEJAMENTO POR SEMANAS ====================

if not df.empty:
    hoje_ref = pd.Timestamp(inicio) if inicio else pd.Timestamp(date.today())
    df["Data Necessidade"] = df["Data Necessidade"].fillna(hoje_ref)
    df["Data Base"] = df["Data Necessidade"].where(df["Data Necessidade"] >= hoje_ref, hoje_ref)
    df["Semana Demanda"] = df["Data Base"].dt.normalize() - pd.to_timedelta(df["Data Base"].dt.weekday, unit="D")
    df["_is_cameba"] = df["Segmento"].astype(str).str.strip().str.upper() == "CAMEBA"

    capacidade_entrega = float(capacidade_entrega)
    capacidade_cameba = capacidade_entrega * (float(pct_cameba) / 100.0)
    intervalo = pd.Timedelta(weeks=int(intervalo_semanas))
    N_SEMANAS = max(1, int(semanas_distribuir))

    # Cada item é dividido em N_SEMANAS partes iguais
    chunks = []
    for cod, grupo in df.groupby("Cód Confec"):
        total = float(grupo["Necessidade"].sum())
        num_chunks = min(N_SEMANAS, max(1, int(total)))
        if num_chunks < 1:
            num_chunks = 1
        base = int(total) // num_chunks
        resto = int(total) % num_chunks
        sizes = [base + (1 if i < resto else 0) for i in range(num_chunks)]
        semana = grupo["Semana Demanda"].iloc[0]
        for ci in range(num_chunks):
            # Pedidos apenas no primeiro chunk (referência); demais são continuação
            orders = grupo.copy() if ci == 0 else pd.DataFrame(columns=grupo.columns)
            chunks.append({
                "cod": cod,
                "produto": str(grupo["Produto"].iloc[0]),
                "is_cameba": bool(grupo["CAMEBA"].iloc[0]) if "CAMEBA" in grupo.columns else False,
                "qty": float(sizes[ci]),
                "chunk_idx": ci + 1,
                "total_chunks": num_chunks,
                "orders": orders,
                "week": semana,
            })

    # Empacotamento por semana: respeita capacidade total e limite CAMEBA
    entregas = []
    for semana in sorted(df["Semana Demanda"].dropna().unique()):
        chunks_semana = [c for c in chunks if c["week"] == semana]
        chunks_semana.sort(key=lambda c: c["qty"], reverse=True)
        for chunk in chunks_semana:
            colocado = False
            for entrega in entregas:
                if entrega["week"] != semana:
                    continue
                if (entrega["total"] + chunk["qty"] <= capacidade_entrega and
                        (not chunk["is_cameba"] or entrega["cameba"] + chunk["qty"] <= capacidade_cameba)):
                    entrega["chunks"].append(chunk)
                    entrega["total"] += chunk["qty"]
                    if chunk["is_cameba"]:
                        entrega["cameba"] += chunk["qty"]
                    colocado = True
                    break
            if not colocado:
                entregas.append({"chunks": [chunk], "week": semana, "total": chunk["qty"],
                                 "cameba": chunk["qty"] if chunk["is_cameba"] else 0.0})

    # Agendamento com intervalo mínimo, sem ultrapassar a data de necessidade
    prev = None
    entregas_atrasadas = 0
    for entrega in entregas:
        candidato = pd.Timestamp(entrega["week"])
        if prev is not None and candidato < prev + intervalo:
            candidato = prev + intervalo
        prazos = [c["orders"]["Data Necessidade"].min() for c in entrega["chunks"] if not c["orders"].empty]
        prazo_raw = pd.Timestamp(min(prazos)) if prazos else pd.Timestamp(hoje_ref)
        prazo = max(prazo_raw, pd.Timestamp(entrega["week"]), pd.Timestamp(hoje_ref))
        entrega["prazo"] = prazo
        if candidato > prazo:
            entrega["atrasada"] = True
            entregas_atrasadas += 1
        else:
            entrega["atrasada"] = False
        entrega["agendada"] = candidato
        prev = candidato

    # Reconstrói df (nível de pedido + continuação)
    linhas_plan = []
    for chunk in chunks:
        ei = next(i for i, e in enumerate(entregas) if chunk in e["chunks"])
        entrega = entregas[ei]
        if chunk["orders"].empty:
            linhas_plan.append({
                "EntregaID": ei, "Chegada Material": entrega["agendada"], "Entrega Atrasada": entrega["atrasada"],
                "Chunk Qty": chunk["qty"], "Chunk": f"{chunk['chunk_idx']}/{chunk['total_chunks']}",
                "Pedido": "(continuação)", "Cód Confec": chunk["cod"], "Produto": chunk["produto"],
                "Cliente": "", "Marca": "", "Operação": "", "Qtd": 0, "Saldo Calc.": 0, "Em Trânsito": 0,
                "Saldo": 0, "Coberto pela Produção": 0, "Necessidade": chunk["qty"],
                "CAMEBA": chunk["is_cameba"], "Data Necessidade": entrega["agendada"],
                "Origem da Data": "", "Em Confecção": False, "Confecções": "",
                "Segmento": "", "Saldo 5": None, "Tec Faz x Confec": None, "Cons. Unitário": None,
            })
        else:
            for _, row in chunk["orders"].iterrows():
                linhas_plan.append({
                    "EntregaID": ei, "Chegada Material": entrega["agendada"], "Entrega Atrasada": entrega["atrasada"],
                    "Chunk Qty": chunk["qty"], "Chunk": f"{chunk['chunk_idx']}/{chunk['total_chunks']}",
                    "Pedido": row["Pedido"], "Cód Confec": chunk["cod"], "Produto": chunk["produto"],
                    "Cliente": row["Cliente"], "Marca": row["Marca"], "Operação": row["Operação"],
                    "Qtd": row["Qtd"], "Saldo Calc.": row["Saldo Calc."], "Em Trânsito": row["Em Trânsito"],
                    "Saldo": row["Saldo"], "Coberto pela Produção": row["Coberto pela Produção"],
                    "Necessidade": row["Necessidade"], "CAMEBA": bool(row["CAMEBA"]) if "CAMEBA" in row.index else False,
                    "Data Necessidade": row["Data Necessidade"], "Origem da Data": row["Origem da Data"],
                    "Em Confecção": row["Em Confecção"], "Confecções": row["Confecções"],
                    "Segmento": row["Segmento"],
                    "Saldo 5": row.get("Saldo 5"), "Tec Faz x Confec": row.get('Tec Faz "x" Confec'), "Cons. Unitário": row.get("Cons. Unitário"),
                })
    df = pd.DataFrame(linhas_plan)
    df["CAMEBA"] = df["CAMEBA"].astype(bool)
    df["Lote"] = df["Chegada Material"].map({c: f"Entrega {i+1:02d} · {pd.Timestamp(c).strftime('%d/%m/%Y')}" for i, c in enumerate(sorted(df["Chegada Material"].dropna().unique()))}).fillna("Sem data")

# ==================== KPIs ====================

st.markdown("### 📈 Visão Geral do Planejamento")

st.caption(f"📄 **{len(df_proj) if df_proj is not None else 0}** linhas lidas da planilha de Projeção. Após os filtros: **{len(df) if not df.empty else 0}** itens.")

qtd_total = float(df["Qtd"].sum()) if not df.empty else 0.0
saldo_total = float(df["Saldo"].sum()) if not df.empty else 0.0
coberto_total = float(df["Coberto pela Produção"].sum()) if not df.empty else 0.0
necessidade_total = float(df["Chunk Qty"].sum()) if (not df.empty and "Chunk Qty" in df.columns) else (float(df["Necessidade"].sum()) if not df.empty else 0.0)
em_conf_itens = int(df["Em Confecção"].sum()) if not df.empty else 0
n_lotes = df["Lote"].nunique() if not df.empty else 0
primeira = pd.Timestamp(df["Chegada Material"].min()) if not df.empty else pd.NaT
ultima = pd.Timestamp(df["Chegada Material"].max()) if not df.empty else pd.NaT
entregas_atrasadas = entregas_atrasadas if "entregas_atrasadas" in dir() else 0

colunas_kpi = st.columns(4)
with colunas_kpi[0]:
    with st.container(border=True):
        st.metric("🧾 Itens", fmt_num(df["Cód Confec"].nunique() if not df.empty else 0), help="Itens únicos na projeção")
with colunas_kpi[1]:
    with st.container(border=True):
        st.metric("📦 Qtd Pedida", fmt_num(qtd_total))
with colunas_kpi[2]:
    with st.container(border=True):
        st.metric("💰 Saldo em Aberto", fmt_num(saldo_total), help="((Qtd* - Saldo Calc.) - Em Trânsito)")
with colunas_kpi[3]:
    with st.container(border=True):
        st.metric("🎯 Necessidade Líquida", fmt_num(necessidade_total), help="Saldo em aberto menos a produção já em andamento")
colunas_kpi2 = st.columns(3)
with colunas_kpi2[0]:
    with st.container(border=True):
        st.metric("🏭 Já em Produção", fmt_num(coberto_total))
with colunas_kpi2[1]:
    with st.container(border=True):
        st.metric("📅 Entregas", fmt_num(n_lotes), help=f"Intervalo mínimo de {intervalo_semanas} semana(s)")
with colunas_kpi2[2]:
    with st.container(border=True):
        periodo = f"{primeira.strftime('%d/%m/%y')} → {ultima.strftime('%d/%m/%y')}" if pd.notna(primeira) and pd.notna(ultima) else "—"
        st.metric("🗓️ Horizonte", periodo)
if pd.notna(primeira) and pd.notna(ultima):
    st.caption(f"🗓️ Horizonte planejado: **{primeira.strftime('%d/%m/%Y')}** → **{ultima.strftime('%d/%m/%Y')}** · {em_conf_itens} itens já possuem confecção definida.")
    if "Saldo 5" in df.columns:
        def _sem_tecido(row):
            s5 = row.get("Saldo 5")
            cons = row.get("Cons. Unitário")
            nec = row.get("Necessidade", 0)
            if pd.isna(s5):
                return True
            if pd.isna(cons) or cons == 0:
                return False
            return float(s5) < float(nec) * float(cons)
        n_sem_tecido = int(df.apply(_sem_tecido, axis=1).sum())
        if n_sem_tecido > 0:
            st.warning(f"⚠️ {n_sem_tecido} item(ns) sem tecido suficiente para a necessidade planejada.")
if entregas_atrasadas:
    st.warning(f"⚠️ {entregas_atrasadas} entrega(s) antecipadas para não ultrapassar a data de necessidade.")

# ==================== GRÁFICOS ====================

st.markdown("### 📊 Entregas Planejadas")

if not df.empty:
    resumo = pd.DataFrame([{"Lote": f"Entrega {i+1:02d} · {pd.Timestamp(e['agendada']).strftime('%d/%m/%Y')}", "Chegada": e["agendada"], "Itens": len(e["chunks"]), "Necessidade": sum(c["qty"] for c in e["chunks"]), "CAMEBA": sum(c["qty"] for c in e["chunks"] if c["is_cameba"]), "Atrasada": e["atrasada"]} for i, e in enumerate(entregas)]).sort_values("Chegada")

    with st.container(border=True):
        figura = go.Figure()
        figura.add_bar(x=resumo["Lote"], y=resumo["Necessidade"], name="Necessidade líquida", marker_color="#6366f1")
        figura.update_layout(template=template_plotly(), barmode="group", height=400, title="Necessidade por entrega", xaxis_title="", yaxis_title="Unidades", legend=dict(orientation="h", y=1.12), margin=dict(t=70, l=10, r=10, b=10))
        st.plotly_chart(figura, width="stretch")

    with st.expander("📊 Gráficos detalhados", expanded=False):
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                por_operacao = df.groupby("Operação").agg(Necessidade=("Necessidade", "sum")).sort_values("Necessidade", ascending=False).reset_index()
                if len(por_operacao) > 7:
                    resto = por_operacao.iloc[7:]["Necessidade"].sum()
                    por_operacao = pd.concat([por_operacao.iloc[:7], pd.DataFrame([{"Operação": "Outros", "Necessidade": resto}])], ignore_index=True)
                pizza = go.Figure(go.Pie(labels=por_operacao["Operação"], values=por_operacao["Necessidade"], hole=0.55, marker=dict(colors=cores_grafico()), textinfo="percent"))
                pizza.update_layout(template=template_plotly(), height=360, title="Necessidade por operação", showlegend=True, legend=dict(orientation="v", font=dict(size=10)), margin=dict(t=60, l=10, r=10, b=10))
                st.plotly_chart(pizza, width="stretch")
        with g2:
            with st.container(border=True):
                top_ops = df["Operação"].value_counts().head(6).index.tolist()
                composicao = df.copy()
                composicao["Operação (agrupada)"] = np.where(composicao["Operação"].isin(top_ops), composicao["Operação"], "Outras")
                tabela_comp = composicao.pivot_table(index="Lote", columns="Operação (agrupada)", values="Necessidade", aggfunc="sum", fill_value=0).reindex(resumo["Lote"]).reset_index()
                ordem_ops = [c for c in tabela_comp.columns if c != "Lote"]
                figura_comp = go.Figure()
                for indice, operacao in enumerate(ordem_ops):
                    figura_comp.add_bar(x=tabela_comp["Lote"], y=tabela_comp[operacao], name=str(operacao), marker_color=cores_grafico()[indice % len(cores_grafico())])
                figura_comp.update_layout(template=template_plotly(), barmode="stack", height=360, title="Composição por operação", xaxis_title="", yaxis_title="Unidades", legend=dict(orientation="h", y=-0.25, font=dict(size=9)), margin=dict(t=60, l=10, r=10, b=10))
                st.plotly_chart(figura_comp, width="stretch")

    st.markdown("### 🗓️ Planejamento por Lote")
    with st.container(border=True):
        st.dataframe(resumo.rename(columns={"Lote": "Lote", "Chegada": "Chegada do material", "Itens": "Itens", "Necessidade": "Necessidade líquida", "CAMEBA": "CAMEBA (un.)"}).assign(**{"Chegada do material": lambda d: d["Chegada do material"].map(fmt_data)}), width="stretch", hide_index=True)

# ==================== DETALHAMENTO POR ENTREGA ====================

st.markdown("### 📋 Detalhamento por Entrega e Item")

if not df.empty:
    lotes_disponiveis = df["Lote"].unique().tolist()
    selecao_lotes = st.multiselect("Filtrar por entrega", lotes_disponiveis, default=lotes_disponiveis, key="filtro_lotes")
    detalhe = df[df["Lote"].isin(selecao_lotes)] if selecao_lotes else df
    if detalhe.empty:
        st.info("Nenhum item selecionado.")
    else:
        entregas_ordenadas = detalhe.groupby("Lote", sort=False)["Chegada Material"].first().sort_values().index.tolist()
        for lote in entregas_ordenadas:
            bloco = detalhe[detalhe["Lote"] == lote].copy()
            chegada = bloco["Chegada Material"].iloc[0]
            n_itens = bloco["Cód Confec"].nunique()
            total_un = float(bloco["Chunk Qty"].sum()) if "Chunk Qty" in bloco.columns else float(bloco["Necessidade"].sum())
            atrasada = bool(bloco["Entrega Atrasada"].iloc[0]) if "Entrega Atrasada" in bloco.columns else False
            titulo = f"{lote}  ·  {n_itens} item(ns)  ·  {fmt_num(total_un)} unidades" + ("  ⚠️ atrasada" if atrasada else "")
            with st.expander(titulo, expanded=False):
                for cod, grupo in bloco.groupby("Cód Confec", sort=False):
                    produto = str(grupo["Produto"].iloc[0])
                    total_item = float(grupo["Chunk Qty"].iloc[0]) if "Chunk Qty" in grupo.columns else float(grupo["Necessidade"].sum())
                    chunk_label = str(grupo["Chunk"].iloc[0]) if "Chunk" in grupo.columns else ""
                    total_chunks = int(chunk_label.split("/")[-1]) if "/" in chunk_label else 1
                    part_info = f" (parte {chunk_label})" if total_chunks > 1 else ""
                    cameba = bool(grupo["CAMEBA"].iloc[0]) if "CAMEBA" in grupo.columns else False
                    st.markdown(f"**Item `{cod}` — {produto} — {fmt_num(total_item)} unidades{part_info}**" + ("  (CAMEBA)" if cameba else ""))
                    s5 = grupo["Saldo 5"].iloc[0] if "Saldo 5" in grupo.columns else None
                    cons = grupo["Cons. Unitário"].iloc[0] if "Cons. Unitário" in grupo.columns else None
                    if pd.notna(s5):
                        tec_nec = float(total_item) * float(cons) if pd.notna(cons) and cons else 0.0
                        status = "✅" if (pd.isna(cons) or cons == 0 or float(s5) >= tec_nec) else "⚠️ sem tecido suficiente"
                        st.caption(f"🧵 Tecido: disponível {fmt_num(s5)} | necessário {fmt_num(tec_nec)} {status}")
                    linhas_pedido = []
                    for _, row in grupo.sort_values("Data Necessidade").iterrows():
                        if str(row["Pedido"]) == "(continuação)":
                            linhas_pedido.append(f"- *(continuação — {fmt_num(row['Necessidade'])} un)*")
                        else:
                            linhas_pedido.append(f"- Pedido **{row['Pedido']}** — {fmt_num(row['Necessidade'])} un — necessidade {fmt_data(row['Data Necessidade'])} ({row['Origem da Data']})")
                    st.markdown("\n".join(linhas_pedido))
                    st.markdown("")

# ==================== ITENS PEQUENOS (< min) ====================

if not df_pequenos.empty:
    st.markdown("### 📌 Itens com Necessidade < 100 (exibidos separadamente)")
    with st.container(border=True):
        resumo_peq = df_pequenos.groupby("Cód Confec", sort=False).agg(Produto=("Produto", "first"), Pedidos=("Pedido", "count"), Necessidade=("Necessidade", "sum")).reset_index().sort_values("Necessidade", ascending=False)
        st.dataframe(resumo_peq.rename(columns={"Cód Confec": "Cód Confec", "Necessidade": "Necessidade total"}), width="stretch", hide_index=True, height=300)

# ==================== TECIDO SUGERIDO ====================

st.markdown("### 🧵 Tecido Sugerido")

df_estoque_pf = preparar_estoque(df_estoque_raw) if df_estoque_raw is not None else None
tecido_rows = []
if df_estoque_pf is not None:
    codigos_proj = set(df["Cód Confec"].tolist()) if not df.empty else set()
    for _, row in df_estoque_pf.iterrows():
        cod = row.get("Cód Confec_norm", "")
        if cod not in codigos_proj:
            continue
        saldo5 = row.get("Saldo 5", np.nan)
        if pd.isna(saldo5) or saldo5 >= 0:
            continue
        tec_faz = row.get('Tec Faz "x" Confec', np.nan)
        cons = row.get("Cons. Unitário", np.nan)
        if pd.isna(tec_faz):
            tec_faz = 0
        calc = float(saldo5) + float(tec_faz)
        tecido = 0.0
        if calc < 0:
            tecido = (abs(calc) * 1.10) * (float(cons) if pd.notna(cons) else 0.0)
        if tecido > 0:
            tecido_rows.append({"Cód Confec": cod, "Descrição": str(row.get("Descrição", "") or ""), "Marca": str(row.get("Marca", "Sem Marca") or "Sem Marca"), "Saldo 5": saldo5, "Tec Faz x Confec": tec_faz, "Cons. Unitário": cons, "Tecido Sugerido (m)": round(tecido, 3)})

tecido_pf = pd.DataFrame(tecido_rows)
if tecido_pf.empty:
    st.info("Não há itens com sugestão de tecido (Saldo 5 < 0) nos códigos da projeção.")
else:
    t1, t2, t3 = st.columns(3)
    with t1:
        with st.container(border=True):
            st.metric("Itens com sugestão", fmt_num(len(tecido_pf)))
    with t2:
        with st.container(border=True):
            st.metric("Total Tecido Sugerido (m)", f"{tecido_pf['Tecido Sugerido (m)'].sum():,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with t3:
        with st.container(border=True):
            st.metric("Códigos únicos", fmt_num(tecido_pf["Cód Confec"].nunique()))
    with st.container(border=True):
        st.dataframe(tecido_pf.sort_values("Tecido Sugerido (m)", ascending=False).style.format({"Saldo 5": "{:,.0f}", "Tec Faz x Confec": "{:,.0f}", "Cons. Unitário": "{:,.4f}", "Tecido Sugerido (m)": "{:,.3f}"}), width="stretch", hide_index=True, height=300)

# ==================== COMPRA SUGERIDA ====================

st.markdown("### 🛒 Compra Sugerida (Reposição de Estoque)")

compra_rows = []
if df_estoque_pf is not None:
    codigos_proj = set(df["Cód Confec"].tolist()) if not df.empty else set()
    for _, row in df_estoque_pf.iterrows():
        cod = row.get("Cód Confec_norm", "")
        if cod not in codigos_proj:
            continue
        saldo5 = row.get("Saldo 5", np.nan)
        if pd.isna(saldo5) or saldo5 >= 0:
            continue
        tec_faz = row.get('Tec Faz "x" Confec', np.nan)
        if pd.isna(tec_faz):
            tec_faz = 0
        compra = math.ceil(min(abs(saldo5) * 1.10, tec_faz) if tec_faz else abs(saldo5) * 1.10)
        if compra > 0:
            compra_rows.append({"Cód Confec": cod, "Descrição": str(row.get("Descrição", "") or ""), "Marca": str(row.get("Marca", "Sem Marca") or "Sem Marca"), "Saldo 5": saldo5, "Tec Faz x Confec": tec_faz, "Compra Sugerida": compra})

compra_pf = pd.DataFrame(compra_rows)
if compra_pf.empty:
    st.info("Não há itens com compra sugerida (Saldo 5 < 0) nos códigos da projeção.")
else:
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.metric("Itens com compra sugerida", fmt_num(len(compra_pf)))
    with c2:
        with st.container(border=True):
            st.metric("Total Compra Sugerida", fmt_num(compra_pf["Compra Sugerida"].sum()))
    with st.container(border=True):
        st.dataframe(compra_pf.sort_values("Compra Sugerida", ascending=False).style.format({"Saldo 5": "{:,.0f}", "Tec Faz x Confec": "{:,.0f}", "Compra Sugerida": "{:,.0f}"}), width="stretch", hide_index=True, height=300)

# ==================== EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Demanda")
    if lotes_ordenados:
        resumo_export = resumo.copy()
        resumo_export["Chegada"] = resumo_export["Chegada"].dt.strftime("%d/%m/%Y")
        resumo_export.to_excel(writer, index=False, sheet_name="Resumo por Lote")
    if "tecido_pf" in globals() and not tecido_pf.empty:
        tecido_pf.to_excel(writer, index=False, sheet_name="Tecido Sugerido")
    if "compra_pf" in globals() and not compra_pf.empty:
        compra_pf.to_excel(writer, index=False, sheet_name="Compra Sugerida")
    if not df_pequenos.empty:
        df_pequenos.to_excel(writer, index=False, sheet_name="Itens < 100")

c1e, c2e = st.columns(2)
with c1e:
    st.download_button("📥 Baixar CSV — Planejamento", data=df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig"), file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.csv", mime="text/csv", width="stretch")
with c2e:
    st.download_button("📊 Baixar Excel — Projeção completa", data=buffer.getvalue(), file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

# ==================== COMO É CALCULADO ====================

with st.expander("ℹ️ Como o planejamento é calculado", expanded=False):
    st.markdown(f"""
1. **Data de necessidade** de cada item: `Dt. Agendamento` → se vazia, `Dt Entrega` → se vazia, `Dt Pedido`, antecipada 5 dias.
2. O **saldo em aberto** é calculado por `((Qtd* - Saldo Calc.) - Em Trânsito)`.
3. A **necessidade líquida** desconta, por código, o saldo dos pedidos que já possuem confecção.
4. Itens com necessidade total < **{qtd_min_item_pf or 100}** são exibidos separadamente.
5. Cada item é distribuído em **{semanas_distribuir}** semanas (quantidade por parte = total ÷ {semanas_distribuir}).
6. Cada **entrega** respeita **{int(capacidade_entrega):,} unidades** no total e no máximo **{int(capacidade_cameba):,} unidades** ({int(pct_cameba)}%) para CAMEBA.
7. As entregas são agendadas para **não ultrapassar a data de necessidade** e espaçadas pelo intervalo mínimo.
""")