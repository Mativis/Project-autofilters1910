"""
Projeção Futuro
---------------
Planejamento de produção com base na planilha Projeção.xlsx,
cruzando com Pedidos e Estoque já disponíveis no sistema.

Considera intervalo mínimo entre pedidos de chegada de material a cada 1 semana.
Utiliza 'Dt Agendamento' como prioridade para programação; caso não exista,
utiliza 'Dt Entrega'. Leva em consideração pedidos já em confecção.
"""

import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nucleo import (
    aplicar_estilo_comum,
    cabecalho,
    cores_grafico,
    fmt_data,
    fmt_num,
    fmt_pct,
    load_excel,
    normalizar_cod,
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

df_pedidos, df_estoque = sidebar_arquivos()

st.markdown("""
<style>
.main .block-container { max-width: 1500px; }
</style>
""", unsafe_allow_html=True)

cabecalho(
    "📅 Projeção Futuro",
    "Planejamento de produção com intervalo mínimo de 1 semana entre chegadas de material — "
    f"data de referência: {date.today().strftime('%d/%m/%Y')}",
)

with st.sidebar:
    st.markdown("---")
    st.header("📁 Arquivo de Projeção")
    arquivo_proj = st.file_uploader(
        "Upload Projeção.xlsx",
        type=["xlsx", "xls"],
        help="Planilha com os dados para projeção e planejamento",
    )
    if arquivo_proj is not None:
        try:
            df_proj = load_excel(arquivo_proj)
            st.session_state["df_projecao"] = df_proj
            st.success("Projeção carregada com sucesso")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
    elif "df_projecao" in st.session_state:
        df_proj = st.session_state["df_projecao"]
        st.info("Usando projeção carregada anteriormente")
    else:
        df_proj = None

if df_proj is None:
    st.info("👆 Faça o upload da planilha **Projeção.xlsx** na barra lateral para gerar a projeção futura.")
    st.stop()

# Normalização
df_proj = df_proj.copy()
df_proj.columns = df_proj.columns.str.strip()

# Detectar colunas
col_dt_agend = None
for c in df_proj.columns:
    if "agend" in str(c).lower():
        col_dt_agend = c
        break

col_dt_entrega_p = None
for c in df_proj.columns:
    if str(c).strip().lower() in ["dt entrega", "dt. entrega"]:
        col_dt_entrega_p = c
        break

col_pedido = "Pedido" if "Pedido" in df_proj.columns else None
col_produto = "Produto" if "Produto" in df_proj.columns else None
col_cod_prod = "Cód Prod" if "Cód Prod" in df_proj.columns else ("Cod. Produto" if "Cod. Produto" in df_proj.columns else None)
col_qtd = "Qtd *" if "Qtd *" in df_proj.columns else None
col_saldo_pedido = "Saldo Pedido" if "Saldo Pedido" in df_proj.columns else None
col_saldo_calc = "Saldo Calc." if "Saldo Calc." in df_proj.columns else None
col_em_transito = "Em Trânsito" if "Em Trânsito" in df_proj.columns else None
col_cliente = "Cliente" if "Cliente" in df_proj.columns else None
col_marca = "Marca" if "Marca" in df_proj.columns else None
col_grupo = "Grupo do Cliente" if "Grupo do Cliente" in df_proj.columns else None
col_colecao = "Coleção" if "Coleção" in df_proj.columns else None
col_operacao = "Operação Produtiva" if "Operação Produtiva" in df_proj.columns else None
col_status = "Sts do Pedido" if "Sts do Pedido" in df_proj.columns else None

# Datas
if col_dt_agend and col_dt_agend in df_proj.columns:
    df_proj["DATA_PROG"] = pd.to_datetime(df_proj[col_dt_agend], errors="coerce")
if col_dt_entrega_p and col_dt_entrega_p in df_proj.columns:
    df_proj["DATA_ENTREGA_REF"] = pd.to_datetime(df_proj[col_dt_entrega_p], errors="coerce")
df_proj["DATA_PRIORITARIA"] = df_proj["DATA_PROG"].fillna(df_proj["DATA_ENTREGA_REF"])

# Valores numéricos
for c in [col_qtd, col_saldo_pedido, col_saldo_calc, col_em_transito]:
    if c and c in df_proj.columns:
        df_proj[c] = pd.to_numeric(df_proj[c], errors="coerce").fillna(0)

# Cruzar com Estoque/Pedidos para entender "em confecção"
pedidos_em_confeccao = set()
if df_pedidos is not None:
    try:
        df_p = preparar_pedidos(df_pedidos)
        pedidos_em_confeccao = set(df_p["Compra"].astype(str).unique())
    except Exception:
        pass

if col_pedido and col_pedido in df_proj.columns:
    df_proj["EM_CONF"] = df_proj[col_pedido].astype(str).isin(pedidos_em_confeccao)
else:
    df_proj["EM_CONF"] = False

# Filtros
with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros Projeção")
    if col_marca and col_marca in df_proj.columns:
        marcas_p = st.multiselect("Marca", sorted(df_proj[col_marca].dropna().unique().tolist()), default=sorted(df_proj[col_marca].dropna().unique().tolist()))
    else:
        marcas_p = None
    if col_grupo and col_grupo in df_proj.columns:
        grupos_p = st.multiselect("Grupo do Cliente", sorted(df_proj[col_grupo].dropna().unique().tolist()), default=sorted(df_proj[col_grupo].dropna().unique().tolist()))
    else:
        grupos_p = None
    if col_operacao and col_operacao in df_proj.columns:
        op_p = st.multiselect("Operação Produtiva", sorted(df_proj[col_operacao].dropna().unique().tolist()), default=sorted(df_proj[col_operacao].dropna().unique().tolist()))
    else:
        op_p = None
    considerar_em_conf = st.checkbox("Considerar pedidos já em confecção", value=True)
    intervalo_semanas = st.number_input("Intervalo mínimo entre chegadas (semanas)", min_value=1, max_value=4, value=1, step=1)

df_f = df_proj.copy()
if marcas_p is not None and col_marca:
    df_f = df_f[df_f[col_marca].isin(marcas_p)]
if grupos_p is not None and col_grupo:
    df_f = df_f[df_f[col_grupo].isin(grupos_p)]
if op_p is not None and col_operacao:
    df_f = df_f[df_f[col_operacao].isin(op_p)]
if not considerar_em_conf:
    df_f = df_f[~df_f["EM_CONF"]]

if df_f.empty:
    st.warning("Nenhum registro encontrado com os filtros selecionados.")
    st.stop()

# KPIs
qtd_total_proj = df_f[col_qtd].sum() if col_qtd else 0
saldo_total_proj = df_f[col_saldo_pedido].sum() if col_saldo_pedido else 0
em_transito_proj = df_f[col_em_transito].sum() if col_em_transito else 0
em_conf_proj = int(df_f["EM_CONF"].sum())

k1,k2,k3,k4,k5 = st.columns(5)
with k1:
    with st.container(border=True): st.metric("Itens na Projeção", f"{len(df_f)}")
with k2:
    with st.container(border=True): st.metric("Qtd Total", fmt_num(qtd_total_proj))
with k3:
    with st.container(border=True): st.metric("Saldo Pedido", fmt_num(saldo_total_proj))
with k4:
    with st.container(border=True): st.metric("Em Trânsito", fmt_num(em_transito_proj))
with k5:
    with st.container(border=True): st.metric("Pedidos já em Confecção", f"{em_conf_proj}")

st.markdown("### 📊 Visão por Data Prioritária (Agendamento / Entrega)")

df_data = df_f.dropna(subset=["DATA_PRIORITARIA"]).copy()
if not df_data.empty:
    df_data["SEMANA"] = df_data["DATA_PRIORITARIA"].dt.to_period("W").apply(lambda r: r.start_time)
    df_semana = df_data.groupby("SEMANA").agg(
        Pedidos=("Pedido", "count") if col_pedido else ("DATA_PRIORITARIA", "count"),
        Qtd=(col_qtd, "sum") if col_qtd else ("DATA_PRIORITARIA", "count"),
        Saldo=(col_saldo_pedido, "sum") if col_saldo_pedido else ("DATA_PRIORITARIA", "count"),
        EmConf=("EM_CONF", "sum"),
    ).reset_index()
    df_semana = df_semana.sort_values("SEMANA")

    c1,c2 = st.columns([1.6,1])
    with c1:
        with st.container(border=True):
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_semana["SEMANA"], y=df_semana["Qtd"], name="Qtd", marker_color="#6366f1"))
            fig.add_trace(go.Bar(x=df_semana["SEMANA"], y=df_semana["Saldo"], name="Saldo", marker_color="#f59e0b"))
            fig.update_layout(barmode="group", template=template_plotly(), height=380, title="Necessidade por Semana (Intervalo >= 1 semana)", margin=dict(t=60,l=10,r=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        with st.container(border=True):
            df_op = df_data.groupby(col_operacao).agg(Qtd=(col_qtd,"sum")).reset_index().sort_values("Qtd", ascending=False)
            fig = px.pie(df_op, names=col_operacao, values="Qtd", hole=0.5, color_discrete_sequence=cores_grafico(), title="Por Operação Produtiva")
            fig.update_layout(height=380, margin=dict(t=60,l=10,r=10,b=10))
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Não há datas de agendamento/entrega para compor a projeção por semana.")

st.markdown("### 📋 Planejamento Sugerido (cronograma com intervalo mínimo de 1 semana)")
df_plan = df_f.copy()
df_plan["DATA_PRIORITARIA"] = df_plan["DATA_PRIORITARIA"].fillna(date.today())
df_plan = df_plan.sort_values(["DATA_PRIORITARIA", col_pedido if col_pedido else df_plan.index])

# Agrupar por semana mínima
plan_rows = []
ultima_semana = None
semana_seq = 0
for _, row in df_plan.iterrows():
    d = pd.to_datetime(row["DATA_PRIORITARIA"]).date()
    # semana ISO
    iso = d.isocalendar()
    chave_semana = f"{iso.year}-W{iso.week:02d}"
    if ultima_semana != chave_semana:
        semana_seq += 1
        ultima_semana = chave_semana
    plan_rows.append({
        "Semana Planejada": f"S{semana_seq:02d} ({chave_semana})",
        "Data Ref. (Agend./Entrega)": d.strftime("%d/%m/%Y") if pd.notna(d) else "—",
        "Pedido": row.get(col_pedido),
        "Produto": row.get(col_produto),
        "Cód Prod": row.get(col_cod_prod),
        "Cliente": row.get(col_cliente),
        "Marca": row.get(col_marca),
        "Operação Produtiva": row.get(col_operacao),
        "Qtd": row.get(col_qtd),
        "Saldo Pedido": row.get(col_saldo_pedido),
        "Em Trânsito": row.get(col_em_transito),
        "Em Confecção": "Sim" if row.get("EM_CONF") else "Não",
        "Dt. Agendamento": fmt_data(row.get(col_dt_agend)) if col_dt_agend and col_dt_agend in df_plan.columns else "—",
        "Dt Entrega": fmt_data(row.get(col_dt_entrega_p)) if col_dt_entrega_p and col_dt_entrega_p in df_plan.columns else "—",
    })

df_plano = pd.DataFrame(plan_rows)
with st.container(border=True):
    st.dataframe(df_plano, use_container_width=True, hide_index=True)

# Exportação
st.markdown("### 📥 Exportar Projeção Futuro")
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_f.to_excel(writer, index=False, sheet_name="Projeção Base")
    df_plano.to_excel(writer, index=False, sheet_name="Planejamento Sugerido")
    if 'df_semana' in locals() and not df_semana.empty:
        df_semana.to_excel(writer, index=False, sheet_name="Por Semana")

c1e,c2e = st.columns(2)
with c1e:
    st.download_button("📥 Baixar CSV - Planejamento", data=df_plano.to_csv(index=False, encoding="utf-8-sig"), file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.csv", mime="text/csv", use_container_width=True)
with c2e:
    st.download_button("📊 Baixar Excel - Projeção Completa", data=buffer.getvalue(), file_name=f"projecao_futuro_{date.today().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
