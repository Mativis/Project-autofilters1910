"""
Núcleo compartilhado pelas páginas do sistema:

    app.py                       -> ponto de entrada (st.navigation)
    kanban_confeccao.py          -> Kanban de Confecção
    paginas/dashboards.py        -> Dashboards de Pedidos
    paginas/analise_estoque.py   -> Análise de Estoque por item

Concentra: leitura dos arquivos, normalização dos dados, regras de
prioridade, formatação e os *uploaders* (compartilhados via session_state,
para que os arquivos sejam enviados uma única vez e valham para todas as
páginas).
"""

import html
import io
import math
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

# ==================== TEMA (claro / escuro) ====================

try:
    _tema_atual = st.context.theme.type
except Exception:
    _tema_atual = None

TEMA_ESCURO = _tema_atual == "dark"

TEMPLATE_PLOTLY = "plotly_dark" if TEMA_ESCURO else "plotly_white"

CORES_GRAFICO = (
    ["#667eea", "#764ba2", "#f44336", "#ff9800", "#4caf50", "#00bcd4",
     "#e91e63", "#795548", "#607d8b", "#9c27b0", "#009688", "#cddc39"]
    if TEMA_ESCURO
    else ["#667eea", "#764ba2", "#f44336", "#ff9800", "#4caf50", "#00bcd4",
          "#e91e63", "#795548", "#607d8b", "#9c27b0", "#009688", "#cddc39"]
)

# ==================== CONSTANTES ====================

COLUNAS_PEDIDOS = [
    "Compra",
    "Cód Confec",
    "Confeccionado",
    "Qtd",
    "Saldo",
    "Dt Entrega",
    "Confecção",
]

COLUNAS_ESTOQUE = ["Cód Confec", "Saldo 1", "Saldo 2", "Saldo 3"]

ORDEM_PRIORIDADE = {"Atrasado": 0, "Alta": 1, "Média": 2, "Baixa": 3}

CORES_PRIORIDADE = {
    "Atrasado": "#b71c1c",
    "Alta": "#f44336",
    "Média": "#ff9800",
    "Baixa": "#4caf50",
}

FATOR_URGENCIA_PADRAO = 1.10
LIMITE_SALDO_BAIXO = 0.04


# ==================== LEITURA E NORMALIZAÇÃO ====================

@st.cache_data
def load_excel(file):
    """Carrega um arquivo Excel com cache.

    Aceita um objeto com ``read`` (UploadedFile) ou os bytes do arquivo.
    """
    try:
        if isinstance(file, (bytes, bytearray)):
            df = pd.read_excel(io.BytesIO(file))
        else:
            df = pd.read_excel(file)
    except ImportError as erro:  # xlrd ausente (arquivos .xls)
        raise ImportError(
            "Não foi possível ler arquivos .xls (falta a biblioteca 'xlrd'). "
            "Salve a planilha como .xlsx ou instale o xlrd."
        ) from erro
    df.columns = df.columns.str.strip()
    return df


def normalizar_cod(valor):
    """Normaliza o código da confecção para string comparável (ex.: 23012.0 -> '23012')"""
    if pd.isna(valor):
        return ""
    try:
        num = float(valor)
        if num == int(num):
            return str(int(num))
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


# ==================== PRIORIDADE E FORMATAÇÃO ====================

def calcular_prioridade(dt_entrega):
    """
    Define a prioridade com base na data de entrega:
    - Data de entrega já vencida.................: Atrasado
    - Faltar mais de 1 mês (> 30 dias)..........: Baixa
    - Entre 15 e 30 dias........................: Média
    - Menos de 15 dias..........................: Alta
    """
    if pd.isna(dt_entrega):
        return "Baixa"
    dias = (pd.Timestamp(dt_entrega).normalize().date() - date.today()).days
    if dias < 0:
        return "Atrasado"
    if dias > 30:
        return "Baixa"
    if dias > 15:
        return "Média"
    return "Alta"


def classe_prioridade(prioridade):
    return {
        "Atrasado": "atrasado",
        "Alta": "alta",
        "Média": "media",
        "Baixa": "baixa",
    }.get(prioridade, "baixa")


def texto_dias(dt_entrega):
    """Texto informativo sobre o prazo de entrega"""
    if pd.isna(dt_entrega):
        return "⏰ Sem data de entrega"
    dias = (pd.Timestamp(dt_entrega).normalize().date() - date.today()).days
    if dias < 0:
        return f"⚠️ Atrasado há {-dias} dia(s)"
    if dias == 0:
        return "⏰ Entrega hoje!"
    return f"⏰ Faltam {dias} dia(s)"


