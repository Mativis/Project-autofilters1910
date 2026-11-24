"""
Painel Online — Visualfil Cloud
--------------------------------
Lê Pedidos/Estoque/Produção já salvos online para uma demanda, gera a
visualização/análise "salva" e o indicador de compra sugerida por confecção.
"""
from datetime import date

import pandas as pd
import streamlit as st

import nuvem as cloud
from nucleo import (
    aplicar_estilo_comum,
    card,
    codigos_saldo2_negativo,
    fmt_num,
    preparar_estoque,
    preparar_pedidos,
)
from rastreabilidade import classificar_rastreabilidade

st.set_page_config(page_title="Painel Online — Visualfil", page_icon="☁️", layout="wide")
aplicar_estilo_comum()

if not cloud.logado():
    st.warning("Faça login em **🔐 Entrar** para acessar o painel online.")
    st.stop()

st.title("☁️ Painel Online — Análise salva")
st.caption(
    "Os dados vêm dos XLSX enviados na **Administração → Demandas e XLSX**. "
    "Nenhum arquivo precisa ser vinculado localmente."
)

try:
    demandas = cloud.demandas()
except Exception as erro:
    st.error(f"Não foi possível listar demandas: {erro}")
    demandas = []

if not demandas:
    st.info("Nenhuma demanda cadastrada. Peça ao administrador para criar uma e enviar os XLSX.")
    st.stop()

opcoes = {
    f"{d.get('nome')}  ·  fonte: {d.get('fonte') or '—'}": d.get("id")
    for d in demandas
}
escolha = st.selectbox("Demanda", list(opcoes))
demanda_id = opcoes[escolha]
demanda = next((d for d in demandas if d.get("id") == demanda_id), {})


def _carregar(tipo: str):
    try:
        return pd.read_excel(__import__("io").BytesIO(cloud.ler_arquivo(demanda_id, tipo)))
    except Exception:
        return None


df_ped_raw = _carregar("pedidos")
df_est_raw = _carregar("estoque")
df_prod_raw = _carregar("producao")

if df_ped_raw is None and df_est_raw is None:
    st.warning("Esta demanda ainda não tem Pedidos ou Estoque enviados.")
    st.stop()

# ============================ PREPARAÇÃO ============================
pedidos = preparar_pedidos(df_ped_raw) if df_ped_raw is not None else None
estoque = preparar_estoque(df_est_raw) if df_est_raw is not None else None

if pedidos is not None and estoque is not None:
    codigos = codigos_saldo2_negativo(estoque)
    ped = pedidos.copy()
    ped["Cód Confec_norm"] = ped["Cód Confec"].astype(str)
    kb = ped[ped["Cód Confec_norm"].isin(codigos)].copy()
else:
    kb = pd.DataFrame()

if not kb.empty:
    kb["Prioridade"] = kb["Dt Entrega"].apply(
        lambda d: "Atrasado" if pd.notna(d) and d < pd.Timestamp(date.today()) else "Baixa"
    )
    kb["Classificação"] = kb["Status"].map(classificar_rastreabilidade) if "Status" in kb.columns else "Sem classificação"
    # Marca vinda do Estoque
    mapa_marca = {}
    if "Marca" in estoque.columns:
        for cod, marca in zip(estoque["Cód Confec"].astype(str), estoque["Marca"]):
            if cod and pd.notna(marca) and str(marca).strip():
                mapa_marca[cod] = str(marca).strip()
    kb["Marca"] = kb["Cód Confec_norm"].map(mapa_marca).fillna("—")

    st.markdown("### 📊 Indicadores do quadro")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos", fmt_num(len(kb)))
    c2.metric("Unidades", fmt_num(kb["Saldo"].sum()) if "Saldo" in kb.columns else "—")
    c3.metric("Confecções", fmt_num(kb["Confecção"].nunique()) if "Confecção" in kb.columns else "—")
    c4.metric("Atrasados", fmt_num((kb["Prioridade"] == "Atrasado").sum()))

    st.markdown("### 🧭 Pedidos (visão salva)")
    colunas = [c for c in ("Compra", "Cód Confec", "Confeccionado", "Confecção", "Marca",
                           "Qtd", "Saldo", "Dt Entrega", "Classificação", "Prioridade") if c in kb.columns]
    st.dataframe(kb[colunas], width="stretch", hide_index=True)
