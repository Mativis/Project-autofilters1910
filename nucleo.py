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

def tema_escuro():
    """True se o aplicativo está em tema escuro.

    ``st.context.theme.type`` considera a preferência de cor do **navegador**
    (e não o tema escolhido no Streamlit), por isso consultamos primeiro a
    opção ``theme.base``, que respeita o tema selecionado no menu de
    configurações e o ``[theme] base`` do ``config.toml``.
    """
    try:
        base = st.get_option("theme.base")
        if base in ("dark", "light"):
            return base == "dark"
    except Exception:
        pass
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def template_plotly():
    """Template do Plotly conforme o tema em uso."""
    return "plotly_dark" if tema_escuro() else "plotly_white"


def cores_grafico():
    """Paleta de cores usada nos gráficos."""
    return [
        "#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444",
        "#ec4899", "#14b8a6", "#f97316", "#84cc16", "#3b82f6", "#a855f7",
    ]

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
        'Tec Faz "x" Confec',
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
    if tema_escuro():
        return {
            "surface": "#0f1623",
            "surface-2": "#131c2e",
            "border": "#1e293b",
            "text": "#e2e8f0",
            "text_soft": "#94a3b8",
            "chip": "#1e293b",
            "shadow": "rgba(0, 0, 0, 0.4)",
            "pos": "#22c55e",
            "neg": "#ef4444",
            "warn": "#f59e0b",
            "accent": "#6366f1",
            "accent-2": "#8b5cf6",
        }
    return {
        "surface": "#ffffff",
        "surface-2": "#f8fafc",
        "border": "#e2e8f0",
        "text": "#0f172a",
        "text_soft": "#64748b",
        "chip": "#f1f5f9",
        "shadow": "rgba(15, 23, 42, 0.04)",
        "pos": "#16a34a",
        "neg": "#dc2626",
        "warn": "#d97706",
        "accent": "#6366f1",
        "accent-2": "#8b5cf6",
    }


CSS_COMUM = """
    :root {
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    /* Modern Header */
    .db-header {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
        color: #ffffff;
        padding: 2rem 2.5rem;
        border-radius: var(--radius-lg);
        margin-bottom: 2rem;
        box-shadow: 0 20px 60px -20px rgba(99, 102, 241, 0.5);
        position: relative;
        overflow: hidden;
    }
    .db-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
        border-radius: 50%;
    }
    .db-header::after {
        content: '';
        position: absolute;
        bottom: -30%;
        left: -5%;
        width: 200px;
        height: 200px;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        border-radius: 50%;
    }
    .db-header h1 { 
        margin: 0; 
        font-size: 1.8rem; 
        font-weight: 800; 
        letter-spacing: -0.02em;
        position: relative; 
        z-index: 1; 
    }
    .db-header p { 
        margin: 0.5rem 0 0 0; 
        font-size: 0.95rem; 
        opacity: 0.95; 
        position: relative; 
        z-index: 1;
        font-weight: 500;
    }
    
    /* Modern Cards */
    [data-testid="stMetric"] {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--radius-md);
        padding: 1.25rem 1.5rem;
        box-shadow: 0 1px 3px var(--db-shadow);
        transition: all 0.2s ease;
        height: 100%;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 12px var(--db-shadow);
        border-color: rgba(99, 102, 241, 0.3);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 700 !important;
        color: var(--db-text-soft) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: var(--db-text) !important;
        letter-spacing: -0.02em;
    }
    
    /* Container with border */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--radius-md);
        box-shadow: 0 1px 3px var(--db-shadow);
        padding: 1.5rem;
        transition: all 0.2s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 12px var(--db-shadow);
    }
    
    /* Section Headers */
    .db-secao {
        font-size: 1.25rem; 
        font-weight: 800; 
        color: var(--db-text);
        margin: 2.5rem 0 1rem 0; 
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Alerts */
    .db-aviso {
        background: linear-gradient(90deg, rgba(99, 102, 241, 0.08) 0%, transparent 100%);
        border-left: 3px solid #6366f1;
        border-radius: var(--radius-sm);
        padding: 0.75rem 1rem;
        font-size: 0.875rem; 
        color: var(--db-text-soft);
        margin: 1rem 0;
    }
    
    /* File upload status */
    .db-file-ok {
        background: linear-gradient(90deg, rgba(34, 197, 94, 0.08) 0%, transparent 100%);
        border-left: 3px solid #22c55e;
        border-radius: var(--radius-sm);
        padding: 0.6rem 0.9rem; 
        font-size: 0.875rem;
        color: var(--db-text); 
        margin-bottom: 0.5rem;
    }
    .db-file-name {
        display: block; 
        font-size: 0.75rem; 
        color: var(--db-text-soft);
        overflow: hidden; 
        text-overflow: ellipsis; 
        white-space: nowrap;
        margin-top: 0.25rem;
    }
    
    /* Dataframes */
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--db-border);
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: var(--radius-sm);
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: var(--db-surface-2);
        padding: 0.375rem;
        border-radius: var(--radius-md);
        border: 1px solid var(--db-border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-sm);
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--radius-md);
        font-weight: 600;
    }
"""


def aplicar_estilo_comum():
    """Injeta o CSS compartilhado (cards, cabeçalho, seções) na página."""
    cores = _cores_pagina()
    variaveis = (
        ":root{"
        f"--db-surface:{cores['surface']};"
        f"--db-surface-2:{cores.get('surface-2', cores['chip'])};"
        f"--db-border:{cores['border']};"
        f"--db-text:{cores['text']};--db-text-soft:{cores['text_soft']};"
        f"--db-chip:{cores['chip']};--db-shadow:{cores['shadow']};"
        f"--db-pos:{cores['pos']};--db-neg:{cores['neg']};--db-warn:{cores['warn']};"
        f"--db-accent:{cores.get('accent', '#6366f1')};"
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