def fmt_num(valor):
    """Formata número no padrão brasileiro (milhar com ponto)"""
    try:
        if pd.isna(valor):
            return "—"
        return f"{float(valor):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def fmt_pct(valor, casas=1):
    """Formata percentual no padrão brasileiro"""
    try:
        if pd.isna(valor):
            return "—"
        return f"{float(valor) * 100:,.{casas}f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def fmt_compra(valor):
    """Formata o número da compra sem casas decimais"""
    try:
        if pd.isna(valor):
            return "—"
        num = float(valor)
        return str(int(num)) if num == int(num) else str(num)
    except (TypeError, ValueError):
        return str(valor)


def fmt_data(valor):
    if pd.isna(valor):
        return "—"
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


# ==================== UPLOAD COMPARTILHADO ====================

KEY_EPOCH_ARQUIVOS = "epoch_arquivos"


def _salvar_arquivo(tag, uploaded):
    """Guarda o conteúdo do arquivo na sessão.

    O conteúdo fica em uma chave que **não** é de widget, porque o valor de um
    ``st.file_uploader`` se perde ao trocar de página. Assim, o upload feito
    uma única vez continua valendo no Kanban e nos dashboards.
    """
    dados = uploaded.getvalue()
    st.session_state[f"bytes_{tag}"] = dados
    st.session_state[f"nome_{tag}"] = uploaded.name
    st.session_state[f"sig_{tag}"] = (uploaded.name, len(dados))
    st.session_state.pop(f"df_{tag}", None)


def _limpar_arquivo(tag):
    """Esquece o arquivo (e o DataFrame carregado) de um tipo de planilha."""
    for sufixo in ("bytes", "nome", "sig", "df"):
        st.session_state.pop(f"{sufixo}_{tag}", None)


def _carregar_arquivo(tag):
    """Carrega (e memoriza na sessão) o DataFrame do arquivo já enviado."""
    dados = st.session_state.get(f"bytes_{tag}")
    if dados is None:
        return None
    nome = st.session_state.get(f"nome_{tag}") or ""
    assinatura = (nome, len(dados))
    if st.session_state.get(f"sig_{tag}") == assinatura and f"df_{tag}" in st.session_state:
        return st.session_state[f"df_{tag}"]
    df = load_excel(dados)
    st.session_state[f"df_{tag}"] = df
    st.session_state[f"sig_{tag}"] = assinatura
    return df


def sidebar_arquivos(mostrar_ajuda=True):
    """Uploaders na barra lateral (compartilhados entre as páginas).

    Quando o arquivo já está carregado, a barra lateral mostra o nome do
    arquivo e um botão para trocá-lo — os dados continuam disponíveis em
    todas as páginas do sistema.

    Devolve ``(df_pedidos, df_estoque)`` — ou ``(None, None)`` se faltar arquivo.
    """
    recarregar = False
    epoch = st.session_state.get(KEY_EPOCH_ARQUIVOS, 0)

    with st.sidebar:
        st.header("📁 Arquivos")

        for tag, rotulo, ajuda in (
            (
                "pedidos",
                "Pedidos",
                "Colunas usadas: Compra, Cód Confec, Confeccionado, Qtd, Saldo, "
                "Dt Entrega, Confecção, Marca, Status, Dt Emissao.",
            ),
            (
                "estoque",
                "Estoque",
                "Colunas usadas: Cód Confec, Saldo 1 (físico), Saldo 2 (+ trânsito), "
                "Saldo 3 (+ confecção), Marca, Descrição.",
            ),
        ):
            nome = st.session_state.get(f"nome_{tag}")
            if nome:
                st.markdown(
                    f'<div class="db-file-ok">✅ <b>{rotulo}</b>'
                    f'<span class="db-file-name">{html.escape(nome)}</span></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"🔄 Trocar {rotulo.lower()}",
                    key=f"btn_trocar_{tag}",
                ):
                    _limpar_arquivo(tag)
                    st.session_state[KEY_EPOCH_ARQUIVOS] = epoch + 1
                    recarregar = True
            else:
                uploaded = st.file_uploader(
                    f"Arquivo de **{rotulo}** (.xlsx)",
                    type=["xlsx", "xls"],
                    key=f"upload_{tag}_{epoch}",
                    help=ajuda,
                )
                if uploaded is not None:
                    _salvar_arquivo(tag, uploaded)
                    recarregar = True

        if mostrar_ajuda:
            st.caption(
                "ℹ️ Os arquivos enviados aqui ficam disponíveis em **todas** as páginas "
                "do sistema — não é preciso enviar de novo."
            )

    if recarregar:
        st.rerun()

    return (
        _carregar_arquivo("pedidos"),
        _carregar_arquivo("estoque"),
    )