else:
    st.info("Sem pedidos correspondentes aos códigos com Saldo 2 negativo.")

# ============================ COMPRA SUGERIDA POR CONFECCÃO ============================
st.markdown("### 🛒 Compra sugerida por confecção")

try:
    catalogo = pd.DataFrame(cloud.catalogo())
except Exception:
    catalogo = pd.DataFrame()

if estoque is None or estoque.empty:
    st.info("Estoque não carregado.")
else:
    est = estoque.copy()
    est["Código"] = est["Cód Confec"].astype(str)
    if "Saldo 5" not in est.columns:
        st.info("A planilha de Estoque não tem a coluna Saldo 5.")
    else:
        saldo5 = pd.to_numeric(est["Saldo 5"], errors="coerce").fillna(0)
        neg = est[saldo5 < 0].copy()
        if neg.empty:
            st.success("Nenhum item com Saldo 5 negativo — sem compra sugerida.")
        else:
            # Catálogo: código -> confecção
            mapa_conf = {}
            if not catalogo.empty and "codigo" in catalogo.columns:
                for _, r in catalogo.iterrows():
                    cod = str(r.get("codigo", "")).strip()
                    conf = str(r.get("confeccao", "") or r.get("Fornecedor", "")).strip()
                    if cod and conf:
                        mapa_conf[cod] = conf
            neg["Confecção sugerida"] = neg["Código"].map(mapa_conf).fillna("Sem confecção cadastrada")
            tec_col = 'Tec Faz "x" Confec'
            tec = pd.to_numeric(neg[tec_col], errors="coerce").fillna(0) if tec_col in neg.columns else 0
            neg["Compra sugerida"] = ((saldo5[neg.index].abs() * 1.10) - tec).clip(lower=0).round()
            resumo = (
                neg.groupby("Confecção sugerida")
                .agg(Itens=("Código", "count"), **{"Compra sugerida": ("Compra sugerida", "sum")})
                .reset_index()
                .sort_values("Compra sugerida", ascending=False)
            )
            st.dataframe(resumo, width="stretch", hide_index=True)
            st.metric("Total compra sugerida", fmt_num(resumo["Compra sugerida"].sum()))

            # capacidade por confecção (produção online, se houver)
            if df_prod_raw is not None:
                try:
                    prod = pd.read_excel(__import__("io").BytesIO(cloud.ler_arquivo(demanda_id, "producao")))
                    col_conf = next((c for c in prod.columns if "fornecedor" in str(c).lower()), None)
                    col_qtd = next((c for c in prod.columns if "qtd" in str(c).lower() and "retorn" in str(c).lower()), None)
                    if col_conf and col_qtd:
                        cap = (
                            prod.assign(Qtd=pd.to_numeric(prod[col_qtd], errors="coerce").fillna(0))
                            .groupby(col_conf)["Qtd"].sum().rename("Capacidade semanal")
                        )
                        resumo = resumo.merge(cap, left_on="Confecção sugerida", right_index=True, how="left")
                        resumo["Semanas p/ absorver"] = (
                            resumo["Compra sugerida"] / resumo["Capacidade semanal"].replace(0, pd.NA)
                        ).round(1)
                        st.markdown("##### Capacidade x compra sugerida")
                        st.dataframe(resumo, width="stretch", hide_index=True)
                except Exception:
                    st.caption("Não foi possível calcular a capacidade a partir da produção.")

            # salvar análise
            if st.button("💾 Salvar análise desta demanda", type="primary"):
                r = cloud.salvar_analise(
                    demanda_id,
                    f"Análise {date.today().strftime('%d/%m/%Y')}",
                    {"resumo": resumo.to_dict("records"), "pedidos": int(len(kb))},
                )
                if r.get("ok"):
                    st.success("Análise salva no banco online.")
                else:
                    st.error(r.get("erro", "Erro ao salvar análise."))

st.markdown("### 🗂️ Análises salvas")
try:
    analises = [a for a in cloud.analises() if str(a.get("demanda_id")) == str(demanda_id)]
except Exception:
    analises = []
if analises:
    st.dataframe(pd.DataFrame(analises)[["nome", "criado_em"]], width="stretch", hide_index=True)
else:
    st.caption("Nenhuma análise salva para esta demanda.")
