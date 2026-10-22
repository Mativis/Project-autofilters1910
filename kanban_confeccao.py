"""
Kanban de Confecção
-------------------------
Página principal do sistema: planilha de pedidos por confecção, com
quantidade emergencial (Q.E), impressão por aba e exportação em Excel.

A função `pagina_kanban` é registrada em `app.py` via `st.navigation`.
"""

import streamlit as st
import pandas as pd
import numpy as np
import html
import io
import re
import base64
import xlsxwriter
from datetime import date

from nucleo import (
    COLUNAS_ESTOQUE,
    COLUNAS_PEDIDOS,
    CORES_PRIORIDADE,
    FATOR_URGENCIA_PADRAO,
    ORDEM_PRIORIDADE,
    calcular_prioridade,
    calcular_qe,
    classe_prioridade,
    codigos_saldo2_negativo,
    fmt_compra,
    fmt_data,
    fmt_num,
    load_excel,
    normalizar_cod,
    preparar_estoque,
    preparar_pedidos,
    saldo2_por_codigo,
    sidebar_arquivos,
    tema_escuro,
    texto_dias,
)

# ==================== TEMA (claro / escuro) ====================
PALETA_ESCURO = """
            --kb-surface: #0f1623;
            --kb-surface-2: #131c2e;
            --kb-row-alt: #111827;
            --kb-row-hover: #1e293b;
            --kb-head-from: #1e293b;
            --kb-head-to: #131c2e;
            --kb-sum-from: #131c2e;
            --kb-sum-to: #1e293b;
            --kb-border: #1e293b;
            --kb-border-soft: #1a2332;
            --kb-text: #e2e8f0;
            --kb-text-soft: #94a3b8;
            --kb-chip-bg: #1e293b;
            --kb-chip-border: #334155;
            --kb-shadow: rgba(0, 0, 0, 0.4);
            --kb-info-from: rgba(99, 102, 241, 0.15);
            --kb-info-to: rgba(139, 92, 246, 0.1);
            --kb-info-text: #c7d2fe;
            --kb-qe: #fbbf24;
            --kb-qe-bg: rgba(251, 191, 36, 0.12);
"""

PALETA_CLARO = """
            --kb-surface: #ffffff;
            --kb-surface-2: #f8fafc;
            --kb-row-alt: #f9fafb;
            --kb-row-hover: #f1f5f9;
            --kb-head-from: #f8fafc;
            --kb-head-to: #f1f5f9;
            --kb-sum-from: #f8fafc;
            --kb-sum-to: #f1f5f9;
            --kb-border: #e2e8f0;
            --kb-border-soft: #f1f5f9;
            --kb-text: #0f172a;
            --kb-text-soft: #64748b;
            --kb-chip-bg: #f1f5f9;
            --kb-chip-border: #e2e8f0;
            --kb-shadow: rgba(15, 23, 42, 0.04);
            --kb-info-from: rgba(99, 102, 241, 0.08);
            --kb-info-to: rgba(139, 92, 246, 0.05);
            --kb-info-text: #4338ca;
            --kb-qe: #b45309;
            --kb-qe-bg: #fffbeb;
"""


