"""
Projeção Futura por Confecção
-----------------------------
Cruza três planilhas para planejar a produção por confecção:

    Produção por confecção.xlsx -> capacidade média semanal realizada
    Pedidos.xlsx                -> pedidos em aberto e rastreabilidade por status
    Estoque.xlsx                -> necessidade de compra (Saldo 5 negativo)

Classificação dos pedidos em aberto:

    Aguardando envio    -> ORÇAMENTO, EM SEPARAÇÃO, PEDIDO
    Aguardando produção -> PEDIDO C/ FORN
    Aguardando saldo    -> FAT. PARCIAL

A compra sugerida usa a mesma regra da Análise de Estoque
(``Saldo 5 < 0`` -> ``ceil(|Saldo 5| × 1,1)``, limitada por
``Tec Faz "x" Confec``) e é classificada pelo histórico da confecção:

    Já produziu -> a confecção já produziu o mesmo código de item;
    Semelhante  -> a confecção produziu item do mesmo tipo e com o mesmo
                   tamanho e/ou a mesma Operação Produtiva.
"""

import html
import io
import math
import unicodedata

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nucleo import (
    BUCKETS_RASTREABILIDADE,
    CORES_RASTREABILIDADE,
    aplicar_estilo_comum,
    cabecalho,
    card,
    classificar_rastreabilidade,
    extrair_tamanho,
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
    page_title="Projeção por Confecção",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_comum()

# ==================== ESTILO KANBAN (CHIPS E RESUMO) ====================

st.markdown(
    """
    <style>
        .pj-legend {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin: 0 0 1.25rem 0;
        }
        .pj-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--db-surface);
            border: 1px solid var(--db-border);
            color: var(--db-text);
            border-radius: 999px;
            padding: 0.4rem 1rem;
            font-size: 0.8rem;
            font-weight: 600;
            box-shadow: 0 1px 3px var(--db-shadow);
            transition: all 0.2s ease;
        }
        .pj-legend-item:hover {
            box-shadow: 0 4px 12px var(--db-shadow);
            border-color: rgba(99, 102, 241, 0.3);
        }
        .pj-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        .pj-dot.envio { background: #667eea; }
        .pj-dot.producao { background: #ef6c00; }
        .pj-dot.saldo { background: #2e7d32; }
        .pj-dot.ja { background: #2e7d32; }
        .pj-dot.semelhante { background: #ef6c00; }
        .pj-dot.semhistorico { background: #9e9e9e; }
        .pj-summary {
            background: linear-gradient(90deg, rgba(99, 102, 241, 0.08) 0%, transparent 100%);
            border: 1px solid var(--db-border);
            border-left: 3px solid #6366f1;
            border-radius: 12px;
            padding: 0.8rem 1.2rem;
            margin: 0.25rem 0 1rem 0;
            font-size: 0.875rem;
            color: var(--db-text-soft);
            font-weight: 500;
            line-height: 1.9;
        }
        .pj-summary b { color: var(--db-text); font-weight: 700; }
        .pj-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.2rem 0.65rem;
            font-size: 0.7rem;
            font-weight: 700;
            color: #ffffff;
            white-space: nowrap;
        }
        .pj-pill.ok { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }
        .pj-pill.muted { background: #64748b; }
    </style>
    """,
    unsafe_allow_html=True,
)

df_pedidos_raw, df_estoque_raw = sidebar_arquivos()

# ==================== UPLOAD DA PRODUÇÃO ====================

CHAVES_PRODUCAO = ("producao_conf_bytes", "producao_conf_nome")

with st.sidebar:
    st.markdown("---")
    st.header("🏭 Produção por confecção")
    nome_producao = st.session_state.get("producao_conf_nome")
    if nome_producao:
        st.markdown(
            f'<div class="db-file-ok">✅ <b>Produção por confecção</b>'
            f'<span class="db-file-name">{nome_producao}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 Trocar produção", key="pc_trocar_producao"):
            for chave in CHAVES_PRODUCAO:
                st.session_state.pop(chave, None)
            st.session_state.pop("producao_conf_df", None)
            st.rerun()
    else:
        upload_producao = st.file_uploader(
            "Arquivo **Produção por confecção** (.xlsx)",
            type=["xlsx", "xls"],
            key="pc_upload_producao",
            help=(
                "Histórico de retornos da confecção. Colunas usadas: Fornecedor, "
                "Dt Retorno, Cód Confec, Confeccionado, Qtd Retornada, Tipo Confec., "
                "Ope. Produtiva e Medida."
            ),
        )
        if upload_producao is not None:
            st.session_state["producao_conf_bytes"] = upload_producao.getvalue()
            st.session_state["producao_conf_nome"] = upload_producao.name
            st.rerun()

# ==================== CONSTANTES ====================

BUCKETS_ORDEM = BUCKETS_RASTREABILIDADE

CORES_BUCKET = CORES_RASTREABILIDADE

CORES_CATEGORIA = {
    "Já produziu": "#2e7d32",
    "Semelhante": "#ef6c00",
    "Sem histórico": "#9e9e9e",
}

TEC_COL = 'Tec Faz "x" Confec'


# ==================== NORMALIZAÇÃO ====================


def _norm(valor):
    """Maiúsculas, sem acentos e com espaços normalizados (chave de comparação)."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


def _texto_com_padrao(serie, padrao):
    """Texto limpo, trocando vazio por um rótulo padrão."""
    if serie is None:
        return pd.Series(dtype="object")
    texto = para_texto(serie).str.strip()
    return texto.where(texto != "", padrao)


def _coluna(df, nome):
    """Devolve a coluna ou uma série vazia, evitando KeyError em planilhas parciais."""
    if nome in df.columns:
        return df[nome]
    return pd.Series(np.nan, index=df.index)


def _periodo(inicio):
    """Rótulo da semana (segunda a domingo) a partir da data inicial."""
    if pd.isna(inicio):
        return "—"
    fim = pd.Timestamp(inicio) + pd.Timedelta(days=6)
    return f"{fmt_data(inicio)} a {fmt_data(fim)}"


# ==================== PREPARAÇÃO DOS DADOS ====================


def preparar_producao(df):
    """Normaliza o histórico de produção e descarta linhas totalizadoras."""
    if df is None:
        return None
    bruto = df.copy()

    producao = pd.DataFrame(index=bruto.index)
    producao["Fornecedor"] = para_texto(_coluna(bruto, "Fornecedor")).str.strip()
    producao["Dt Retorno"] = pd.to_datetime(
        _coluna(bruto, "Dt Retorno"), errors="coerce"
    )
    producao["Codigo"] = _coluna(bruto, "Cód Confec").map(normalizar_cod)
    producao["Item"] = para_texto(_coluna(bruto, "Confeccionado")).str.strip()
    producao["Qtd"] = pd.to_numeric(
        _coluna(bruto, "Qtd Retornada"), errors="coerce"
    ).fillna(0.0)
    producao["Tipo"] = _texto_com_padrao(
        _coluna(bruto, "Tipo Confec."), "Sem tipo"
    )
    producao["Operacao"] = _texto_com_padrao(
        _coluna(bruto, "Ope. Produtiva"), "Sem operação"
    )
    producao["Medida"] = para_texto(_coluna(bruto, "Medida")).str.strip()
    producao["Marca"] = _texto_com_padrao(_coluna(bruto, "Marca"), "Sem Marca")

    # A planilha traz uma linha de total geral (Fornecedor numérico, sem data e
    # sem código) que duplicaria a capacidade. Só entram retornos identificados.
    validos = (
        (producao["Fornecedor"] != "")
        & (producao["Codigo"] != "")
        & producao["Dt Retorno"].notna()
        & (producao["Qtd"] > 0)
    )
    producao = producao[validos].copy()

    if producao.empty:
        return producao

    producao["Semana"] = producao["Dt Retorno"].dt.to_period("W").dt.start_time
    producao["Tamanho"] = [
        extrair_tamanho(medida) if medida else extrair_tamanho(item)
        for medida, item in zip(producao["Medida"], producao["Item"])
    ]
    producao["FornecedorChave"] = producao["Fornecedor"].map(_norm)
    producao["TipoChave"] = producao["Tipo"].map(_norm)
    producao["OperacaoChave"] = producao["Operacao"].map(_norm)
    producao["TamanhoChave"] = producao["Tamanho"].map(_norm)
    return producao.reset_index(drop=True)


def resumo_capacidade(producao, semanas_janela):
    """Capacidade média semanal por confecção, opcionalmente nas últimas semanas."""
    vazio = pd.DataFrame(
        columns=[
            "Fornecedor",
            "Semanas",
            "ProducaoTotal",
            "CapacidadeSemanal",
            "MelhorSemana",
            "UltimaSemana",
            "Tipos",
        ]
    )
    if producao is None or producao.empty:
        return vazio

    semanas = sorted(producao["Semana"].dropna().unique())
    base = producao
    if semanas_janela and len(semanas) > semanas_janela:
        base = producao[producao["Semana"] >= semanas[-int(semanas_janela)]]

    semanal = (
        base.groupby(["Fornecedor", "Semana"], as_index=False)
        .agg(Qtd=("Qtd", "sum"), Itens=("Codigo", "nunique"))
        .reset_index(drop=True)
    )
    resumo = (
        semanal.groupby("Fornecedor", as_index=False)
        .agg(
            Semanas=("Semana", "nunique"),
            ProducaoTotal=("Qtd", "sum"),
            CapacidadeSemanal=("Qtd", "mean"),
            MelhorSemana=("Qtd", "max"),
            UltimaSemana=("Semana", "max"),
            Itens=("Itens", "sum"),
        )
        .reset_index(drop=True)
    )

    tipos = (
        base.groupby("Fornecedor")["Tipo"]
        .apply(lambda serie: ", ".join(sorted({str(v) for v in serie if str(v).strip()})))
        .rename("Tipos")
    )
    resumo = resumo.merge(tipos, on="Fornecedor", how="left")
    resumo["Tipos"] = resumo["Tipos"].fillna("—")
    resumo["FornecedorChave"] = resumo["Fornecedor"].map(_norm)
    return resumo.sort_values("CapacidadeSemanal", ascending=False).reset_index(drop=True)


def preparar_pedidos_pagina(df):
    """Pedidos preparados + classificação de rastreabilidade e saldo em aberto."""
    if df is None:
        return None
    pedidos = preparar_pedidos(df)
    pedidos = pedidos.copy()

    pedidos["QtdRet"] = pd.to_numeric(
        _coluna(pedidos, "Qtd Ret"), errors="coerce"
    ).fillna(0.0)
    pedidos["SaldoAberto"] = (
        pd.to_numeric(_coluna(pedidos, "Saldo"), errors="coerce")
        .fillna(0.0)
        .clip(lower=0)
    )
    pedidos["Classificacao"] = pedidos["Status"].map(
        classificar_rastreabilidade
    )
    pedidos["Tipo"] = _texto_com_padrao(
        _coluna(pedidos, "Tipo do Confeccionado"), "Sem tipo"
    )
    pedidos["Operacao"] = _texto_com_padrao(
        _coluna(pedidos, "Ope. produtiva"), "Sem operação"
    )
    pedidos["Tamanho"] = pedidos["Confeccionado"].map(extrair_tamanho)
    pedidos["ConfecaoChave"] = pedidos["Confecção"].map(_norm)
    pedidos["TipoChave"] = pedidos["Tipo"].map(_norm)
    pedidos["OperacaoChave"] = pedidos["Operacao"].map(_norm)
    return pedidos


def preparar_compra(df):
    """Estoque preparado + compra sugerida (Saldo 5 negativo)."""
    if df is None:
        return None
    estoque = preparar_estoque(df)
    estoque = estoque.copy()

    estoque["Codigo"] = estoque["Cód Confec_norm"]
    estoque["Tamanho"] = estoque["Descrição"].map(extrair_tamanho)
    estoque["Tipo"] = _texto_com_padrao(
        _coluna(estoque, "Tipo Produto"), "Sem tipo"
    )
    estoque["Operacao"] = _texto_com_padrao(
        _coluna(estoque, "Operação Produtiva"), "Sem operação"
    )
    estoque["Saldo 5"] = pd.to_numeric(
        _coluna(estoque, "Saldo 5"), errors="coerce"
    )
    estoque["Teto"] = pd.to_numeric(_coluna(estoque, TEC_COL), errors="coerce")

    def calcular_sugestao(row):
        saldo5 = row.get("Saldo 5")
        if pd.isna(saldo5) or float(saldo5) >= 0:
            return 0
        sugerida = math.ceil(abs(float(saldo5)) * 1.1)
        teto = row.get("Teto")
        if pd.notna(teto) and float(teto) >= 0:
            sugerida = min(sugerida, float(teto))
        return int(max(0, math.floor(sugerida)))

    estoque["Compra Sugerida"] = estoque.apply(calcular_sugestao, axis=1)
    return estoque


def montar_historico(producao, pedidos):
    """Histórico combinado de itens já produzidos (produção + Qtd Ret > 0)."""
    colunas = [
        "Fornecedor",
        "Codigo",
        "Item",
        "Tipo",
        "Operacao",
        "Tamanho",
        "Qtd",
        "Origem",
    ]
    partes = []

    if producao is not None and not producao.empty:
        partes.append(
            producao[
                ["Fornecedor", "Codigo", "Item", "Tipo", "Operacao", "Tamanho", "Qtd"]
            ].assign(Origem="Produção")
        )

    if pedidos is not None and not pedidos.empty:
        retornados = pedidos[pedidos["QtdRet"] > 0]
        if not retornados.empty:
            partes.append(
                pd.DataFrame(
                    {
                        "Fornecedor": retornados["Confecção"],
                        "Codigo": retornados["Cód Confec"],
                        "Item": retornados["Confeccionado"],
                        "Tipo": retornados["Tipo"],
                        "Operacao": retornados["Operacao"],
                        "Tamanho": retornados["Tamanho"],
                        "Qtd": retornados["QtdRet"],
                        "Origem": "Pedidos (Qtd Ret > 0)",
                    }
                )
            )

    if not partes:
        return pd.DataFrame(columns=colunas)

    historico = pd.concat(partes, ignore_index=True)
    historico["Fornecedor"] = para_texto(historico["Fornecedor"]).str.strip()
    historico["Codigo"] = historico["Codigo"].map(normalizar_cod)
    historico["Qtd"] = pd.to_numeric(historico["Qtd"], errors="coerce").fillna(0.0)
    for coluna in ("Item", "Tipo", "Operacao", "Tamanho"):
        historico[coluna] = para_texto(historico[coluna]).str.strip()

    historico = historico[
        (historico["Fornecedor"] != "")
        & (historico["Codigo"] != "")
        & (historico["Qtd"] > 0)
    ].copy()

    historico["FornecedorChave"] = historico["Fornecedor"].map(_norm)
    historico["TipoChave"] = historico["Tipo"].map(_norm)
    historico["OperacaoChave"] = historico["Operacao"].map(_norm)
    historico["TamanhoChave"] = historico["Tamanho"].map(_norm)
    return historico.reset_index(drop=True)


def classificar_compra(estoque, historico, capacidades):
    """Classifica cada compra sugerida como 'Já produziu' ou 'Semelhante'.

    Devolve ``(compra, detalhe)``: a compra com a melhor confecção sugerida e o
    detalhe de todas as confecções compatíveis com cada item.
    """
    if estoque is None or estoque.empty:
        return pd.DataFrame(), pd.DataFrame()

    alvo = estoque[estoque["Compra Sugerida"] > 0].copy()
    if alvo.empty:
        return alvo, pd.DataFrame()

    cap_map = {}
    if capacidades is not None and not capacidades.empty:
        cap_map = dict(
            zip(capacidades["FornecedorChave"], capacidades["CapacidadeSemanal"])
        )

    linhas = []
    detalhes = []

    for _, item in alvo.iterrows():
        codigo = str(item.get("Codigo") or "").strip()
        tipo_chave = _norm(item.get("Tipo"))
        tamanho_chave = _norm(item.get("Tamanho"))
        operacao_chave = _norm(item.get("Operacao"))

        candidatos = []
        if historico is not None and not historico.empty:
            exatos = historico[historico["Codigo"] == codigo]
            for confeccao, grupo in exatos.groupby("Fornecedor"):
                candidatos.append(
                    {
                        "Confecção": confeccao,
                        "Categoria": "Já produziu",
                        "Score": 3,
                        "Motivo": "Código já produzido por esta confecção",
                        "Qtd histórico": float(grupo["Qtd"].sum()),
                        "Origem": ", ".join(sorted(set(grupo["Origem"]))),
                    }
                )

            confeccoes_exatas = {c["Confecção"] for c in candidatos}
            base = (
                historico[historico["TipoChave"] == tipo_chave]
                if tipo_chave
                else historico.iloc[0:0]
            )
            for confeccao, grupo in base.groupby("Fornecedor"):
                if confeccao in confeccoes_exatas:
                    continue
                mesma_medida = tamanho_chave not in (
                    "",
                    "SEM TAMANHO",
                ) and bool((grupo["TamanhoChave"] == tamanho_chave).any())
                mesma_operacao = operacao_chave not in (
                    "",
                    "SEM OPERACAO",
                ) and bool((grupo["OperacaoChave"] == operacao_chave).any())
                if not (mesma_medida or mesma_operacao):
                    continue
                if mesma_medida and mesma_operacao:
                    score, motivo = 2, "Mesmo tipo + mesmo tamanho + mesma operação"
                elif mesma_medida:
                    score, motivo = 1, "Mesmo tipo + mesmo tamanho"
                else:
                    score, motivo = 1, "Mesmo tipo + mesma operação"
                candidatos.append(
                    {
                        "Confecção": confeccao,
                        "Categoria": "Semelhante",
                        "Score": score,
                        "Motivo": motivo,
                        "Qtd histórico": float(grupo["Qtd"].sum()),
                        "Origem": ", ".join(sorted(set(grupo["Origem"]))),
                    }
                )

        candidatos.sort(
            key=lambda c: (
                -c["Score"],
                -float(cap_map.get(_norm(c["Confecção"]), 0) or 0),
                -c["Qtd histórico"],
            )
        )

        melhor = candidatos[0] if candidatos else None
        for candidato in candidatos:
            detalhes.append(
                {
                    "Código": codigo,
                    "Descrição": item.get("Descrição", ""),
                    "Tamanho": item.get("Tamanho", ""),
                    "Tipo": item.get("Tipo", ""),
                    "Operação": item.get("Operacao", ""),
                    "Compra Sugerida": int(item["Compra Sugerida"]),
                    **candidato,
                    "Capacidade semanal": cap_map.get(
                        _norm(candidato["Confecção"]), np.nan
                    ),
                }
            )

        capacidade = (
            cap_map.get(_norm(melhor["Confecção"]), np.nan) if melhor else np.nan
        )
        sugestao = int(item["Compra Sugerida"])
        semanas = (
            math.ceil(sugestao / float(capacidade))
            if pd.notna(capacidade) and float(capacidade) > 0
            else np.nan
        )

        linhas.append(
            {
                "Marca": item.get("Marca", ""),
                "Código": codigo,
                "Descrição": item.get("Descrição", ""),
                "Tamanho": item.get("Tamanho", ""),
                "Tipo": item.get("Tipo", ""),
                "Operação": item.get("Operacao", ""),
                "Saldo 5": item.get("Saldo 5", np.nan),
                "Teto": item.get("Teto", np.nan),
                "Compra Sugerida": sugestao,
                "Categoria": melhor["Categoria"] if melhor else "Sem histórico",
                "Confecção sugerida": melhor["Confecção"] if melhor else "—",
                "Motivo": (
                    melhor["Motivo"]
                    if melhor
                    else "Nenhuma confecção com histórico compatível"
                ),
                "Capacidade semanal": capacidade,
                "Semanas estimadas": semanas,
                "Confecções compatíveis": len(candidatos),
            }
        )

    compra = pd.DataFrame(linhas)
    detalhe = pd.DataFrame(detalhes)
    ordem_categoria = {"Já produziu": 0, "Semelhante": 1, "Sem histórico": 2}
    compra["_ordem"] = compra["Categoria"].map(ordem_categoria).fillna(3)
    compra = compra.sort_values(
        ["_ordem", "Compra Sugerida"], ascending=[True, False]
    ).drop(columns="_ordem")
    return compra.reset_index(drop=True), detalhe


def resumo_pedidos(pedidos):
    """Saldo em aberto por confecção e por classificação de rastreabilidade."""
    vazio = pd.DataFrame(
        columns=[
            "Confecção",
            "Pedidos abertos",
            "Saldo aberto",
            *BUCKETS_ORDEM,
        ]
    )
    if pedidos is None or pedidos.empty:
        return vazio

    abertos = pedidos[pedidos["SaldoAberto"] > 0]
    if abertos.empty:
        return vazio

    base = (
        abertos.groupby("Confecção", as_index=False)
        .agg(
            Pedidos=("Compra", "nunique"),
            Saldo=("SaldoAberto", "sum"),
        )
        .reset_index(drop=True)
    )
    pivot = abertos.pivot_table(
        index="Confecção",
        columns="Classificacao",
        values="SaldoAberto",
        aggfunc="sum",
        fill_value=0,
    )
    for bucket in BUCKETS_ORDEM:
        if bucket not in pivot.columns:
            pivot[bucket] = 0.0
    pivot = pivot[list(BUCKETS_ORDEM)].reset_index()

    resumo = base.merge(pivot, on="Confecção", how="left").fillna(0)
    resumo = resumo.rename(
        columns={"Pedidos": "Pedidos abertos", "Saldo": "Saldo aberto"}
    )
    resumo["ConfecaoChave"] = resumo["Confecção"].map(_norm)
    return resumo.sort_values("Saldo aberto", ascending=False).reset_index(drop=True)


def montar_consolidado(capacidades, pedidos_resumo, compra):
    """Visão única por confecção: capacidade, pedidos abertos e compra atribuída."""
    nomes = {}
    if capacidades is not None and not capacidades.empty:
        for nome in capacidades["Fornecedor"]:
            chave = _norm(nome)
            if chave:
                nomes.setdefault(chave, nome)
    if pedidos_resumo is not None and not pedidos_resumo.empty:
        for nome in pedidos_resumo["Confecção"]:
            chave = _norm(nome)
            if chave:
                nomes.setdefault(chave, nome)

    compra_atribuida = {}
    if compra is not None and not compra.empty:
        atribuida = compra[compra["Confecção sugerida"] != "—"]
        for nome, grupo in atribuida.groupby("Confecção sugerida"):
            compra_atribuida[_norm(nome)] = {
                "CompraAtribuida": float(grupo["Compra Sugerida"].sum()),
                "ItensSugeridos": len(grupo),
            }

    linhas = []
    for chave, nome in nomes.items():
        linha = {
            "Confecção": nome,
            "Capacidade semanal": np.nan,
            "Semanas observadas": 0,
            "Produção no período": 0.0,
            "Pedidos abertos": 0,
            "Saldo aberto": 0.0,
            "Aguardando envio": 0.0,
            "Aguardando produção": 0.0,
            "Aguardando saldo": 0.0,
            "Compra atribuída": 0.0,
            "Itens sugeridos": 0,
        }

        if capacidades is not None and not capacidades.empty:
            achado = capacidades[capacidades["FornecedorChave"] == chave]
            if not achado.empty:
                registro = achado.iloc[0]
                linha["Capacidade semanal"] = registro["CapacidadeSemanal"]
                linha["Semanas observadas"] = int(registro["Semanas"])
                linha["Produção no período"] = float(registro["ProducaoTotal"])

        if pedidos_resumo is not None and not pedidos_resumo.empty:
            achado = pedidos_resumo[pedidos_resumo["ConfecaoChave"] == chave]
            if not achado.empty:
                registro = achado.iloc[0]
                linha["Pedidos abertos"] = int(registro["Pedidos abertos"])
                linha["Saldo aberto"] = float(registro["Saldo aberto"])
                for bucket in BUCKETS_ORDEM:
                    linha[bucket] = float(registro[bucket])

        if chave in compra_atribuida:
            linha["Compra atribuída"] = compra_atribuida[chave]["CompraAtribuida"]
            linha["Itens sugeridos"] = compra_atribuida[chave]["ItensSugeridos"]

        linhas.append(linha)

    consolidado = pd.DataFrame(linhas)
    if consolidado.empty:
        return consolidado

    capacidade = pd.to_numeric(consolidado["Capacidade semanal"], errors="coerce")
    demanda = consolidado["Saldo aberto"] + consolidado["Compra atribuída"]
    consolidado["Semanas p/ absorver"] = np.where(
        capacidade > 0, np.ceil(demanda / capacidade), np.nan
    )
    consolidado["Com histórico"] = np.where(capacidade > 0, "Sim", "Não")
    return consolidado.sort_values(
        ["Saldo aberto", "Capacidade semanal"], ascending=[False, False]
    ).reset_index(drop=True)


# ==================== LEITURA ====================

dados_producao = st.session_state.get("producao_conf_bytes")

cabecalho(
    "🏭 Projeção Futura por Confecção",
    "Capacidade semanal realizada × pedidos em aberto × compra sugerida — "
    f"referência: {pd.Timestamp.today().strftime('%d/%m/%Y')}",
)

st.markdown(
    """
    <div class="pj-legend">
        <span class="pj-legend-item"><span class="pj-dot envio"></span> Aguardando envio</span>
        <span class="pj-legend-item"><span class="pj-dot producao"></span> Aguardando produção</span>
        <span class="pj-legend-item"><span class="pj-dot saldo"></span> Aguardando saldo</span>
        <span class="pj-legend-item"><span class="pj-dot ja"></span> Já produziu</span>
        <span class="pj-legend-item"><span class="pj-dot semelhante"></span> Semelhante</span>
        <span class="pj-legend-item"><span class="pj-dot semhistorico"></span> Sem histórico</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if not dados_producao:
    st.info(
        "👆 Envie a planilha **Produção por confecção.xlsx** na barra lateral. "
        "Os arquivos de **Pedidos** e **Estoque** já enviados no sistema são reaproveitados."
    )
    st.stop()

try:
    producao_bruta = load_excel(dados_producao)
except Exception as erro:  # noqa: BLE001
    st.error(f"Não foi possível ler a planilha de produção: {erro}")
    st.stop()

producao = preparar_producao(producao_bruta)
if producao is None or producao.empty:
    st.warning(
        "A planilha de produção não tem retornos válidos (Fornecedor, Dt Retorno, "
        "Cód Confec e Qtd Retornada preenchidos)."
    )
    st.stop()

pedidos = preparar_pedidos_pagina(df_pedidos_raw)
estoque = preparar_compra(df_estoque_raw)

if pedidos is None:
    st.warning(
        "Envie o arquivo de **Pedidos** na barra lateral para ver a rastreabilidade "
        "dos pedidos em aberto por confecção."
    )
if estoque is None:
    st.warning(
        "Envie o arquivo de **Estoque** na barra lateral para calcular a compra sugerida."
    )

# ==================== FILTROS ====================

semanas_disponiveis = int(producao["Semana"].nunique())

with st.sidebar:
    st.markdown("---")
    st.header("🔍 Filtros")

    semanas_janela = st.number_input(
        "Janela da média (últimas semanas)",
        min_value=1,
        max_value=52,
        value=max(1, min(8, semanas_disponiveis)),
        step=1,
        key="pc_semanas_janela",
        help=(
            "A capacidade média usa apenas as últimas N semanas observadas no "
            f"arquivo. O arquivo atual tem {semanas_disponiveis} semana(s)."
        ),
    )

    nomes_confeccoes = set()
    if not producao.empty:
        nomes_confeccoes.update(producao["Fornecedor"].dropna().tolist())
    if pedidos is not None and not pedidos.empty:
        nomes_confeccoes.update(pedidos["Confecção"].dropna().tolist())
    opcoes_confeccoes = sorted(
        (nome for nome in nomes_confeccoes if str(nome).strip()),
        key=lambda nome: _norm(nome),
    )
    confeccoes_sel = st.multiselect(
        "Confecções",
        options=opcoes_confeccoes,
        default=opcoes_confeccoes,
        key="pc_confeccoes",
    )

    categorias_sel = st.multiselect(
        "Categoria da compra sugerida",
        options=["Já produziu", "Semelhante", "Sem histórico"],
        default=["Já produziu", "Semelhante", "Sem histórico"],
        key="pc_categorias",
    )

    top_n = st.slider(
        "Top N nos gráficos",
        min_value=5,
        max_value=40,
        value=20,
        step=1,
        key="pc_top_n",
    )
    somente_com_aberto = st.checkbox(
        "Somente confecções com pedidos em aberto",
        value=False,
        key="pc_somente_aberto",
    )

# ==================== CAPACIDADE ====================

capacidades = resumo_capacidade(producao, semanas_janela)
pedidos_resumo = resumo_pedidos(pedidos)
historico = montar_historico(producao, pedidos)
compra, detalhe_compra = classificar_compra(estoque, historico, capacidades)
consolidado = montar_consolidado(capacidades, pedidos_resumo, compra)

# ==================== KPIs ====================

consolidado_escopo = (
    consolidado[consolidado["Confecção"].isin(confeccoes_sel)].copy()
    if not consolidado.empty
    else consolidado
)
total_capacidade = (
    float(consolidado_escopo["Capacidade semanal"].sum())
    if not consolidado_escopo.empty
    else 0.0
)
total_aberto = (
    float(consolidado_escopo["Saldo aberto"].sum())
    if not consolidado_escopo.empty
    else 0.0
)
compra_escopo = (
    compra[
        compra["Categoria"].isin(categorias_sel)
        & (
            compra["Confecção sugerida"].isin(confeccoes_sel)
            | (compra["Confecção sugerida"] == "—")
        )
    ]
    if not compra.empty
    else compra
)
total_compra = (
    float(compra_escopo["Compra Sugerida"].sum()) if not compra_escopo.empty else 0.0
)
n_confeccoes = len(confeccoes_sel)
n_sem_historico = (
    int(
        (
            (consolidado_escopo["Com histórico"] == "Não")
            & (consolidado_escopo["Saldo aberto"] > 0)
        ).sum()
    )
    if not consolidado_escopo.empty
    else 0
)
demanda_total = total_aberto + total_compra
semanas_globais = (
    math.ceil(demanda_total / total_capacidade) if total_capacidade > 0 else None
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    st.markdown(
        card(
            "Confecções",
            fmt_num(n_confeccoes),
            f"{fmt_num(len(capacidades[capacidades['Fornecedor'].isin(confeccoes_sel)]))} com histórico de produção",
            "#667eea",
        ),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        card(
            "Capacidade semanal",
            fmt_num(total_capacidade),
            f"média das últimas {min(semanas_janela, semanas_disponiveis)} semana(s)",
            "#2e7d32",
        ),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        card(
            "Pedidos em aberto",
            fmt_num(total_aberto),
            "soma do Saldo dos pedidos",
            "#ef6c00",
        ),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        card(
            "Compra sugerida",
            fmt_num(total_compra),
            "Saldo 5 negativo × 1,1",
            "#b71c1c",
        ),
        unsafe_allow_html=True,
    )
with k5:
    st.markdown(
        card(
            "Semanas p/ absorver",
            fmt_num(semanas_globais) if semanas_globais is not None else "—",
            "pedidos abertos + compra sugerida",
            "#764ba2",
        ),
        unsafe_allow_html=True,
    )
with k6:
    st.markdown(
        card(
            "Sem histórico",
            fmt_num(n_sem_historico),
            "confecções com pedidos e sem produção",
            "#9e9e9e",
        ),
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='db-aviso'>📈 A capacidade semanal é a <b>média das semanas "
    f"observadas</b> no arquivo de produção ({semanas_disponiveis} semana(s)), "
    "considerando a janela escolhida na barra lateral. Pedidos com "
    "<b>Saldo &gt; 0</b> entram na rastreabilidade; a compra sugerida segue a "
    'regra <code>|Saldo 5| × 1,1</code> limitada por <code>Tec Faz "x" Confec</code>.</div>',
    unsafe_allow_html=True,
)

# ==================== 1. FICHA DA CONFECÇÃO ====================

st.markdown(
    '<div class="db-secao">🪪 Ficha de indicadores por confecção</div>',
    unsafe_allow_html=True,
)

# Ordena as opções pelo saldo em aberto para abrir na confecção mais crítica.
saldo_por_confeccao = (
    dict(zip(consolidado["Confecção"], consolidado["Saldo aberto"]))
    if not consolidado.empty
    else {}
)
opcoes_ficha = list(confeccoes_sel)
if somente_com_aberto:
    opcoes_ficha = [
        nome for nome in opcoes_ficha if saldo_por_confeccao.get(nome, 0) > 0
    ]
opcoes_ficha = sorted(
    opcoes_ficha,
    key=lambda nome: (-float(saldo_por_confeccao.get(nome, 0) or 0), _norm(nome)),
)

if not opcoes_ficha:
    st.info("Nenhuma confecção disponível com os filtros atuais.")
else:
    confeccao_ficha = st.selectbox(
        "Escolha a confecção",
        options=opcoes_ficha,
        key="pc_ficha_confeccao",
        help=(
            "Reúne capacidade, pedidos em aberto, compra sugerida e histórico "
            "de itens já produzidos por esta confecção."
        ),
    )

    chave_ficha = _norm(confeccao_ficha)
    registro = consolidado[consolidado["Confecção"] == confeccao_ficha]
    registro = registro.iloc[0] if not registro.empty else None
    cap_ficha = capacidades[capacidades["FornecedorChave"] == chave_ficha]
    cap_ficha = cap_ficha.iloc[0] if not cap_ficha.empty else None
    historico_ficha = (
        historico[historico["FornecedorChave"] == chave_ficha].copy()
        if historico is not None and not historico.empty
        else pd.DataFrame()
    )

    if registro is None:
        st.info("Sem indicadores consolidados para esta confecção.")
    else:
        capacidade_ficha = registro["Capacidade semanal"]
        tem_historico = (
            pd.notna(capacidade_ficha) and float(capacidade_ficha) > 0
        )
        n_itens_historico = (
            int(historico_ficha["Codigo"].nunique())
            if not historico_ficha.empty
            else 0
        )

        semanas_ficha = registro["Semanas p/ absorver"]
        status_html = (
            '<span class="pj-pill ok">🟢 com histórico</span>'
            if tem_historico
            else '<span class="pj-pill muted">⚪ sem histórico</span>'
        )
        st.markdown(
            f"""
            <div class="pj-summary">
                🏭 <b>{html.escape(str(confeccao_ficha))}</b> &nbsp;·&nbsp; {status_html} &nbsp;·&nbsp;
                ⚡ Capacidade <b>{fmt_num(capacidade_ficha)}</b> un./semana &nbsp;·&nbsp;
                📦 Em aberto <b>{fmt_num(registro["Saldo aberto"])}</b> un. &nbsp;·&nbsp;
                🛒 Compra <b>{fmt_num(registro["Compra atribuída"])}</b> un. &nbsp;·&nbsp;
                ⏳ <b>{fmt_num(semanas_ficha) if pd.notna(semanas_ficha) else "—"}</b> semana(s)
            </div>
            """,
            unsafe_allow_html=True,
        )

        e1, e2, e3, e4 = st.columns(4)
        with e1:
            st.markdown(
                card(
                    "Capacidade semanal",
                    fmt_num(capacidade_ficha),
                    (
                        f"média de {int(registro['Semanas observadas'])} semana(s)"
                        if tem_historico
                        else "sem produção registrada"
                    ),
                    "#2e7d32",
                ),
                unsafe_allow_html=True,
            )
        with e2:
            st.markdown(
                card(
                    "Pedidos em aberto",
                    fmt_num(registro["Saldo aberto"]),
                    f"{fmt_num(registro['Pedidos abertos'])} pedido(s)",
                    "#ef6c00",
                ),
                unsafe_allow_html=True,
            )
        with e3:
            st.markdown(
                card(
                    "Compra sugerida atribuída",
                    fmt_num(registro["Compra atribuída"]),
                    f"{fmt_num(registro['Itens sugeridos'])} item(ns)",
                    "#b71c1c",
                ),
                unsafe_allow_html=True,
            )
        with e4:
            st.markdown(
                card(
                    "Semanas p/ absorver",
                    (
                        fmt_num(semanas_ficha)
                        if pd.notna(semanas_ficha)
                        else "—"
                    ),
                    "pedidos abertos + compra atribuída",
                    "#764ba2",
                ),
                unsafe_allow_html=True,
            )

        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.markdown(
                card(
                    "Produção no período",
                    fmt_num(registro["Produção no período"]),
                    "soma dos retornos do arquivo",
                    "#3949ab",
                ),
                unsafe_allow_html=True,
            )
        with p2:
            melhor = cap_ficha["MelhorSemana"] if cap_ficha is not None else np.nan
            st.markdown(
                card(
                    "Melhor semana",
                    fmt_num(melhor),
                    "maior volume semanal",
                    "#00897b",
                ),
                unsafe_allow_html=True,
            )
        with p3:
            ultima = (
                _periodo(cap_ficha["UltimaSemana"])
                if cap_ficha is not None
                else "—"
            )
            st.markdown(
                card(
                    "Última semana",
                    ultima,
                    "semana mais recente",
                    "#5e35b1",
                ),
                unsafe_allow_html=True,
            )
        with p4:
            st.markdown(
                card(
                    "Itens no histórico",
                    fmt_num(n_itens_historico),
                    "códigos já produzidos",
                    "#546e7a",
                ),
                unsafe_allow_html=True,
            )

        if cap_ficha is not None:
            st.caption(f"**Tipos produzidos:** {cap_ficha['Tipos']}")

        g1, g2 = st.columns([1.4, 1])
        with g1:
            semanal_ficha = (
                producao[producao["FornecedorChave"] == chave_ficha]
                .groupby("Semana", as_index=False)
                .agg(Qtd=("Qtd", "sum"), Itens=("Codigo", "nunique"))
                .sort_values("Semana")
            )
            if semanal_ficha.empty:
                st.info(
                    "Sem produção registrada para esta confecção no arquivo atual."
                )
            else:
                semanal_ficha["Rotulo"] = semanal_ficha["Semana"].map(fmt_data)
                fig = px.bar(
                    semanal_ficha,
                    x="Rotulo",
                    y="Qtd",
                    text="Qtd",
                    labels={"Rotulo": "", "Qtd": "Unidades produzidas"},
                    title="Produção por semana",
                    template=template_plotly(),
                )
                fig.update_traces(
                    texttemplate="%{text:,.0f}",
                    textposition="outside",
                    marker_color="#3949ab",
                )
                if tem_historico:
                    fig.add_hline(
                        y=float(capacidade_ficha),
                        line_dash="dot",
                        line_color="#2e7d32",
                        annotation_text="Média semanal",
                        annotation_position="top left",
                    )
                fig.update_layout(
                    height=360,
                    showlegend=False,
                    margin=dict(t=55, l=10, r=10, b=10),
                )
                st.plotly_chart(fig, width="stretch")

        with g2:
            dados_bucket = pd.DataFrame(
                {
                    "Classificação": list(BUCKETS_ORDEM),
                    "Unidades": [
                        float(registro[bucket]) for bucket in BUCKETS_ORDEM
                    ],
                }
            )
            total_buckets = float(dados_bucket["Unidades"].sum())
            if total_buckets <= 0:
                st.info("Sem pedidos em aberto para esta confecção.")
            else:
                fig = px.bar(
                    dados_bucket,
                    x="Unidades",
                    y="Classificação",
                    orientation="h",
                    color="Classificação",
                    color_discrete_map=CORES_BUCKET,
                    text="Unidades",
                    title="Pedidos em aberto por classificação",
                    template=template_plotly(),
                )
                fig.update_traces(
                    texttemplate="%{text:,.0f}", textposition="outside"
                )
                fig.update_layout(
                    height=360,
                    showlegend=False,
                    margin=dict(t=55, l=10, r=10, b=10),
                    xaxis_title="Unidades",
                    yaxis_title="",
                )
                st.plotly_chart(fig, width="stretch")

        pedidos_ficha = pd.DataFrame()
        if pedidos is not None and not pedidos.empty:
            pedidos_ficha = pedidos[
                (pedidos["Confecção"] == confeccao_ficha)
                & (pedidos["SaldoAberto"] > 0)
            ].copy()

        compra_ficha = (
            compra[compra["Confecção sugerida"] == confeccao_ficha].copy()
            if compra is not None and not compra.empty
            else pd.DataFrame()
        )

        aba_pedidos, aba_compra, aba_historico = st.tabs(
            [
                f"📋 Pedidos em aberto ({len(pedidos_ficha)})",
                f"🛒 Compra sugerida ({len(compra_ficha)})",
                f"🧵 Itens já produzidos ({n_itens_historico})",
            ]
        )

        with aba_pedidos:
            if pedidos_ficha.empty:
                st.caption(
                    "Nenhum pedido com saldo em aberto para esta confecção."
                )
            else:
                detalhe_ficha = pedidos_ficha.sort_values(
                    ["Dt Entrega", "SaldoAberto"],
                    ascending=[True, False],
                    na_position="last",
                ).copy()
                detalhe_ficha["Retorno %"] = (
                    detalhe_ficha["QtdRet"]
                    / detalhe_ficha["Qtd"].where(detalhe_ficha["Qtd"] > 0)
                    * 100
                ).fillna(0).clip(0, 100)
                st.dataframe(
                    detalhe_ficha[
                        [
                            coluna
                            for coluna in (
                                "Compra",
                                "Status",
                                "Classificacao",
                                "Cód Confec",
                                "Confeccionado",
                                "Qtd",
                                "QtdRet",
                                "Retorno %",
                                "SaldoAberto",
                                "Dt Entrega",
                            )
                            if coluna in detalhe_ficha.columns
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Compra": st.column_config.TextColumn(
                            "Pedido", width="small"
                        ),
                        "Status": st.column_config.TextColumn(
                            "Status", width="small"
                        ),
                        "Classificacao": st.column_config.TextColumn(
                            "Classificação", width="small"
                        ),
                        "Cód Confec": st.column_config.TextColumn(
                            "Código", width="small"
                        ),
                        "Confeccionado": st.column_config.TextColumn(
                            "Item", width="large"
                        ),
                        "Qtd": st.column_config.NumberColumn(
                            "Qtd", format="%d"
                        ),
                        "QtdRet": st.column_config.NumberColumn(
                            "Qtd retornada", format="%d"
                        ),
                        "Retorno %": st.column_config.ProgressColumn(
                            "Retorno",
                            min_value=0,
                            max_value=100,
                            format="%d%%",
                        ),
                        "SaldoAberto": st.column_config.NumberColumn(
                            "Saldo em aberto", format="%d"
                        ),
                        "Dt Entrega": st.column_config.DateColumn(
                            "Dt Entrega", format="DD/MM/YYYY"
                        ),
                    },
                )

        with aba_compra:
            if compra_ficha.empty:
                st.caption(
                    "Nenhum item de compra sugerida atribuído a esta confecção."
                )
            else:
                st.dataframe(
                    compra_ficha[
                        [
                            "Categoria",
                            "Marca",
                            "Código",
                            "Descrição",
                            "Tamanho",
                            "Saldo 5",
                            "Teto",
                            "Compra Sugerida",
                            "Semanas estimadas",
                            "Motivo",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Categoria": st.column_config.TextColumn(
                            "Categoria", width="small"
                        ),
                        "Marca": st.column_config.TextColumn(
                            "Marca", width="small"
                        ),
                        "Código": st.column_config.TextColumn(
                            "Código", width="small"
                        ),
                        "Descrição": st.column_config.TextColumn(
                            "Descrição", width="large"
                        ),
                        "Tamanho": st.column_config.TextColumn(
                            "Tamanho", width="small"
                        ),
                        "Saldo 5": st.column_config.NumberColumn(
                            "Saldo 5", format="%d"
                        ),
                        "Teto": st.column_config.NumberColumn(
                            'Tec Faz "x" Confec', format="%d"
                        ),
                        "Compra Sugerida": st.column_config.NumberColumn(
                            "Compra Sugerida", format="%d"
                        ),
                        "Semanas estimadas": st.column_config.NumberColumn(
                            "Semanas estimadas", format="%d"
                        ),
                        "Motivo": st.column_config.TextColumn(
                            "Motivo", width="medium"
                        ),
                    },
                )

        with aba_historico:
            if historico_ficha.empty:
                st.caption(
                    "Esta confecção ainda não tem itens no histórico de produção."
                )
            else:
                itens_ficha = (
                    historico_ficha.groupby(
                        ["Codigo", "Item", "Tipo", "Operacao", "Tamanho"],
                        as_index=False,
                    )
                    .agg(
                        Qtd=("Qtd", "sum"),
                        Origem=(
                            "Origem",
                            lambda serie: ", ".join(
                                sorted({str(v) for v in serie if str(v).strip()})
                            ),
                        ),
                    )
                    .sort_values("Qtd", ascending=False)
                    .rename(columns={"Operacao": "Operação"})
                )
                if len(itens_ficha) > 100:
                    st.caption(
                        "Mostrando os 100 itens de maior volume "
                        f"de {fmt_num(len(itens_ficha))} no histórico."
                    )
                st.dataframe(
                    itens_ficha.head(100),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Codigo": st.column_config.TextColumn(
                            "Código", width="small"
                        ),
                        "Item": st.column_config.TextColumn(
                            "Item", width="large"
                        ),
                        "Tipo": st.column_config.TextColumn(
                            "Tipo", width="small"
                        ),
                        "Operação": st.column_config.TextColumn(
                            "Operação", width="medium"
                        ),
                        "Tamanho": st.column_config.TextColumn(
                            "Tamanho", width="small"
                        ),
                        "Qtd": st.column_config.NumberColumn(
                            "Quantidade", format="%d"
                        ),
                        "Origem": st.column_config.TextColumn(
                            "Origem", width="medium"
                        ),
                    },
                )

# ==================== 2. CAPACIDADE SEMANAL ====================

st.markdown(
    '<div class="db-secao">⚡ Capacidade semanal por confecção</div>',
    unsafe_allow_html=True,
)

capacidades_sel = capacidades[capacidades["Fornecedor"].isin(confeccoes_sel)]
if capacidades_sel.empty:
    st.info("Nenhuma confecção com produção no filtro atual.")
else:
    graf = capacidades_sel.sort_values("CapacidadeSemanal").tail(top_n)
    fig = px.bar(
        graf,
        x="CapacidadeSemanal",
        y="Fornecedor",
        orientation="h",
        color="CapacidadeSemanal",
        color_continuous_scale=["#e8eaf6", "#3949ab"],
        labels={"CapacidadeSemanal": "Unidades por semana", "Fornecedor": ""},
        title=f"Top {len(graf)} confecções por capacidade média semanal",
        template=template_plotly(),
    )
    fig.update_layout(
        height=max(380, 28 * len(graf)),
        coloraxis_showscale=False,
        margin=dict(t=55, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

tabela_capacidade = capacidades_sel.copy()
tabela_capacidade["Última semana"] = tabela_capacidade["UltimaSemana"].map(_periodo)
tabela_capacidade["Média semanal"] = tabela_capacidade["CapacidadeSemanal"].round(0)
tabela_capacidade["Produção total"] = tabela_capacidade["ProducaoTotal"]
tabela_capacidade = tabela_capacidade.rename(
    columns={
        "Fornecedor": "Confecção",
        "Semanas": "Semanas observadas",
        "Tipos": "Tipos produzidos",
    }
)
colunas_capacidade = [
    "Confecção",
    "Média semanal",
    "Semanas observadas",
    "Produção total",
    "MelhorSemana",
    "Última semana",
    "Tipos produzidos",
]
st.dataframe(
    tabela_capacidade[
        [c for c in colunas_capacidade if c in tabela_capacidade.columns]
    ],
    width="stretch",
    hide_index=True,
    column_config={
        "Confecção": st.column_config.TextColumn("Confecção", width="large"),
        "Média semanal": st.column_config.NumberColumn(
            "Capacidade semanal (un.)", format="%d"
        ),
        "Semanas observadas": st.column_config.NumberColumn(
            "Semanas observadas", format="%d"
        ),
        "Produção total": st.column_config.NumberColumn(
            "Produção no período (un.)", format="%d"
        ),
        "MelhorSemana": st.column_config.NumberColumn(
            "Melhor semana (un.)", format="%d"
        ),
        "Última semana": st.column_config.TextColumn(
            "Última semana observada", width="medium"
        ),
        "Tipos produzidos": st.column_config.TextColumn(
            "Tipos produzidos", width="medium"
        ),
    },
)

with st.expander("📅 Ver produção por semana"):
    semanal = (
        producao[producao["Fornecedor"].isin(confeccoes_sel)]
        .groupby(["Fornecedor", "Semana"], as_index=False)
        .agg(Qtd=("Qtd", "sum"), Itens=("Codigo", "nunique"))
        .sort_values(["Semana", "Fornecedor"])
    )
    semanal["Semana"] = semanal["Semana"].map(_periodo)
    semanal = semanal.rename(
        columns={
            "Fornecedor": "Confecção",
            "Semana": "Semana",
            "Qtd": "Unidades",
            "Itens": "Itens",
        }
    )
    st.dataframe(semanal, width="stretch", hide_index=True)

# ==================== 3. RASTREABILIDADE DOS PEDIDOS ====================

st.markdown(
    '<div class="db-secao">🧭 Rastreabilidade dos pedidos em aberto</div>',
    unsafe_allow_html=True,
)

if pedidos is None or pedidos.empty:
    st.info("Envie o arquivo de **Pedidos** para classificar os pedidos em aberto.")
else:
    pedidos_sel = pedidos[
        pedidos["Confecção"].isin(confeccoes_sel) & (pedidos["SaldoAberto"] > 0)
    ].copy()

    totais_bucket = {
        bucket: float(pedidos_sel.loc[pedidos_sel["Classificacao"] == bucket, "SaldoAberto"].sum())
        for bucket in BUCKETS_ORDEM
    }
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(
            card(
                "🟦 Aguardando envio",
                fmt_num(totais_bucket["Aguardando envio"]),
                "ORÇAMENTO · EM SEPARAÇÃO · PEDIDO",
                CORES_BUCKET["Aguardando envio"],
            ),
            unsafe_allow_html=True,
        )
    with b2:
        st.markdown(
            card(
                "🟧 Aguardando produção",
                fmt_num(totais_bucket["Aguardando produção"]),
                "PEDIDO C/ FORN",
                CORES_BUCKET["Aguardando produção"],
            ),
            unsafe_allow_html=True,
        )
    with b3:
        st.markdown(
            card(
                "🟩 Aguardando saldo",
                fmt_num(totais_bucket["Aguardando saldo"]),
                "FAT. PARCIAL",
                CORES_BUCKET["Aguardando saldo"],
            ),
            unsafe_allow_html=True,
        )

    if pedidos_resumo.empty:
        st.info("Não há pedidos com Saldo em aberto no filtro atual.")
    else:
        resumo_sel = pedidos_resumo[
            pedidos_resumo["Confecção"].isin(confeccoes_sel)
        ].copy()
        if somente_com_aberto:
            resumo_sel = resumo_sel[resumo_sel["Saldo aberto"] > 0]
        resumo_sel = resumo_sel.sort_values("Saldo aberto", ascending=False).head(top_n)

        fig = go.Figure()
        for bucket in BUCKETS_ORDEM:
            fig.add_bar(
                x=resumo_sel["Confecção"],
                y=resumo_sel[bucket],
                name=bucket,
                marker_color=CORES_BUCKET[bucket],
                hovertemplate="%{y:,.0f} un.<extra>" + bucket + "</extra>",
            )
        fig.update_layout(
            barmode="stack",
            title=f"Top {len(resumo_sel)} confecções por saldo em aberto",
            yaxis_title="Unidades em aberto",
            xaxis_title="",
            template=template_plotly(),
            height=460,
            legend=dict(orientation="h", y=1.12),
            margin=dict(t=70, l=10, r=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")

        tabela_pedidos = resumo_sel.rename(
            columns={
                "Saldo aberto": "Total em aberto",
                "Pedidos abertos": "Pedidos",
            }
        )
        st.dataframe(
            tabela_pedidos[
                [
                    "Confecção",
                    "Pedidos",
                    "Total em aberto",
                    "Aguardando envio",
                    "Aguardando produção",
                    "Aguardando saldo",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "Confecção": st.column_config.TextColumn("Confecção", width="large"),
                "Pedidos": st.column_config.NumberColumn("Pedidos", format="%d"),
                "Total em aberto": st.column_config.NumberColumn(
                    "Total em aberto (un.)", format="%d"
                ),
                "Aguardando envio": st.column_config.NumberColumn(
                    "Aguardando envio (un.)", format="%d"
                ),
                "Aguardando produção": st.column_config.NumberColumn(
                    "Aguardando produção (un.)", format="%d"
                ),
                "Aguardando saldo": st.column_config.NumberColumn(
                    "Aguardando saldo (un.)", format="%d"
                ),
            },
        )

    with st.expander("📋 Detalhar pedidos em aberto (rastreabilidade)"):
        detalhe_pedidos = pedidos_sel.sort_values(
            ["Dt Entrega", "SaldoAberto"], ascending=[True, False]
        )
        colunas_detalhe = [
            "Confecção",
            "Compra",
            "Status",
            "Classificacao",
            "Cód Confec",
            "Confeccionado",
            "Qtd",
            "QtdRet",
            "SaldoAberto",
            "Dt Entrega",
        ]
        st.dataframe(
            detalhe_pedidos[
                [c for c in colunas_detalhe if c in detalhe_pedidos.columns]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "Confecção": st.column_config.TextColumn("Confecção", width="medium"),
                "Compra": st.column_config.TextColumn("Pedido", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Classificacao": st.column_config.TextColumn(
                    "Classificação", width="small"
                ),
                "Cód Confec": st.column_config.TextColumn("Código", width="small"),
                "Confeccionado": st.column_config.TextColumn(
                    "Item", width="large"
                ),
                "Qtd": st.column_config.NumberColumn("Qtd", format="%d"),
                "QtdRet": st.column_config.NumberColumn("Qtd retornada", format="%d"),
                "SaldoAberto": st.column_config.NumberColumn(
                    "Saldo em aberto", format="%d"
                ),
                "Dt Entrega": st.column_config.DateColumn(
                    "Dt Entrega", format="DD/MM/YYYY"
                ),
            },
        )

# ==================== 4. COMPRA SUGERIDA ====================

st.markdown(
    '<div class="db-secao">🛒 Compra sugerida e categoria da confecção</div>',
    unsafe_allow_html=True,
)

if estoque is None or estoque.empty:
    st.info("Envie o arquivo de **Estoque** para calcular a compra sugerida.")
elif compra.empty:
    st.info("Não há itens com Saldo 5 negativo e compra sugerida no momento.")
else:
    compra_sel = compra[compra["Categoria"].isin(categorias_sel)].copy()

    total_por_categoria = (
        compra.groupby("Categoria")
        .agg(Itens=("Código", "count"), Unidades=("Compra Sugerida", "sum"))
        .reindex(["Já produziu", "Semelhante", "Sem histórico"])
        .fillna(0)
        .reset_index()
    )

    c1, c2 = st.columns([1, 1.6])
    with c1:
        fig = px.pie(
            total_por_categoria,
            names="Categoria",
            values="Unidades",
            hole=0.45,
            color="Categoria",
            color_discrete_map=CORES_CATEGORIA,
            title="Compra sugerida por categoria",
            template=template_plotly(),
        )
        fig.update_layout(height=380, margin=dict(t=55, l=10, r=10, b=10))
        st.plotly_chart(fig, width="stretch")

    with c2:
        k_cat1, k_cat2, k_cat3 = st.columns(3)
        for coluna, categoria, emoji in zip(
            (k_cat1, k_cat2, k_cat3),
            ("Já produziu", "Semelhante", "Sem histórico"),
            ("✅", "🟠", "⚪"),
        ):
            registro = total_por_categoria[
                total_por_categoria["Categoria"] == categoria
            ]
            unidades = float(registro["Unidades"].iloc[0]) if not registro.empty else 0.0
            itens = int(registro["Itens"].iloc[0]) if not registro.empty else 0
            with coluna:
                st.markdown(
                    card(
                        f"{emoji} {categoria}",
                        fmt_num(unidades),
                        f"{fmt_num(itens)} item(ns)",
                        CORES_CATEGORIA[categoria],
                    ),
                    unsafe_allow_html=True,
                )
        st.caption(
            "**Já produziu**: código do item consta no histórico da confecção "
            "(produção e/ou pedidos com Qtd Ret > 0). "
            "**Semelhante**: mesma categoria de produto e mesmo tamanho e/ou mesma "
            "Operação Produtiva. A confecção sugerida é a de maior capacidade entre "
            "as compatíveis, priorizando o código exato."
        )

    if compra_sel.empty:
        st.info("Nenhuma categoria de compra selecionada no filtro.")
    else:
        st.dataframe(
            compra_sel[
                [
                    "Categoria",
                    "Confecção sugerida",
                    "Marca",
                    "Código",
                    "Descrição",
                    "Tamanho",
                    "Saldo 5",
                    "Teto",
                    "Compra Sugerida",
                    "Capacidade semanal",
                    "Semanas estimadas",
                    "Motivo",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "Categoria": st.column_config.TextColumn("Categoria", width="small"),
                "Confecção sugerida": st.column_config.TextColumn(
                    "Confecção sugerida", width="medium"
                ),
                "Marca": st.column_config.TextColumn("Marca", width="small"),
                "Código": st.column_config.TextColumn("Código", width="small"),
                "Descrição": st.column_config.TextColumn(
                    "Descrição", width="large"
                ),
                "Tamanho": st.column_config.TextColumn("Tamanho", width="small"),
                "Saldo 5": st.column_config.NumberColumn("Saldo 5", format="%d"),
                "Teto": st.column_config.NumberColumn(
                    'Tec Faz "x" Confec', format="%d"
                ),
                "Compra Sugerida": st.column_config.NumberColumn(
                    "Compra Sugerida", format="%d"
                ),
                "Capacidade semanal": st.column_config.NumberColumn(
                    "Capacidade semanal (un.)", format="%d"
                ),
                "Semanas estimadas": st.column_config.NumberColumn(
                    "Semanas estimadas", format="%d"
                ),
                "Motivo": st.column_config.TextColumn("Motivo", width="medium"),
            },
        )

        with st.expander("🔎 Ver todas as confecções compatíveis por item"):
            if detalhe_compra.empty:
                st.caption("Sem detalhe de compatibilidade para os itens atuais.")
            else:
                detalhe_sel = detalhe_compra[
                    detalhe_compra["Código"].isin(compra_sel["Código"])
                ].sort_values(
                    ["Código", "Score", "Capacidade semanal"],
                    ascending=[True, False, False],
                )
                st.dataframe(
                    detalhe_sel[
                        [
                            "Código",
                            "Descrição",
                            "Categoria",
                            "Confecção",
                            "Motivo",
                            "Qtd histórico",
                            "Origem",
                            "Capacidade semanal",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Código": st.column_config.TextColumn("Código", width="small"),
                        "Descrição": st.column_config.TextColumn(
                            "Descrição", width="large"
                        ),
                        "Categoria": st.column_config.TextColumn(
                            "Categoria", width="small"
                        ),
                        "Confecção": st.column_config.TextColumn(
                            "Confecção", width="medium"
                        ),
                        "Motivo": st.column_config.TextColumn(
                            "Motivo", width="medium"
                        ),
                        "Qtd histórico": st.column_config.NumberColumn(
                            "Qtd no histórico", format="%d"
                        ),
                        "Origem": st.column_config.TextColumn(
                            "Origem do histórico", width="medium"
                        ),
                        "Capacidade semanal": st.column_config.NumberColumn(
                            "Capacidade semanal (un.)", format="%d"
                        ),
                    },
                )

# ==================== 5. EXPORTAÇÃO ====================

st.markdown("### 📥 Exportar a projeção")

colunas_compra = [
    "Categoria",
    "Confecção sugerida",
    "Marca",
    "Código",
    "Descrição",
    "Tamanho",
    "Tipo",
    "Operação",
    "Saldo 5",
    "Teto",
    "Compra Sugerida",
    "Capacidade semanal",
    "Semanas estimadas",
    "Motivo",
]
compra_export = compra[[c for c in colunas_compra if c in compra.columns]].copy()

pedidos_export = pd.DataFrame()
if pedidos is not None and not pedidos.empty:
    abertos = pedidos[pedidos["SaldoAberto"] > 0]
    colunas_pedidos = [
        "Confecção",
        "Compra",
        "Status",
        "Classificacao",
        "Cód Confec",
        "Confeccionado",
        "Qtd",
        "QtdRet",
        "SaldoAberto",
        "Dt Entrega",
    ]
    pedidos_export = abertos[
        [c for c in colunas_pedidos if c in abertos.columns]
    ].copy()

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    capacidades.to_excel(writer, index=False, sheet_name="Capacidade")
    pedidos_export.to_excel(writer, index=False, sheet_name="Pedidos em Aberto")
    compra_export.to_excel(writer, index=False, sheet_name="Compra Sugerida")
    consolidado.to_excel(writer, index=False, sheet_name="Por Confecção")
    if not detalhe_compra.empty:
        detalhe_compra.to_excel(writer, index=False, sheet_name="Compatibilidade")

data_arquivo = pd.Timestamp.today().strftime("%Y-%m-%d")
c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "📥 Baixar CSV — compra sugerida",
        data=compra_export.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"compra_sugerida_confeccao_{data_arquivo}.csv",
        mime="text/csv",
        width="stretch",
    )
with c2:
    st.download_button(
        "📊 Baixar Excel — projeção completa",
        data=buffer.getvalue(),
        file_name=f"projecao_confeccao_{data_arquivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
