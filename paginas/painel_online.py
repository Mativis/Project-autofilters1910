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
st.caption(
    "Regra: |Saldo 5| × 1,1 − Tec Faz 'x' Confec (mínimo zero). "
    "O catálogo online define a confecção de cada código."
)

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
            # ---------- enriquecimento ----------
            mapa_conf = {}
            mapa_item = {}
            if not catalogo.empty and "codigo" in catalogo.columns:
                for _, r in catalogo.iterrows():
                    cod = str(r.get("codigo", "")).strip()
                    if not cod:
                        continue
                    conf = str(r.get("confeccao", "") or "").strip()
                    if conf:
                        mapa_conf[cod] = conf
                    item = str(r.get("item", "") or "").strip()
                    if item:
                        mapa_item[cod] = item

            neg["Confecção sugerida"] = neg["Código"].map(mapa_conf).fillna("Sem confecção cadastrada")
            if "Descrição" in neg.columns:
                neg["Item"] = neg["Descrição"].astype(str).str.strip()
            else:
                neg["Item"] = neg["Código"].map(mapa_item).fillna("—")
            neg.loc[neg["Item"].isin(["", "nan", "None"]), "Item"] = neg["Código"].map(mapa_item)

            tec_col = 'Tec Faz "x" Confec'
            neg["Tec Faz x Confec"] = (
                pd.to_numeric(neg[tec_col], errors="coerce").fillna(0)
                if tec_col in neg.columns else 0.0
            )
            neg["Cons. Unitário"] = (
                pd.to_numeric(neg["Cons. Unitário"], errors="coerce").fillna(0)
                if "Cons. Unitário" in neg.columns else 0.0
            )
            neg["Saldo 5"] = saldo5[neg.index]
            neg["Fator"] = 1.10
            neg["Base 1,1"] = (neg["Saldo 5"].abs() * 1.10).round(0)
            neg["Compra sugerida"] = (neg["Base 1,1"] - neg["Tec Faz x Confec"]).clip(lower=0).round()
            neg["Tecido necessário (m)"] = (neg["Compra sugerida"] * neg["Cons. Unitário"]).round(2)

            # ---------- KPIs ----------
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.markdown(card("Total compra sugerida", fmt_num(neg["Compra sugerida"].sum()),
                                 "unidades", "#b71c1c"), unsafe_allow_html=True)
            with k2:
                st.markdown(card("Itens com Saldo 5 negativo", fmt_num(len(neg)),
                                 "códigos", "#ef6c00"), unsafe_allow_html=True)
            with k3:
                st.markdown(card("Confecções", fmt_num(neg["Confecção sugerida"].nunique()),
                                 "com sugestão", "#3949ab"), unsafe_allow_html=True)
            with k4:
                sem = int((neg["Confecção sugerida"] == "Sem confecção cadastrada").sum())
                st.markdown(card("Sem confecção", fmt_num(sem),
                                 "cadastrar no catálogo", "#9e9e9e"), unsafe_allow_html=True)

            # ---------- detalhe por item ----------
            st.markdown("#### 🔍 Detalhe por item")
            confs = sorted(neg["Confecção sugerida"].unique().tolist())
            conf_sel = st.multiselect("Filtrar confecção (detalhe)",
                                      options=confs, default=confs, key="vf_compra_conf")
            detalhe = neg[neg["Confecção sugerida"].isin(conf_sel)] if conf_sel else neg

            colunas_detalhe = {
                "Código": st.column_config.TextColumn("Código", width="small"),
                "Item": st.column_config.TextColumn("Item", width="large"),
                "Marca": st.column_config.TextColumn("Marca", width="small"),
                "Confecção sugerida": st.column_config.TextColumn("Confecção", width="medium"),
                "Saldo 5": st.column_config.NumberColumn("Saldo 5", format="%.0f"),
                "Tec Faz x Confec": st.column_config.NumberColumn("Tec Faz", format="%.0f"),
                "Cons. Unitário": st.column_config.NumberColumn("Cons. un.", format="%.4f"),
                "Base 1,1": st.column_config.NumberColumn("Base 1,1", format="%.0f"),
                "Compra sugerida": st.column_config.NumberColumn("Compra", format="%.0f"),
                "Tecido necessário (m)": st.column_config.NumberColumn("Tecido (m)", format="%.2f"),
            }
            ordem = [c for c in ("Código", "Item", "Marca", "Confecção sugerida", "Saldo 5",
                                 "Tec Faz x Confec", "Cons. Unitário", "Base 1,1",
                                 "Compra sugerida", "Tecido necessário (m)") if c in detalhe.columns]
            st.dataframe(
                detalhe[ordem].sort_values("Compra sugerida", ascending=False),
                width="stretch", hide_index=True, height=360,
                column_config=colunas_detalhe,
            )

            # ---------- resumo por confecção ----------
            st.markdown("#### 📦 Resumo por confecção")
            resumo = (
                neg.groupby("Confecção sugerida", as_index=False)
                .agg(
                    Itens=("Código", "count"),
                    **{"Saldo 5": ("Saldo 5", "sum")},
                    **{"Compra sugerida": ("Compra sugerida", "sum")},
                    **{"Tecido necessário (m)": ("Tecido necessário (m)", "sum")},
                )
                .sort_values("Compra sugerida", ascending=False)
            )

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
                        resumo = resumo.merge(cap, left_on="Confecção sugerida",
                                              right_index=True, how="left")
                        resumo["Semanas p/ absorver"] = (
                            resumo["Compra sugerida"] / resumo["Capacidade semanal"].replace(0, pd.NA)
                        ).round(1)
                except Exception:
                    st.caption("Não foi possível calcular a capacidade a partir da produção.")

            st.dataframe(
                resumo,
                width="stretch", hide_index=True,
                column_config={
                    "Confecção sugerida": st.column_config.TextColumn("Confecção", width="large"),
                    "Itens": st.column_config.NumberColumn("Itens", format="%d"),
                    "Saldo 5": st.column_config.NumberColumn("Saldo 5", format="%.0f"),
                    "Compra sugerida": st.column_config.NumberColumn("Compra sugerida", format="%.0f"),
                    "Tecido necessário (m)": st.column_config.NumberColumn("Tecido (m)", format="%.2f"),
                    "Capacidade semanal": st.column_config.NumberColumn("Capac./sem.", format="%.0f"),
                    "Semanas p/ absorver": st.column_config.NumberColumn("Semanas", format="%.1f"),
                },
            )

            # ---------- salvar análise ----------
            if st.button("💾 Salvar análise desta demanda", type="primary"):
                r = cloud.salvar_analise(
                    demanda_id,
                    f"Análise {date.today().strftime('%d/%m/%Y')}",
                    {
                        "resumo": resumo.to_dict("records"),
                        "itens": detalhe[ordem].to_dict("records"),
                        "pedidos": int(len(kb)),
                        "total_compra": float(neg["Compra sugerida"].sum()),
                    },
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