# ==================== PREPARAÇÃO DOS DADOS ====================

def _texto(valor, padrao):
    texto = "" if valor is None else str(valor).strip()
    return texto if texto else padrao


def preparar_pedidos(df):
    """Normaliza o DataFrame de Pedidos (tipos, datas, textos e colunas calculadas)."""
    df = df.copy()
    # Nomes de colunas com acento são padronizados (ex.: 'Dt Emissão' -> 'Dt Emissao')
    for antes, depois in (("Dt Emissão", "Dt Emissao"), ("Dt Emissao ", "Dt Emissao")):
        if antes in df.columns and depois not in df.columns:
            df = df.rename(columns={antes: depois})
    df["Cód Confec_norm"] = df["Cód Confec"].map(normalizar_cod)
    df["Dt Entrega"] = pd.to_datetime(df["Dt Entrega"], errors="coerce")
    if "Dt Emissao" in df.columns:
        df["Dt Emissao"] = pd.to_datetime(df["Dt Emissao"], errors="coerce")
    for coluna in ["Qtd", "Saldo", "Qtd Ret"]:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    df["Confecção"] = df["Confecção"].map(lambda v: _texto(v, "Sem Confecção"))
    df["Confeccionado"] = df["Confeccionado"].map(lambda v: _texto(v, ""))
    if "Marca" in df.columns:
        df["Marca"] = df["Marca"].map(lambda v: _texto(v, "Sem Marca"))
    else:
        df["Marca"] = "Sem Marca"
    if "Status" in df.columns:
        df["Status"] = df["Status"].map(lambda v: _texto(v, "Sem Status"))
    else:
        df["Status"] = "Sem Status"
    df["Prioridade"] = df["Dt Entrega"].apply(calcular_prioridade)
    # Eficácia: quanto do pedido continua em aberto (Saldo ÷ Qtd)
    df["Eficacia"] = np.where(df["Qtd"] > 0, df["Saldo"] / df["Qtd"], np.nan)
    return df


def preparar_estoque(df):
    """Normaliza o DataFrame de Estoque (tipos numéricos e textos)."""
    df = df.copy()
    df["Cód Confec_norm"] = df["Cód Confec"].map(normalizar_cod)
    for coluna in [
        "Saldo 1",
        "Saldo 2",
        "Saldo 3",
        "Saldo 4",
        "Saldo 5",
        "Em Trânsito",
        "Em Confecção",
        "Carteira sem Fat",
        "Empenhado",
        "Estoque",
        "Saldo Compra",
        "Qtd. Cortado",
    ]:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    if "Marca" in df.columns:
        df["Marca"] = df["Marca"].map(lambda v: _texto(v, "Sem Marca"))
    else:
        df["Marca"] = "Sem Marca"
    if "Descrição" in df.columns:
        df["Descrição"] = df["Descrição"].map(lambda v: _texto(v, ""))
    else:
        df["Descrição"] = ""
    for coluna, padrao in [("Situação", "Sem Situação"), ("Coleção", "Sem Coleção"),
                           ("Segmento", "Sem Segmento"), ("Tipo Produto", "Sem Tipo")]:
        if coluna in df.columns:
            df[coluna] = df[coluna].map(lambda v, p=padrao: _texto(v, p))
    return df


def codigos_saldo2_negativo(df_estoque):
    """Códigos de confecção com Saldo 2 negativo (físico + em trânsito)."""
    saldo2 = pd.to_numeric(df_estoque["Saldo 2"], errors="coerce")
    return set(df_estoque.loc[saldo2 < 0, "Cód Confec"].map(normalizar_cod)) - {""}


def saldo2_por_codigo(df_estoque):
    """Mapa {código: Saldo 2} do Estoque (para cálculo da Q.E)."""
    saldo2 = pd.to_numeric(df_estoque["Saldo 2"], errors="coerce")
    mapa = {}
    for cod, valor in zip(df_estoque["Cód Confec"].map(normalizar_cod), saldo2):
        if cod and pd.notna(valor):
            mapa[cod] = float(valor)
    return mapa