def pagina_kanban():
    """Renderiza a página do Kanban de Confecção."""
    # Configurar página
    st.set_page_config(
        page_title="Kanban de Confecção",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # A paleta acompanha o tema em uso (claro/escuro) a cada execução
    paleta = PALETA_ESCURO if tema_escuro() else PALETA_CLARO

    st.markdown(
        """
        <style>
            :root {
                --kb-primary: #6366f1;
                --kb-secondary: #8b5cf6;
                --kb-atrasado: #dc2626;
                --kb-alta: #ef4444;
                --kb-media: #f59e0b;
                --kb-baixa: #22c55e;
    /*__PALETA__*/
            }
            
            .main .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                max-width: 1600px;
            }

            .kb-header {
                background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
                color: white;
                padding: 2rem 2.5rem;
                border-radius: 16px;
                margin-bottom: 1.5rem;
                box-shadow: 0 20px 60px -20px rgba(99, 102, 241, 0.6);
                position: relative;
                overflow: hidden;
            }
            .kb-header::before {
                content: '';
                position: absolute;
                top: -50%;
                right: -10%;
                width: 320px;
                height: 320px;
                background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
                border-radius: 50%;
            }
            .kb-header::after {
                content: '';
                position: absolute;
                bottom: -30%;
                left: -5%;
                width: 200px;
                height: 200px;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                border-radius: 50%;
            }
            .kb-header h1 { margin: 0; font-size: 2rem; font-weight: 800; position: relative; z-index: 1; letter-spacing: -0.02em; }
            .kb-header p { margin: 0.5rem 0 0 0; opacity: 0.95; font-size: 1rem; position: relative; z-index: 1; font-weight: 500; }

            .kb-legend {
                display: flex;
                gap: 0.6rem;
                flex-wrap: wrap;
                margin-bottom: 1.5rem;
            }
            .kb-legend-item {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: var(--kb-surface);
                border: 1px solid var(--kb-border);
                color: var(--kb-text);
                border-radius: 999px;
                padding: 0.4rem 1rem;
                font-size: 0.8rem;
                font-weight: 600;
                box-shadow: 0 1px 3px var(--kb-shadow);
                transition: all 0.2s ease;
            }
            .kb-legend-item:hover {
                box-shadow: 0 4px 12px var(--kb-shadow);
                border-color: rgba(99, 102, 241, 0.3);
            }
            .kb-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; box-shadow: 0 0 0 3px rgba(0,0,0,0.02); }
            .kb-dot.atrasado { background: var(--kb-atrasado); }
            .kb-dot.alta { background: var(--kb-alta); }
            .kb-dot.media { background: var(--kb-media); }
            .kb-dot.baixa { background: var(--kb-baixa); }

            .kb-tab-summary {
                background: linear-gradient(90deg, rgba(99, 102, 241, 0.08) 0%, transparent 100%);
                border: 1px solid var(--kb-border);
                border-left: 3px solid #6366f1;
                border-radius: 12px;
                padding: 0.8rem 1.2rem;
                margin: 0.5rem 0 1rem 0;
                font-size: 0.875rem;
                color: var(--kb-text-soft);
                font-weight: 500;
            }
            .kb-tab-summary b { color: var(--kb-text); font-weight: 700; }

            .kb-badge {
                display: inline-flex;
                align-items: center;
                padding: 0.2rem 0.65rem;
                border-radius: 999px;
                font-size: 0.7rem;
                font-weight: 600;
                color: white;
                white-space: nowrap;
                letter-spacing: 0.01em;
            }
            .kb-badge.atrasado { background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); box-shadow: 0 2px 8px rgba(220, 38, 38, 0.3); }
            .kb-badge.alta { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3); }
            .kb-badge.media { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3); }
            .kb-badge.baixa { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3); }

            /* Planilha — uma linha por item */
            .kb-sheet-wrap {
                overflow-x: auto;
                background: var(--kb-surface);
                border: 1px solid var(--kb-border);
                border-radius: 16px;
                box-shadow: 0 1px 3px var(--kb-shadow);
                margin-bottom: 1rem;
            }
            table.kb-sheet {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.875rem;
            }
            table.kb-sheet thead th {
                position: sticky;
                top: 0;
                z-index: 2;
                background: linear-gradient(180deg, var(--kb-head-from) 0%, var(--kb-head-to) 100%);
                color: var(--kb-text-soft);
                text-align: left;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--kb-border);
                white-space: nowrap;
            }
            table.kb-sheet tbody td {
                padding: 0.7rem 1rem;
                border-bottom: 1px solid var(--kb-border-soft);
                color: var(--kb-text);
                vertical-align: middle;
            }
            table.kb-sheet tbody tr:nth-child(even) { background: var(--kb-row-alt); }
            table.kb-sheet tbody tr:hover { background: var(--kb-row-hover); }
            table.kb-sheet td.kb-num { text-align: right; font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; }
            table.kb-sheet td.kb-qe {
                color: var(--kb-qe);
                background: var(--kb-qe-bg);
                border-left: 1px solid var(--kb-border-soft);
                border-right: 1px solid var(--kb-border-soft);
                font-weight: 700;
            }
            table.kb-sheet thead th:nth-child(6) { color: var(--kb-qe); }
            table.kb-sheet tfoot td.kb-qe { background: var(--kb-qe-bg); color: var(--kb-qe); }
            table.kb-sheet td.kb-date { white-space: nowrap; font-variant-numeric: tabular-nums; }
            table.kb-sheet td.kb-desc-cell { min-width: 280px; }
            table.kb-sheet td.kb-conf-cell { color: var(--kb-text-soft); white-space: nowrap; }
            table.kb-sheet tr.row-atrasado td:first-child { box-shadow: inset 3px 0 0 var(--kb-atrasado); }
            table.kb-sheet tr.row-alta td:first-child { box-shadow: inset 3px 0 0 var(--kb-alta); }
            table.kb-sheet tr.row-media td:first-child { box-shadow: inset 3px 0 0 var(--kb-media); }
            table.kb-sheet tr.row-baixa td:first-child { box-shadow: inset 3px 0 0 var(--kb-baixa); }
            table.kb-sheet tfoot td {
                padding: 0.75rem 1rem;
                border-top: 1px solid var(--kb-border);
                background: var(--kb-surface-2);
                color: var(--kb-text);
                font-weight: 700;
            }
            .kb-sheet-wrap .kb-cod {
                display: inline-block;
                background: var(--kb-chip-bg);
                border: 1px solid var(--kb-chip-border);
                color: var(--kb-text);
                border-radius: 6px;
                padding: 0.15rem 0.5rem;
                font-size: 0.75rem;
                font-weight: 600;
                font-variant-numeric: tabular-nums;
            }

            .kb-info-box {
                background: linear-gradient(90deg, var(--kb-info-from) 0%, var(--kb-info-to) 100%);
                color: var(--kb-info-text);
                padding: 0.9rem 1.25rem;
                border-radius: 12px;
                border: 1px solid rgba(99, 102, 241, 0.2);
                margin: 1rem 0;
                font-size: 0.875rem;
            }
        </style>
        """.replace("/*__PALETA__*/", paleta),
        unsafe_allow_html=True,
    )

    # ==================== FUNÇÕES AUXILIARES ====================
    # (load_excel, normalizar_cod, prioridade, formatação e uploaders ficam em
    #  nucleo.py, compartilhados com as páginas de Dashboards e Estoque.)


    # ==================== INTERFACE PRINCIPAL ====================

    st.markdown(
        """
        <div class="kb-header">
            <h1>📋 Kanban de Confecção</h1>
            <p>Gestão visual de pedidos por confecção com controle de prioridade e quantidade emergencial</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="kb-legend">
            <span class="kb-legend-item"><span class="kb-dot atrasado"></span> Atrasado — data de entrega vencida</span>
            <span class="kb-legend-item"><span class="kb-dot alta"></span> Alta — entrega em até 15 dias</span>
            <span class="kb-legend-item"><span class="kb-dot media"></span> Média — entrega em 16 a 30 dias</span>
            <span class="kb-legend-item"><span class="kb-dot baixa"></span> Baixa — entrega em mais de 1 mês</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar: upload dos arquivos (compartilhado com as demais páginas)
    df_pedidos, df_estoque = sidebar_arquivos()

    if df_pedidos is None or df_estoque is None:
        st.info("👆 Faça o upload dos arquivos de **Pedidos** e **Estoque** na barra lateral para montar o kanban.")
        with st.expander("ℹ️ Como funciona esta página"):
            st.markdown("""
                1. O sistema lê o arquivo de **Estoque** e identifica todos os itens com **Saldo 2 negativo**.
                2. Esses códigos (`Cód Confec`) são usados para **filtrar os Pedidos**.
                3. Os pedidos filtrados são **agrupados por Confecção** em abas, com os itens em formato de **planilha (uma linha por item)**.
                4. Cada linha mostra informações vindas apenas do arquivo de **Pedidos**:
                   - **Pedido** (coluna `Compra`)
                   - **Cód Confec**
                   - **Descrição** (coluna `Confeccionado`)
                   - **Quantidade** (coluna `Saldo`)
                   - **Q.E** (Quantidade Emergencial, calculada com o `Saldo 2` do Estoque)
                   - **Data de entrega** (coluna `Dt Entrega`)
                   - **Prioridade** (calculada pela data de entrega)

                ### Regra de prioridade (em relação ao dia de hoje):
                | Prazo até a entrega | Prioridade |
                |---|---|
                | Data de entrega já vencida | ⚠️ Atrasado |
                | Mais de 1 mês (> 30 dias) | 🟢 Baixa |
                | Menos de 1 mês e mais de 15 dias (16 a 30) | 🟠 Média |
                | Menos de 15 dias | 🔴 Alta |

                ### Regra de quantidade:
                - 🚫 Linhas em que o **Saldo** é **igual ou menor que 4% da Qtd** são desconsideradas
                  (ex.: Qtd = 100 → Saldo ≤ 4 é descartado). Pode ser desativada na barra lateral.

                ### Quantidade Emergencial (Q.E):
                - `Q.E = |Saldo 2| × fator` (fator ajustável na barra lateral, padrão **1,10**), arredondada para cima.
                - A Q.E **nunca ultrapassa a Quantidade em aberto do pedido** (coluna `Saldo`).
            """)
        st.stop()

    # ==================== CARREGAMENTO E FILTRAGEM ====================

    try:
        df_pedidos = preparar_pedidos(df_pedidos)
        df_estoque = preparar_estoque(df_estoque)
    except Exception as e:
        st.error(f"Erro ao ler os arquivos: {e}")
        st.stop()

    # Validação de colunas
    faltando_pedidos = [c for c in COLUNAS_PEDIDOS if c not in df_pedidos.columns]
    faltando_estoque = [c for c in COLUNAS_ESTOQUE if c not in df_estoque.columns]

    if faltando_pedidos:
        st.error(f"❌ Colunas ausentes no arquivo de **Pedidos**: {', '.join(faltando_pedidos)}")
        st.stop()
    if faltando_estoque:
        st.error(f"❌ Colunas ausentes no arquivo de **Estoque**: {', '.join(faltando_estoque)}")
        st.stop()

    # 1) Códigos com Saldo 2 negativo no Estoque
    codigos_saldo2_neg = codigos_saldo2_negativo(df_estoque)
    mapa_saldo2 = saldo2_por_codigo(df_estoque)

    # 2) Filtrar Pedidos pelo Cód Confec
    df_pedidos["Cód Confec_norm"] = df_pedidos["Cód Confec"].map(normalizar_cod)
    df_kanban = df_pedidos[df_pedidos["Cód Confec_norm"].isin(codigos_saldo2_neg)].copy()

    # 3) Preparar colunas exibidas no kanban (dados somente de Pedidos)
    df_kanban["Dt Entrega"] = pd.to_datetime(df_kanban["Dt Entrega"], errors="coerce")
    df_kanban["Saldo"] = pd.to_numeric(df_kanban["Saldo"], errors="coerce")
    df_kanban["Qtd"] = pd.to_numeric(df_kanban["Qtd"], errors="coerce")
    df_kanban["Prioridade"] = df_kanban["Dt Entrega"].apply(calcular_prioridade)
    df_kanban["Confecção"] = (
        df_kanban["Confecção"].fillna("").astype(str).str.strip().replace("", "Sem Confecção")
    )
    df_kanban["Confeccionado"] = df_kanban["Confeccionado"].fillna("").astype(str).str.strip()
    df_kanban["Cód Confec"] = df_kanban["Cód Confec_norm"]

    if df_kanban.empty:
        st.warning("Nenhum pedido encontrado para os códigos com Saldo 2 negativo no Estoque.")
        st.stop()

    # ==================== BARRA LATERAL: FILTROS ====================

    with st.sidebar:
        st.markdown("---")
        st.header("🔍 Filtros")

        confeccoes_sel = st.multiselect(
            "Confecção",
            options=sorted(df_kanban["Confecção"].unique().tolist()),
            default=sorted(df_kanban["Confecção"].unique().tolist()),
        )

        prioridades_sel = st.multiselect(
            "Prioridade",
            options=["Atrasado", "Alta", "Média", "Baixa"],
            default=["Atrasado", "Alta", "Média", "Baixa"],
        )

        termo_busca = st.text_input("Buscar por código ou descrição:", value="")

        st.markdown("---")
        desconsiderar_saldo_baixo = st.checkbox(
            "Desconsiderar Saldo ≤ 4% da Qtd",
            value=True,
            help="Remove as linhas em que o Saldo é igual ou menor que 4% da Qtd.",
        )

        fator_urgencia = st.number_input(
            "Fator de urgência (Q.E)",
            min_value=1.0,
            max_value=3.0,
            value=FATOR_URGENCIA_PADRAO,
            step=0.05,
            format="%.2f",
            help=(
                "Quantidade Emergencial = |Saldo 2| × fator, limitada pela Quantidade "
                "em aberto do pedido."
            ),
        )

    # ==================== REGRA: Saldo ≤ 4% da Qtd ====================

    df_base = df_kanban.copy()
    linhas_descartadas = 0

    # Quantidade Emergencial: |Saldo 2| x fator, limitada pela Quantidade do pedido
    df_base["Saldo 2"] = df_base["Cód Confec"].map(mapa_saldo2)
    df_base["Q.E"] = [
        calcular_qe(saldo2, saldo, fator_urgencia)
        for saldo2, saldo in zip(df_base["Saldo 2"], df_base["Saldo"])
    ]

    if desconsiderar_saldo_baixo:
        mask_saldo_baixo = (df_base["Qtd"] > 0) & (df_base["Saldo"] <= df_base["Qtd"] * 0.04)
        linhas_descartadas = int(mask_saldo_baixo.sum())
        df_base = df_base[~mask_saldo_baixo].copy()

    df_filtrado = df_base[df_base["Confecção"].isin(confeccoes_sel)].copy()
    df_filtrado = df_filtrado[df_filtrado["Prioridade"].isin(prioridades_sel)]

    if termo_busca.strip():
        termo = termo_busca.strip().lower()
        df_filtrado = df_filtrado[
            df_filtrado["Cód Confec"].str.lower().str.contains(termo, na=False)
            | df_filtrado["Confeccionado"].str.lower().str.contains(termo, na=False)
        ]

    if desconsiderar_saldo_baixo and linhas_descartadas > 0:
        st.info(
            f"ℹ️ {linhas_descartadas} linha(s) desconsiderada(s) por terem "
            f"Saldo ≤ 4% da Qtd (dados apenas de Pedidos)."
        )


    # ==================== MÉTRICAS ====================

    st.markdown("---")

    contagem_prio = df_filtrado["Prioridade"].value_counts()

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total de Pedidos", len(df_filtrado))
    with col2:
        st.metric("Confecções", df_filtrado["Confecção"].nunique())
    with col3:
        st.metric("⚠️ Atrasado", int(contagem_prio.get("Atrasado", 0)))
    with col4:
        st.metric("🔴 Alta", int(contagem_prio.get("Alta", 0)))
    with col5:
        st.metric("🟠 Média", int(contagem_prio.get("Média", 0)))
    with col6:
        st.metric("🟢 Baixa", int(contagem_prio.get("Baixa", 0)))

    st.markdown(
        f"<div class='kb-info-box'>📦 Quantidade total (Saldo): <b>{fmt_num(df_filtrado['Saldo'].sum())}</b> unidade(s) &nbsp;|&nbsp; "
        f"🚨 Quantidade Emergencial: <b>{fmt_num(df_filtrado['Q.E'].sum())}</b> unidade(s) "
        f"(|Saldo 2| × {fator_urgencia:.2f}, limitada pela quantidade do pedido) &nbsp;|&nbsp; "
        f"🔍 <b>{len(codigos_saldo2_neg)}</b> código(s) com Saldo 2 negativo no Estoque &nbsp;|&nbsp; "
        f"📅 Data de referência: <b>{date.today().strftime('%d/%m/%Y')}</b></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ==================== RENDERIZAÇÃO DO KANBAN ====================

    st.markdown("### 📌 Pedidos por Confecção ")

    if df_filtrado.empty:
        st.warning("Nenhum pedido encontrado com os filtros selecionados.")
        st.stop()

    # Ordenar por prioridade → data de entrega → compra
    df_filtrado["_prio_ord"] = df_filtrado["Prioridade"].map(ORDEM_PRIORIDADE)
    df_filtrado = df_filtrado.sort_values(
        ["_prio_ord", "Dt Entrega", "Compra"],
        ascending=[True, True, True],
    )


    def html_sheet(df_col):
        """Monta o HTML de uma planilha (uma linha por item) de uma confecção"""
        linhas = []
        for _, row in df_col.iterrows():
            cls = classe_prioridade(row["Prioridade"])
            pedido = html.escape(fmt_compra(row["Compra"]))
            cod = html.escape(str(row["Cód Confec"]))
            desc = html.escape(str(row["Confeccionado"]).strip())
            conf = html.escape(str(row["Confecção"]))
            qtd = fmt_num(row["Saldo"])
            qe = fmt_num(row["Q.E"])
            data = fmt_data(row["Dt Entrega"])
            prio = html.escape(str(row["Prioridade"]))
            prio_txt = ("⚠️ " if row["Prioridade"] == "Atrasado" else "") + prio
            dias_txt = html.escape(texto_dias(row["Dt Entrega"]))

            linhas.append(
                f'<tr class="row-{cls}">'
                f'<td class="kb-pedido-cell">{pedido}</td>'
                f'<td><span class="kb-cod">{cod}</span></td>'
                f'<td class="kb-desc-cell">{desc}</td>'
                f'<td class="kb-conf-cell">{conf}</td>'
                f'<td class="kb-num">{qtd}</td>'
                f'<td class="kb-num kb-qe">{qe}</td>'
                f'<td class="kb-date" title="{dias_txt}">{data}</td>'
                f'<td><span class="kb-badge {cls}">{prio_txt}</span></td>'
                "</tr>"
            )

        return (
            '<div class="kb-sheet-wrap">'
            '<table class="kb-sheet">'
            "<thead><tr>"
            "<th>Pedido</th>"
            "<th>Cód Confec</th>"
            "<th>Descrição</th>"
            "<th>Confecção</th>"
            '<th style="text-align:right">Quantidade</th>'
            '<th style="text-align:right" title="Quantidade Emergencial">Q.E</th>'
            "<th>Data de Entrega</th>"
            "<th>Prioridade</th>"
            "</tr></thead>"
            "<tbody>" + "".join(linhas) + "</tbody>"
            "<tfoot><tr>"
            f'<td colspan="4">Total ({len(df_col)} item(ns))</td>'
            f'<td class="kb-num">{fmt_num(df_col["Saldo"].sum())}</td>'
            f'<td class="kb-num kb-qe">{fmt_num(df_col["Q.E"].sum())}</td>'
            '<td colspan="2"></td>'
            "</tr></tfoot>"
            "</table></div>"
        )


    # ==================== IMPRESSÃO (NOVA GUIA) ====================

    CSS_IMPRESSAO = """
        @page { size: A4 landscape; margin: 10mm; }
        * { box-sizing: border-box; }
        body {
            font-family: "Segoe UI", Roboto, Arial, sans-serif;
            color: #1f2430;
            background: #eef1f6;
            margin: 0;
            padding: 18px;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .barra {
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
            background: #ffffff;
            border: 1px solid #dfe4f0;
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 18px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.07);
        }
        .botao {
            border: 0;
            cursor: pointer;
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .dica { font-size: 12px; color: #5a6172; }
        .cab { margin-bottom: 14px; }
        .cab h1 { font-size: 20px; margin: 0 0 4px 0; }
        .cab p { margin: 2px 0; font-size: 12px; color: #5a6172; }
        .legenda { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; font-size: 12px; font-weight: 600; }
        .legenda .item { display: inline-flex; align-items: center; gap: 6px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .dot.atrasado { background: #b71c1c; }
        .dot.alta { background: #f44336; }
        .dot.media { background: #ff9800; }
        .dot.baixa { background: #4caf50; }
        .bloco {
            background: #ffffff;
            border: 1px solid #dfe4f0;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 18px;
        }
        .bloco h2 { font-size: 15px; margin: 0 0 2px 0; }
        .bloco h2 .cont { font-size: 12px; font-weight: 600; color: #5a6172; }
        .resumo-linha { margin: 0 0 10px 0; font-size: 12px; color: #3d4455; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #d9dfec; padding: 5px 7px; font-size: 11px; text-align: left; vertical-align: top; }
        th {
            background: #f2f5fa;
            color: #5a6172;
            font-size: 9.5px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        th.num-h, td.num { text-align: right; }
        td.num { font-weight: 700; white-space: nowrap; }
        th.num-h.qe, td.num.qe { color: #b26a00; background: #fff6e6; }
        tfoot td.num.qe { color: #b26a00; background: #fdeeda; }
        td.dt { white-space: nowrap; }
        td.conf { white-space: nowrap; }
        td.desc { min-width: 220px; }
        .dias { display: block; font-size: 9.5px; font-weight: 600; color: #7a8194; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            color: #ffffff;
            white-space: nowrap;
        }
        .badge.atrasado { background: #b71c1c; }
        .badge.alta { background: #f44336; }
        .badge.media { background: #ff9800; }
        .badge.baixa { background: #4caf50; }
        tfoot td { font-weight: 800; background: #f8fafd; }
        @media print {
            body { background: #ffffff; padding: 0; }
            .barra { display: none; }
            .bloco { border: 0; border-radius: 0; padding: 0; margin: 0 0 14px 0; }
            .bloco + .bloco { break-before: page; page-break-before: always; }
            .bloco, table, tr, td, th { break-inside: avoid; page-break-inside: avoid; }
            thead { display: table-header-group; }
        }
    """

    COMPONENTE_IMPRESSAO = """
    <style>
        html, body { margin: 0; padding: 0; background: transparent; }
    </style>
    <a id="kb-abrir-impressao" href="#" target="_blank" rel="noopener" style="
        display: block;
        box-sizing: border-box;
        width: 100%;
        cursor: pointer;
        border-radius: 8px;
        padding: 0.55rem 1rem;
        text-align: center;
        text-decoration: none;
        font-family: 'Segoe UI', Roboto, sans-serif;
        font-size: 0.95rem;
        font-weight: 700;
        color: #ffffff;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        box-shadow: 0 2px 10px rgba(102, 126, 234, 0.35);">
        🖨️ Abrir para impressão (nova guia)
    </a>
    <script>
        (function () {
            const KB_B64 = "__B64__";
            const bin = atob(KB_B64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const documento = new TextDecoder("utf-8").decode(bytes);
            const url = URL.createObjectURL(new Blob([documento], { type: "text/html;charset=utf-8" }));
            /* Link de verdade (target=_blank): não sofre bloqueio de pop-up. */
            document.getElementById("kb-abrir-impressao").href = url;
        })();
    </script>
    """


    def gerar_html_impressao(df_dados, incluir_resumo=True, confeccao_destaque=None):
        """Gera um documento HTML completo e autocontido, pronto para impressão.

        Com ``confeccao_destaque`` o documento fica focado em uma única confecção
        (usado pelos botões de impressão de cada aba).
        """
        confeccoes = sorted(df_dados["Confecção"].unique().tolist())

        blocos = []
        linhas_resumo = []

        for conf in confeccoes:
            d = df_dados[df_dados["Confecção"] == conf]
            conf_esc = html.escape(str(conf))
            contagem = d["Prioridade"].value_counts()
            n_atrasado = int(contagem.get("Atrasado", 0))
            n_alta = int(contagem.get("Alta", 0))
            n_media = int(contagem.get("Média", 0))
            n_baixa = int(contagem.get("Baixa", 0))
            total_un = fmt_num(d["Saldo"].sum())

            linhas = []
            for _, row in d.iterrows():
                prio_val = str(row["Prioridade"])
                cls = classe_prioridade(prio_val)
                prio_txt = html.escape(("⚠️ " if prio_val == "Atrasado" else "") + prio_val)
                linhas.append(
                    "<tr>"
                    f'<td>{html.escape(fmt_compra(row["Compra"]))}</td>'
                    f'<td>{html.escape(str(row["Cód Confec"]))}</td>'
                    f'<td class="desc">{html.escape(str(row["Confeccionado"]))}</td>'
                    f'<td class="conf">{conf_esc}</td>'
                    f'<td class="num">{fmt_num(row["Saldo"])}</td>'
                    f'<td class="num qe">{fmt_num(row["Q.E"])}</td>'
                    f'<td class="dt">{fmt_data(row["Dt Entrega"])}'
                    f'<span class="dias">{html.escape(texto_dias(row["Dt Entrega"]))}</span></td>'
                    f'<td><span class="badge {cls}">{prio_txt}</span></td>'
                    "</tr>"
                )

            tabela = (
                "<table>"
                "<thead><tr>"
                "<th>Pedido</th><th>Cód Confec</th><th>Descrição</th><th>Confecção</th>"
                '<th class="num-h">Quantidade</th><th class="num-h">Q.E</th>'
                "<th>Data de Entrega</th><th>Prioridade</th>"
                "</tr></thead>"
                "<tbody>" + "".join(linhas) + "</tbody>"
                "<tfoot><tr>"
                f'<td colspan="4">Total ({len(d)} item(ns))</td>'
                f'<td class="num">{total_un}</td>'
                f'<td class="num qe">{fmt_num(d["Q.E"].sum())}</td>'
                '<td colspan="2"></td>'
                "</tr></tfoot>"
                "</table>"
            )

            blocos.append(
                '<section class="bloco">'
                f'<h2>🏭 {conf_esc} <span class="cont">({len(d)} pedido(s) · {total_un} unidade(s) · '
                f'Q.E: {fmt_num(d["Q.E"].sum())})</span></h2>'
                '<p class="resumo-linha">'
                f'⚠️ Atrasado: <b>{n_atrasado}</b> &nbsp;·&nbsp; 🔴 Alta: <b>{n_alta}</b> '
                f'&nbsp;·&nbsp; 🟠 Média: <b>{n_media}</b> &nbsp;·&nbsp; 🟢 Baixa: <b>{n_baixa}</b>'
                "</p>"
                + tabela
                + "</section>"
            )

            linhas_resumo.append(
                "<tr>"
                f"<td>{conf_esc}</td>"
                f'<td class="num">{len(d)}</td>'
                f'<td class="num">{total_un}</td>'
                f'<td class="num">{n_atrasado}</td>'
                f'<td class="num">{n_alta}</td>'
                f'<td class="num">{n_media}</td>'
                f'<td class="num">{n_baixa}</td>'
                "</tr>"
            )

        total_prio = df_dados["Prioridade"].value_counts()
        resumo = (
            '<section class="bloco">'
            "<h2>Resumo geral por confecção</h2>"
            "<table>"
            "<thead><tr>"
            "<th>Confecção</th>"
            '<th class="num-h">Pedidos</th>'
            '<th class="num-h">Unidades</th>'
            '<th class="num-h">⚠️ Atrasado</th>'
            '<th class="num-h">🔴 Alta</th>'
            '<th class="num-h">🟠 Média</th>'
            '<th class="num-h">🟢 Baixa</th>'
            "</tr></thead>"
            "<tbody>" + "".join(linhas_resumo) + "</tbody>"
            "<tfoot><tr>"
            "<td>TOTAL</td>"
            f'<td class="num">{len(df_dados)}</td>'
            f'<td class="num">{fmt_num(df_dados["Saldo"].sum())}</td>'
            f'<td class="num">{int(total_prio.get("Atrasado", 0))}</td>'
            f'<td class="num">{int(total_prio.get("Alta", 0))}</td>'
            f'<td class="num">{int(total_prio.get("Média", 0))}</td>'
            f'<td class="num">{int(total_prio.get("Baixa", 0))}</td>'
            "</tr></tfoot>"
            "</table>"
            "</section>"
        )

        if not incluir_resumo or len(confeccoes) < 2:
            resumo = ""

        legenda = (
            '<div class="legenda">'
            '<span class="item"><span class="dot atrasado"></span> ⚠️ Atrasado — data de entrega vencida</span>'
            '<span class="item"><span class="dot alta"></span> 🔴 Alta — entrega em até 15 dias</span>'
            '<span class="item"><span class="dot media"></span> 🟠 Média — entrega em 16 a 30 dias</span>'
            '<span class="item"><span class="dot baixa"></span> 🟢 Baixa — entrega em mais de 1 mês</span>'
            "</div>"
        )

        destaque_html = (
            f"<p><b>Confecção:</b> {html.escape(str(confeccao_destaque))}</p>"
            if confeccao_destaque
            else ""
        )
        titulo = (
            f"Kanban de Confecção — {confeccao_destaque}"
            if confeccao_destaque
            else "Kanban de Confecção"
        )
        info_confs = (
            ""
            if confeccao_destaque
            else f" · {df_dados['Confecção'].nunique()} confecção(ões)"
        )

        return (
            "<!DOCTYPE html>"
            '<html lang="pt-BR"><head><meta charset="utf-8">'
            f"<title>{html.escape(str(titulo))} — {date.today().strftime('%d/%m/%Y')}</title>"
            "<style>" + CSS_IMPRESSAO + "</style>"
            "</head><body>"
            '<div class="barra">'
            '<button class="botao" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>'
            '<span class="dica">Dica: em “Mais definições”, escolha <b>Paisagem</b> e marque '
            "<b>Gráficos de plano de fundo</b> para sair com as cores.</span>"
            "</div>"
            '<header class="cab">'
            "<h1>📌 Kanban de Confecção </h1>"
            + destaque_html
            + f"<p>Data de referência: <b>{date.today().strftime('%d/%m/%Y')}</b> · "
            f"{len(df_dados)} pedido(s) · {fmt_num(df_dados['Saldo'].sum())} unidade(s)"
            f"{info_confs}</p>"
            "</header>"
            + legenda
            + "".join(blocos)
            + resumo
            + "</body></html>"
        )


    # ==================== EXPORTAÇÃO EXCEL FORMATADA (POR CONFECÇÃO) ====================

    CORES_PRIORIDADE = {
        "Atrasado": "#b71c1c",
        "Alta": "#f44336",
        "Média": "#ff9800",
        "Baixa": "#4caf50",
    }


    def _nome_aba(confeccao):
        """Nome de aba válido no Excel (sem caracteres proibidos, até 31 chars)."""
        nome = re.sub(r"[\[\]\*\?/\\:]", " ", str(confeccao)).strip()
        nome = re.sub(r"\s+", " ", nome)
        return (nome or "Kanban")[:31]


    def gerar_excel_conf(df_col, confeccao):
        """Gera um .xlsx formatado, o mais próximo possível da visualização em tela."""
        C_PRIMARIA = "#667eea"
        C_BORDA = "#d9dfec"
        C_BORDA_SOFT = "#eef1f7"
        C_HEAD_BG = "#eef1f7"
        C_ROW_ALT = "#fbfcfe"
        C_TEXT = "#3d4455"
        C_TEXT_SOFT = "#5a6172"
        C_TOTAL_BG = "#f0f2f8"

        linhas = list(df_col.iterrows())
        n_linhas = len(linhas)

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
        workbook.set_properties(
            {
                "title": f"Kanban de Confecção — {confeccao}",
                "subject": "Pedidos sem estoque (Estoque com Saldo 2 negativo)",
                "author": "Kanban de Confecção",
                "comments": f"Gerado em {date.today().strftime('%d/%m/%Y')}",
            }
        )
        ws = workbook.add_worksheet(_nome_aba(confeccao))

        # ---------- Formatos ----------
        def base(bg, extra=None):
            props = {
                "font_name": "Calibri",
                "font_size": 10,
                "font_color": C_TEXT,
                "bg_color": bg,
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA_SOFT,
            }
            if extra:
                props.update(extra)
            return workbook.add_format(props)

        f_titulo = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 15,
                "font_color": "#ffffff",
                "bg_color": C_PRIMARIA,
                "align": "left",
                "valign": "vcenter",
                "indent": 1,
            }
        )
        f_subtitulo = workbook.add_format(
            {
                "font_name": "Calibri",
                "font_size": 10,
                "font_color": C_TEXT_SOFT,
                "bg_color": C_HEAD_BG,
                "align": "left",
                "valign": "vcenter",
                "indent": 1,
            }
        )
        f_legenda_prio = {
            p: workbook.add_format(
                {"font_name": "Calibri", "bold": True, "font_size": 10, "font_color": cor}
            )
            for p, cor in CORES_PRIORIDADE.items()
        }
        f_legenda_celula = workbook.add_format({"font_name": "Calibri"})

        f_head = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 9,
                "font_color": C_TEXT_SOFT,
                "bg_color": C_HEAD_BG,
                "align": "left",
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA,
                "bottom": 2,
                "bottom_color": C_BORDA,
            }
        )
        f_head_centro = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 9,
                "font_color": C_TEXT_SOFT,
                "bg_color": C_HEAD_BG,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA,
                "bottom": 2,
                "bottom_color": C_BORDA,
            }
        )
        f_head_dir = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 9,
                "font_color": C_TEXT_SOFT,
                "bg_color": C_HEAD_BG,
                "align": "right",
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA,
                "bottom": 2,
                "bottom_color": C_BORDA,
            }
        )

        f_celula = base("#ffffff")
        f_celula_alt = base(C_ROW_ALT)
        f_celula_cod = base("#ffffff", {"align": "center", "font_color": C_TEXT_SOFT})
        f_celula_cod_alt = base(C_ROW_ALT, {"align": "center", "font_color": C_TEXT_SOFT})
        f_celula_conf = base("#ffffff", {"font_color": C_TEXT_SOFT})
        f_celula_conf_alt = base(C_ROW_ALT, {"font_color": C_TEXT_SOFT})
        f_celula_num = base("#ffffff", {"align": "right", "bold": True, "num_format": "#,##0"})
        f_celula_num_alt = base(C_ROW_ALT, {"align": "right", "bold": True, "num_format": "#,##0"})
        f_celula_qe = base("#fff6e6", {"align": "right", "bold": True, "num_format": "#,##0", "font_color": "#b26a00"})
        f_celula_qe_alt = base("#fdf1dc", {"align": "right", "bold": True, "num_format": "#,##0", "font_color": "#b26a00"})
        f_head_qe = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 9,
                "font_color": "#b26a00",
                "bg_color": "#fff6e6",
                "align": "right",
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA,
                "bottom": 2,
                "bottom_color": C_BORDA,
            }
        )
        f_celula_data = base("#ffffff", {"align": "center", "num_format": "DD/MM/YYYY"})
        f_celula_data_alt = base(C_ROW_ALT, {"align": "center", "num_format": "DD/MM/YYYY"})
        f_celula_data_atraso = base(
            "#ffffff",
            {"align": "center", "num_format": "DD/MM/YYYY", "bold": True, "font_color": CORES_PRIORIDADE["Atrasado"]},
        )
        f_celula_data_atraso_alt = base(
            C_ROW_ALT,
            {"align": "center", "num_format": "DD/MM/YYYY", "bold": True, "font_color": CORES_PRIORIDADE["Atrasado"]},
        )
        f_pedido = {
            p: (
                base("#ffffff", {"left": 5, "left_color": cor}),
                base(C_ROW_ALT, {"left": 5, "left_color": cor}),
            )
            for p, cor in CORES_PRIORIDADE.items()
        }
        f_badge = {
            p: workbook.add_format(
                {
                    "font_name": "Calibri",
                    "bold": True,
                    "font_size": 10,
                    "font_color": "#ffffff",
                    "bg_color": cor,
                    "align": "center",
                    "valign": "vcenter",
                    "border": 1,
                    "border_color": C_BORDA_SOFT,
                }
            )
            for p, cor in CORES_PRIORIDADE.items()
        }

        f_total_rotulo = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 10,
                "font_color": C_TEXT,
                "bg_color": C_TOTAL_BG,
                "align": "left",
                "valign": "vcenter",
                "border": 1,
                "border_color": C_BORDA_SOFT,
                "top": 2,
                "top_color": C_BORDA,
                "indent": 1,
            }
        )
        f_total_num = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 10,
                "font_color": C_TEXT,
                "bg_color": C_TOTAL_BG,
                "align": "right",
                "valign": "vcenter",
                "num_format": "#,##0",
                "border": 1,
                "border_color": C_BORDA_SOFT,
                "top": 2,
                "top_color": C_BORDA,
            }
        )
        f_total_vazio = workbook.add_format(
            {
                "font_name": "Calibri",
                "bg_color": C_TOTAL_BG,
                "border": 1,
                "border_color": C_BORDA_SOFT,
                "top": 2,
                "top_color": C_BORDA,
            }
        )
        f_total_qe = workbook.add_format(
            {
                "font_name": "Calibri",
                "bold": True,
                "font_size": 10,
                "font_color": "#b26a00",
                "bg_color": "#fdeeda",
                "align": "right",
                "valign": "vcenter",
                "num_format": "#,##0",
                "border": 1,
                "border_color": C_BORDA_SOFT,
                "top": 2,
                "top_color": C_BORDA,
            }
        )

        # ---------- Colunas ----------
        larguras = [
            (0, 0, 13),
            (1, 1, 12),
            (2, 2, 52),
            (3, 3, 34),
            (4, 4, 12),
            (5, 5, 11),
            (6, 6, 16),
            (7, 7, 14),
        ]
        for ini, fim, larg in larguras:
            ws.set_column(ini, fim, larg)

        # ---------- Cabeçalho da folha ----------
        ws.set_row(0, 30)
        ws.merge_range(0, 0, 0, 7, f"📌 Kanban de Confecção — {confeccao}", f_titulo)

        ws.set_row(1, 18)
        ws.merge_range(
            1,
            0,
            1,
            7,
            f"Itens do Estoque localizados nos Pedidos pelo Cód Confec  ·  "
            f"Data de referência: {date.today().strftime('%d/%m/%Y')}  ·  "
            f"{n_linhas} pedido(s)  ·  {fmt_num(df_col['Saldo'].sum())} unidade(s)  ·  "
            f"Q.E: {fmt_num(df_col['Q.E'].sum())}",
            f_subtitulo,
        )

        ws.set_row(2, 18)
        contagem = df_col["Prioridade"].value_counts()
        legenda = ["Prioridade:"]
        for prio in ["Atrasado", "Alta", "Média", "Baixa"]:
            prefixo = "⚠️ " if prio == "Atrasado" else ""
            # No xlsxwriter o formato vale para o texto seguinte; a lista deve
            # terminar em texto (nunca em formato).
            legenda += [f_legenda_prio[prio], f"   {prefixo}{prio}: {int(contagem.get(prio, 0))}"]
        ws.write_rich_string(2, 0, *legenda, f_legenda_celula)

        ws.set_row(3, 6)

        # ---------- Cabeçalho da tabela ----------
        linha_head = 4
        ws.set_row(linha_head, 22)
        ws.write(linha_head, 0, "PEDIDO", f_head)
        ws.write(linha_head, 1, "CÓD CONFEC", f_head_centro)
        ws.write(linha_head, 2, "DESCRIÇÃO", f_head)
        ws.write(linha_head, 3, "CONFECÇÃO", f_head)
        ws.write(linha_head, 4, "QUANTIDADE", f_head_dir)
        ws.write(linha_head, 5, "Q.E", f_head_qe)
        ws.write(linha_head, 6, "DATA DE ENTREGA", f_head_centro)
        ws.write(linha_head, 7, "PRIORIDADE", f_head_centro)

        # ---------- Linhas ----------
        for i, (_, row) in enumerate(linhas):
            r = linha_head + 1 + i
            alt = i % 2 == 1
            prio = str(row["Prioridade"]).strip()
            prio = prio if prio in CORES_PRIORIDADE else "Baixa"
            ws.set_row(r, 20)

            f_ped, f_ped_alt = f_pedido[prio]
            compra = row["Compra"]
            try:
                num = float(compra)
                valor_pedido = int(num) if num == int(num) else num
            except (TypeError, ValueError):
                valor_pedido = fmt_compra(compra)
            ws.write(r, 0, valor_pedido, f_ped_alt if alt else f_ped)

            cod = str(row["Cód Confec"]).strip()
            valor_cod = int(cod) if cod.isdigit() else cod
            ws.write(r, 1, valor_cod, f_celula_cod_alt if alt else f_celula_cod)

            ws.write(r, 2, str(row["Confeccionado"]).strip(), f_celula_alt if alt else f_celula)
            ws.write(r, 3, str(row["Confecção"]).strip(), f_celula_conf_alt if alt else f_celula_conf)
            ws.write(r, 4, float(row["Saldo"]), f_celula_num_alt if alt else f_celula_num)
            ws.write_number(r, 5, float(row["Q.E"]), f_celula_qe_alt if alt else f_celula_qe)

            dt = row["Dt Entrega"]
            if pd.isna(dt):
                ws.write(r, 6, "—", f_celula_data_alt if alt else f_celula_data)
            else:
                atrasado = prio == "Atrasado"
                if atrasado:
                    fmt_data_cell = f_celula_data_atraso_alt if alt else f_celula_data_atraso
                else:
                    fmt_data_cell = f_celula_data_alt if alt else f_celula_data
                ws.write_datetime(r, 6, pd.Timestamp(dt).to_pydatetime(), fmt_data_cell)

            texto_prio = ("⚠️ " if prio == "Atrasado" else "") + prio
            ws.write(r, 7, texto_prio, f_badge[prio])

        # ---------- Total ----------
        linha_total = linha_head + 1 + n_linhas
        ws.set_row(linha_total, 22)
        ws.merge_range(
            linha_total, 0, linha_total, 3, f"Total — {n_linhas} item(ns)", f_total_rotulo
        )
        ws.write_number(linha_total, 4, float(df_col["Saldo"].sum()), f_total_num)
        ws.write_number(linha_total, 5, float(df_col["Q.E"].sum()), f_total_qe)
        ws.merge_range(linha_total, 6, linha_total, 7, "", f_total_vazio)

        # ---------- Aparência / impressão ----------
        ws.autofilter(linha_head, 0, linha_total - 1, 7)
        ws.freeze_panes(linha_head + 1, 0)
        ws.hide_gridlines(2)
        ws.set_landscape()
        ws.set_paper(9)
        ws.fit_to_pages(1, 0)
        ws.repeat_rows(linha_head)
        ws.set_margins(0.4, 0.4, 0.5, 0.4)
        ws.print_area(0, 0, linha_total, 7)
        ws.set_zoom(90)

        workbook.close()
        return buffer.getvalue()


    def render_acoes_conf(df_dados, confeccao):
        """Ações de UMA confecção: imprimir (nova guia), baixar HTML e baixar Excel."""
        html_conf = gerar_html_impressao(
            df_dados, incluir_resumo=False, confeccao_destaque=confeccao
        )
        b64_conf = base64.b64encode(html_conf.encode("utf-8")).decode("ascii")
        excel_conf = gerar_excel_conf(df_dados, confeccao)
        slug = re.sub(r"[^A-Za-z0-9]+", "_", str(confeccao)).strip("_").lower()[:40] or "confeccao"
        hoje = date.today().strftime("%Y-%m-%d")

        col_print, col_html, col_excel = st.columns([3, 2, 2])
        with col_print:
            st.iframe(COMPONENTE_IMPRESSAO.replace("__B64__", b64_conf), height=58)
        with col_html:
            st.download_button(
                "⬇️ Baixar HTML",
                data=html_conf,
                file_name=f"kanban_impressao_{slug}_{hoje}.html",
                mime="text/html",
                width="stretch",
                key=f"dl_html_{slug}",
            )
        with col_excel:
            st.download_button(
                "📊 Baixar Excel (.xlsx)",
                data=excel_conf,
                file_name=f"kanban_confeccao_{slug}_{hoje}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key=f"dl_excel_{slug}",
            )


    # Uma aba por confecção
    confeccoes_abas = sorted(df_filtrado["Confecção"].unique().tolist())
    abas = st.tabs([f"🏭 {conf[:30]}" for conf in confeccoes_abas])

    for aba, confeccao in zip(abas, confeccoes_abas):
        with aba:
            df_col = df_filtrado[df_filtrado["Confecção"] == confeccao]
            total_qtd = df_col["Saldo"].sum()
            qtd_atrasado = int((df_col["Prioridade"] == "Atrasado").sum())
            qtd_alta = int((df_col["Prioridade"] == "Alta").sum())
            qtd_media = int((df_col["Prioridade"] == "Média").sum())
            qtd_baixa = int((df_col["Prioridade"] == "Baixa").sum())

            st.markdown(
                f"""
                <div class="kb-tab-summary">
                    🏭 <b>{html.escape(confeccao)}</b> &nbsp;·&nbsp;
                    <b>{len(df_col)}</b> pedido(s) &nbsp;·&nbsp;
                    📦 <b>{fmt_num(total_qtd)}</b> unidade(s) &nbsp;·&nbsp;
                    🚨 Q.E <b>{fmt_num(df_col['Q.E'].sum())}</b> &nbsp;·&nbsp;
                    ⚠️ <b>{qtd_atrasado}</b> atrasado(s) &nbsp;·&nbsp;
                    🔴 <b>{qtd_alta}</b> alta(s) &nbsp;·&nbsp;
                    🟠 <b>{qtd_media}</b> média(s) &nbsp;·&nbsp;
                    🟢 <b>{qtd_baixa}</b> baixa(s)
                </div>
                """,
                unsafe_allow_html=True,
            )

            if df_col.empty:
                st.info("Nenhum pedido nesta confecção com os filtros atuais.")
            else:
                render_acoes_conf(df_col, confeccao)
                st.caption(
                    "🖨️ A nova guia abre pronta para impressão e contém **somente esta confecção** "
                    "(sugerido: **A4 paisagem**, com “Gráficos de plano de fundo” ativado). "
                    "📊 O Excel sai com a mesma formatação visual da tela (uma aba, filtros e cores por prioridade)."
                )
                st.markdown(html_sheet(df_col), unsafe_allow_html=True)

    # ==================== TABELA E EXPORTAÇÃO ====================

    st.markdown("---")
    st.markdown("### 📋 Detalhamento e exportação")

    df_tabela = df_filtrado[
        ["Compra", "Cód Confec", "Confeccionado", "Saldo", "Q.E", "Dt Entrega", "Prioridade", "Confecção"]
    ].copy()
    df_tabela = df_tabela.rename(
        columns={
            "Compra": "Pedido",
            "Saldo": "Quantidade",
            "Q.E": "Q.E (Emergencial)",
            "Dt Entrega": "Data de Entrega",
        }
    ).sort_values(["Confecção", "Data de Entrega"])

    with st.expander("📋 Ver tabela completa e interativa (todos os registros)"):
        st.dataframe(
            df_tabela,
            width="stretch",
            hide_index=True,
            column_config={
                "Pedido": st.column_config.TextColumn("Pedido", width="small"),
                "Cód Confec": st.column_config.TextColumn("Cód Confec", width="small"),
                "Confeccionado": st.column_config.TextColumn("Descrição", width="large"),
                "Quantidade": st.column_config.NumberColumn("Quantidade", format="%d"),
                "Q.E (Emergencial)": st.column_config.NumberColumn("Q.E (Emergencial)", format="%d"),
                "Data de Entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"),
                "Prioridade": st.column_config.TextColumn("Prioridade", width="small"),
                "Confecção": st.column_config.TextColumn("Confecção", width="large"),
            },
        )

    col1, col2 = st.columns(2)

    with col1:
        csv = df_tabela.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 Baixar CSV",
            data=csv,
            file_name=f"kanban_confeccao_{date.today().strftime('%Y-%m-%d')}.csv",
            width="stretch",
        )

    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_tabela.to_excel(writer, index=False, sheet_name="Kanban")
            resumo = (
                df_filtrado.groupby("Confecção")
                .agg(
                    Pedidos=("Compra", "count"),
                    Quantidade=("Saldo", "sum"),
                    QE=("Q.E", "sum"),
                )
                .reset_index()
            )
            resumo.to_excel(writer, index=False, sheet_name="Resumo")
        st.download_button(
            "📊 Baixar Excel",
            data=buffer.getvalue(),
            file_name=f"kanban_confeccao_{date.today().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
