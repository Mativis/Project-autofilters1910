"""
Painel Online — Visualfil Cloud (Streamlit)
--------------------------------------------
Lê os XLSX salvos online para uma demanda e gera a análise "salva":
indicadores, pedidos, compra sugerida por confecção e discriminada por item.

Performance: pré-agregação no servidor → cache em memória → leitura em lote → paralelo.
"""
import io
import json
from datetime import date

import pandas as pd
import streamlit as st

import nuvem as cloud
from nucleo import aplicar_estilo_comum, card, fmt_num
from rastreabilidade import classificar_rastreabilidade

st.set_page_config(page_title="Painel Online — Visualfil", page_icon="☁️", layout="wide")
aplicar_estilo_comum()

if not cloud.logado():
    st.warning("Faça login em **🔐 Entrar** para acessar o painel online.")
    st.stop()

st.title("☁️ Painel Online — Análise salva")
st.caption(
    "Os dados vêm dos XLSX enviados na **Administração → Demandas e XLSX**. "
    "Carregamento otimizado: pré-agregação → cache → lote."
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

forcar = st.button("🔄 Atualizar dados", help="Recalcula e salva nova pré-agregação.")
if forcar:
    cloud.cache_limpar(demanda_id)


# ============================ CARREGAMENTO OTIMIZADO ============================
def _calcular(ped_raw, est_raw, prod_raw, catalogo_df):
    """Devolve dict com tudo que a página exibe."""
    pedidos = (
        __import__("nucleo").preparar_pedidos(ped_raw)
        if ped_raw is not None else None
    )
    estoque = (
        __import__("nucleo").preparar_estoque(est_raw)
        if est_raw is not None else None
    )

    kb = pd.DataFrame()
    if pedidos is not None and estoque is not None and not pedidos.empty and not estoque.empty:
        codigos = __import__("nucleo").codigos_saldo2_negativo(estoque)
        ped = pedidos.copy()
        ped["_cod"] = ped["Cód Confec"].map(
            lambda v: str(int(float(v))) if str(v).replace(".", "", 1).isdigit() else str(v)
        )
        kb = ped[ped["_cod"].isin(codigos)].copy()

    if not kb.empty:
        kb["Prioridade"] = kb["Dt Entrega"].apply(
            lambda d: "Atrasado" if pd.notna(d) and d < pd.Timestamp(date.today()) else "Baixa"
        )
        kb["Classificação"] = (
            kb["Status"].map(classificar_rastreabilidade) if "Status" in kb.columns
            else "Sem classificação"
        )
        mapa_marca = {}
        if "Marca" in estoque.columns:
            for cod, marca in zip(
                estoque["Cód Confec"].map(
                    lambda v: str(int(float(v))) if str(v).replace(".", "", 1).isdigit() else str(v)
                ),
                estoque["Marca"],
            ):
                if cod and pd.notna(marca) and str(marca).strip():
                    mapa_marca[cod] = str(marca).strip()
        kb["Marca"] = kb["_cod"].map(mapa_marca).fillna("—")
        kb["Pedido"] = kb["Compra"].map(
            lambda v: int(float(v)) if str(v).replace(".", "", 1).isdigit() else str(v)
        )

    # ---------- compra sugerida ----------
    compra_itens = pd.DataFrame()
    compra_resumo = pd.DataFrame()
    total_compra = 0.0
    if estoque is not None and not estoque.empty and "Saldo 5" in estoque.columns:
        est = estoque.copy()
        saldo5 = pd.to_numeric(est["Saldo 5"], errors="coerce").fillna(0)
        neg = est[saldo5 < 0].copy()
        if not neg.empty:
            mapa_conf, mapa_item = {}, {}
            if not catalogo_df.empty and "codigo" in catalogo_df.columns:
                for _, r in catalogo_df.iterrows():
                    cod = str(r.get("codigo", "")).strip()
                    if not cod:
                        continue
                    conf = str(r.get("confeccao", "") or "").strip()
                    if conf:
                        mapa_conf[cod] = conf
                    item = str(r.get("item", "") or "").strip()
                    if item:
                        mapa_item[cod] = item
            neg["_cod"] = neg["Cód Confec"].map(
                lambda v: str(int(float(v))) if str(v).replace(".", "", 1).isdigit() else str(v)
            )
            neg["Confecção sugerida"] = neg["_cod"].map(mapa_conf).fillna("Sem confecção cadastrada")
            neg["Item"] = (
                neg["Descrição"].astype(str).str.strip()
                if "Descrição" in neg.columns else neg["_cod"].map(mapa_item).fillna("—")
            )
            tec = (
                pd.to_numeric(neg['Tec Faz "x" Confec'], errors="coerce").fillna(0)
                if 'Tec Faz "x" Confec' in neg.columns else 0
            )
            neg["Tec Faz x Confec"] = tec
            neg["Cons. Unitário"] = (
                pd.to_numeric(neg["Cons. Unitário"], errors="coerce").fillna(0)
                if "Cons. Unitário" in neg.columns else 0
            )
            neg["Base 1,1"] = (saldo5[neg.index].abs() * 1.10).round(0)
            neg["Compra sugerida"] = (neg["Base 1,1"] - tec).clip(lower=0).round()
            neg["Tecido necessário (m)"] = (
                neg["Compra sugerida"] * neg["Cons. Unitário"]
            ).round(2)
            neg["Saldo 5"] = saldo5[neg.index]

            colunas = ["_cod", "Item", "Marca", "Confecção sugerida", "Saldo 5",
                       "Tec Faz x Confec", "Cons. Unitário", "Base 1,1",
                       "Compra sugerida", "Tecido necessário (m)"]
            compra_itens = neg[[c for c in colunas if c in neg.columns]].rename(
                columns={"_cod": "Código"}
            ).sort_values("Compra sugerida", ascending=False)

            compra_resumo = (
                neg.groupby("Confecção sugerida", as_index=False)
                .agg(
                    Itens=("_cod", "count"),
                    **{"Saldo 5": ("Saldo 5", "sum")},
                    **{"Compra sugerida": ("Compra sugerida", "sum")},
                    **{"Tecido necessário (m)": ("Tecido necessário (m)", "sum")},
                )
                .sort_values("Compra sugerida", ascending=False)
            )
            total_compra = float(compra_resumo["Compra sugerida"].sum())

    # ---------- capacidade ----------
    capacidade = pd.DataFrame()
    if prod_raw is not None and not prod_raw.empty:
        col_conf = next((c for c in prod_raw.columns if "fornecedor" in str(c).lower()), None)
        col_qtd = next(
            (c for c in prod_raw.columns
             if "qtd" in str(c).lower() and "retorn" in str(c).lower()), None
        )
        if col_conf and col_qtd:
            p = prod_raw.copy()
            p["_qtd"] = pd.to_numeric(p[col_qtd], errors="coerce").fillna(0)
            capacidade = (
                p.groupby(col_conf)["_qtd"].sum().rename("Capacidade semanal")
                .reset_index().sort_values("Capacidade semanal", ascending=False)
            )
            compra_resumo = compra_resumo.merge(
                capacidade, left_on="Confecção sugerida", right_on=col_conf, how="left"
            ).drop(columns=[col_conf])
            compra_resumo["Semanas p/ absorver"] = (
                compra_resumo["Compra sugerida"]
                / compra_resumo["Capacidade semanal"].replace(0, pd.NA)
            ).round(1)

    return {
        "kb": kb, "compra_itens": compra_itens, "compra_resumo": compra_resumo,
        "total_compra": total_compra, "capacidade": capacidade,
    }


def _serializar(d: dict) -> dict:
    return {
        "kb": d["kb"].to_dict("records") if not d["kb"].empty else [],
        "compra_itens": d["compra_itens"].to_dict("records") if not d["compra_itens"].empty else [],
        "compra_resumo": d["compra_resumo"].to_dict("records") if not d["compra_resumo"].empty else [],
        "total_compra": d["total_compra"],
        "capacidade": d["capacidade"].to_dict("records") if not d["capacidade"].empty else [],
    }


def _desserializar(d: dict) -> dict:
    return {
        "kb": pd.DataFrame(d.get("kb", [])),
        "compra_itens": pd.DataFrame(d.get("compra_itens", [])),
        "compra_resumo": pd.DataFrame(d.get("compra_resumo", [])),
        "total_compra": float(d.get("total_compra", 0)),
        "capacidade": pd.DataFrame(d.get("capacidade", [])),
    }


try:
    catalogo_df = pd.DataFrame(cloud.catalogo())
except Exception:
    catalogo_df = pd.DataFrame()

modo_carregamento = ""
with st.status("Carregando dados otimizados…", expanded=False) as status:
    if not forcar and cloud.cache_validar(demanda_id):
        dados = _desserializar(cloud.cache_ler(demanda_id))
        modo_carregamento = "cache em memória ⚡"
        status.update(label="Cache local", state="complete")
    else:
        agregado = None
        try:
            resposta = cloud.agregado_ler(demanda_id)
            if resposta.get("ok") and resposta.get("dados"):
                agregado = resposta["dados"]
        except Exception:
            pass
        if agregado and not forcar:
            dados = _desserializar(agregado)
            modo_carregamento = "pré-agregação no servidor ⚡"
            status.update(label="Pré-agregação", state="complete")
        else:
            arquivos, erros, modo = cloud.arquivos_ler(
                demanda_id, ("pedidos", "estoque", "producao")
            )
            ped_raw = (
                pd.read_excel(io.BytesIO(arquivos["pedidos"]))
                if "pedidos" in arquivos else None
            )
            est_raw = (
                pd.read_excel(io.BytesIO(arquivos["estoque"]))
                if "estoque" in arquivos else None
            )
            prod_raw = (
                pd.read_excel(io.BytesIO(arquivos["producao"]))
                if "producao" in arquivos else None
            )
            dados = _calcular(ped_raw, est_raw, prod_raw, catalogo_df)
            cloud.cache_guardar(demanda_id, _serializar(dados))
            try:
                cloud.agregado_salvar(demanda_id, _serializar(dados))
            except Exception:
                pass
            modo_carregamento = f"{modo} (recalculado)"
            status.update(label=f"Carregado via {modo}", state="complete")
            if erros:
                st.caption("⚠️ " + "; ".join(f"{k}: {v}" for k, v in erros.items()))

kb = dados["kb"]
compra_itens = dados["compra_itens"]
compra_resumo = dados["compra_resumo"]
total_compra = dados["total_compra"]
capacidade = dados["capacidade"]

# garante DataFrames mesmo se vier algo inesperado do cache/JSON
if not isinstance(kb, pd.DataFrame):
    kb = pd.DataFrame(kb or [])
if not isinstance(compra_itens, pd.DataFrame):
    compra_itens = pd.DataFrame(compra_itens or [])
if not isinstance(compra_resumo, pd.DataFrame):
    compra_resumo = pd.DataFrame(compra_resumo or [])
if not isinstance(capacidade, pd.DataFrame):
    capacidade = pd.DataFrame(capacidade or [])

st.caption(f"🚀 Modo de carregamento: **{modo_carregamento}**")

if kb.empty and compra_itens.empty:
    st.warning("Esta demanda ainda não tem Pedidos ou Estoque processáveis.")
    st.stop()

# ============================ INDICADORES ============================
st.markdown("### 📊 Indicadores do quadro")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pedidos", fmt_num(len(kb)))
c2.metric("Unidades", fmt_num(kb["Saldo"].sum()) if "Saldo" in kb.columns else "—")
c3.metric("Confecções", fmt_num(kb["Confecção"].nunique()) if "Confecção" in kb.columns else "—")
c4.metric("Atrasados", fmt_num((kb["Prioridade"] == "Atrasado").sum()) if "Prioridade" in kb.columns else "—")

st.markdown("### 🧭 Pedidos (visão salva)")
if not kb.empty:
    colunas = [c for c in ("Pedido", "Cód Confec", "Confeccionado", "Confecção", "Marca",
                           "Qtd", "Saldo", "Dt Entrega", "Classificação", "Prioridade") if c in kb.columns]
    st.dataframe(kb[colunas], width="stretch", hide_index=True)
else:
    st.info("Sem pedidos no quadro desta demanda.")

# ============================ COMPRA SUGERIDA ============================
st.markdown("### 🛒 Compra sugerida por confecção")
st.caption("Regra: |Saldo 5| × 1,1 − Tec Faz 'x' Confec (mínimo zero).")

if compra_itens.empty:
    st.success("Nenhum item com Saldo 5 negativo — sem compra sugerida.")
else:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(card("Total compra sugerida", fmt_num(total_compra), "unidades", "#b71c1c"),
                    unsafe_allow_html=True)
    with k2:
        st.markdown(card("Itens com Saldo 5 negativo", fmt_num(len(compra_itens)), "códigos", "#ef6c00"),
                    unsafe_allow_html=True)
    with k3:
        st.markdown(card("Confecções", fmt_num(len(compra_resumo)), "com sugestão", "#3949ab"),
                    unsafe_allow_html=True)
    with k4:
        sem = int((compra_resumo["Confecção sugerida"] == "Sem confecção cadastrada").sum()) if not compra_resumo.empty else 0
        st.markdown(card("Sem confecção", fmt_num(sem), "cadastrar no catálogo", "#9e9e9e"),
                    unsafe_allow_html=True)

    st.markdown("#### 🔍 Detalhe por item")
    confs = sorted(compra_itens["Confecção sugerida"].unique().tolist())
    conf_sel = st.multiselect("Filtrar confecção (detalhe)", confs, default=confs, key="vf_compra_conf")
    detalhe = compra_itens[compra_itens["Confecção sugerida"].isin(conf_sel)] if conf_sel else compra_itens
    cfg_itens = {
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
    st.dataframe(detalhe[ordem].sort_values("Compra sugerida", ascending=False),
                 width="stretch", hide_index=True, height=360, column_config=cfg_itens)

    st.markdown("#### 📦 Resumo por confecção")
    cfg_resumo = {
        "Confecção sugerida": st.column_config.TextColumn("Confecção", width="large"),
        "Itens": st.column_config.NumberColumn("Itens", format="%d"),
        "Saldo 5": st.column_config.NumberColumn("Saldo 5", format="%.0f"),
        "Compra sugerida": st.column_config.NumberColumn("Compra sugerida", format="%.0f"),
        "Tecido necessário (m)": st.column_config.NumberColumn("Tecido (m)", format="%.2f"),
        "Capacidade semanal": st.column_config.NumberColumn("Capac./sem.", format="%.0f"),
        "Semanas p/ absorver": st.column_config.NumberColumn("Semanas", format="%.1f"),
    }
    st.dataframe(compra_resumo, width="stretch", hide_index=True, column_config=cfg_resumo)

    if st.button("💾 Salvar análise desta demanda", type="primary"):
        r = cloud.salvar_analise(
            demanda_id,
            f"Análise {date.today().strftime('%d/%m/%Y')}",
            {"resumo": compra_resumo.to_dict("records"),
             "itens": detalhe[ordem].to_dict("records"),
             "pedidos": int(len(kb)), "total_compra": total_compra},
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