# ==================== ESTILO COMUM DAS PÁGINAS ====================

def _cores_pagina():
    if TEMA_ESCURO:
        return {
            "surface": "#1a2332",
            "border": "#2d3a4f",
            "text": "#e7ecf3",
            "text_soft": "#a9b8cf",
            "chip": "#243044",
            "shadow": "rgba(0, 0, 0, 0.55)",
            "pos": "#4caf50",
            "neg": "#f44336",
            "warn": "#ff9800",
        }
    return {
        "surface": "#ffffff",
        "border": "#d9dfec",
        "text": "#3d4455",
        "text_soft": "#5a6172",
        "chip": "#f0f2f8",
        "shadow": "rgba(0, 0, 0, 0.06)",
        "pos": "#2e7d32",
        "neg": "#c62828",
        "warn": "#ef6c00",
    }


CSS_COMUM = """
    .db-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff;
        padding: 1.4rem 2rem;
        border-radius: 15px;
        margin-bottom: 1.2rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    .db-header h1 { margin: 0; font-size: 1.55rem; }
    .db-header p { margin: .35rem 0 0 0; font-size: .88rem; opacity: .92; }
    .db-card {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 12px;
        padding: .85rem 1rem;
        box-shadow: 0 2px 10px var(--db-shadow);
    }
    .db-card .db-titulo {
        font-size: .68rem; text-transform: uppercase; letter-spacing: .06em;
        color: var(--db-text-soft); font-weight: 800; margin-bottom: .3rem;
    }
    .db-card .db-valor { font-size: 1.4rem; font-weight: 800; color: var(--db-text); }
    .db-card .db-nota { font-size: .76rem; color: var(--db-text-soft); margin-top: .15rem; }
    .db-secao {
        font-size: 1.08rem; font-weight: 800; color: var(--db-text);
        margin: 1.5rem 0 .4rem 0; border-left: 4px solid #667eea; padding-left: .6rem;
    }
    .db-aviso {
        background: var(--db-chip); border: 1px solid var(--db-border);
        border-radius: 10px; padding: .6rem .9rem; font-size: .82rem; color: var(--db-text-soft);
    }
    .db-file-ok {
        background: var(--db-chip); border: 1px solid var(--db-border);
        border-radius: 10px; padding: .5rem .75rem; font-size: .82rem;
        color: var(--db-text); margin-bottom: .35rem;
    }
    .db-file-name {
        display: block; font-size: .74rem; color: var(--db-text-soft);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
"""


def aplicar_estilo_comum():
    """Injeta o CSS compartilhado (cards, cabeçalho, seções) na página."""
    cores = _cores_pagina()
    variaveis = (
        ":root{"
        f"--db-surface:{cores['surface']};--db-border:{cores['border']};"
        f"--db-text:{cores['text']};--db-text-soft:{cores['text_soft']};"
        f"--db-chip:{cores['chip']};--db-shadow:{cores['shadow']};"
        f"--db-pos:{cores['pos']};--db-neg:{cores['neg']};--db-warn:{cores['warn']};"
        "}"
    )
    st.markdown(f"<style>{variaveis}{CSS_COMUM}</style>", unsafe_allow_html=True)


def card(titulo, valor, nota="", cor=None):
    """Monta um card de KPI em HTML."""
    estilo = f"color:{cor};" if cor else ""
    nota_html = f'<div class="db-nota">{nota}</div>' if nota else ""
    return (
        '<div class="db-card">'
        f'<div class="db-titulo">{titulo}</div>'
        f'<div class="db-valor" style="{estilo}">{valor}</div>'
        f"{nota_html}"
        "</div>"
    )


def cabecalho(titulo, subtitulo=""):
    """Cabeçalho das páginas de dashboard."""
    sub = f"<p>{subtitulo}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="db-header"><h1>{titulo}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


# ==================== QUANTIDADE EMERGENCIAL (Q.E) ====================

def calcular_qe(saldo2, saldo_pedido, fator=FATOR_URGENCIA_PADRAO):
    """Quantidade Emergencial.

    ``Q.E = |Saldo 2| × fator`` (arredondado para cima), limitada pela
    **Quantidade em aberto do pedido** (``Saldo``): nunca se produz mais do
    que o pedido exige.
    """
    if pd.isna(saldo2) or pd.isna(saldo_pedido):
        return 0
    bruto = math.ceil(abs(float(saldo2)) * float(fator))
    teto = int(max(0, float(saldo_pedido)))
    return int(max(0, min(bruto, teto)))
