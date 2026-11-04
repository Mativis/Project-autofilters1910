"""Geração do PDF da listagem de compra sugerida (Análise de Estoque).

O módulo não depende do Streamlit: recebe o DataFrame já filtrado e ordenado
pela página e devolve os bytes do PDF. Isso mantém a geração testável e evita
misturar layout de documento com a interface.
"""

from __future__ import annotations

import html
import io
from datetime import date, datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PAGINA = landscape(A4)  # A4 paisagem: 297 x 210 mm
MARGEM_LATERAL = 10 * mm
MARGEM_SUPERIOR = 24 * mm
MARGEM_INFERIOR = 15 * mm
ESPACO_RODAPE = 7 * mm

COR_TEXTO = colors.HexColor("#0f172a")
COR_MUTED = colors.HexColor("#64748b")
COR_BORDA = colors.HexColor("#e2e8f0")
COR_ZEBRA = colors.HexColor("#f8fafc")
COR_PRIMARIA = colors.HexColor("#4f46e5")
COR_PRIMARIA_ESCURA = colors.HexColor("#312e81")
COR_PRIMARIA_CLARA = colors.HexColor("#eef2ff")
COR_CABECALHO = colors.HexColor("#1e293b")
COR_DESTAQUE = colors.HexColor("#b45309")
COR_PERIGO = colors.HexColor("#b42318")
COR_OK = colors.HexColor("#047857")
COR_AVISO = colors.HexColor("#a16207")

# (coluna do DataFrame, título no PDF, largura fixa em mm, tipo)
COLUNAS = [
    ("Marca", "Marca", 21, "texto"),
    ("Cód Confec", "Cód.<br/>confec.", 19, "texto"),
    ("Descrição", "Descrição do item", None, "texto"),
    ("Tamanho", "Tam.", 21, "centro"),
    ("Saldo 5", "Saldo 5<br/>projetado", 14, "numero"),
    ('Tec Faz "x" Confec', "Teto<br/>Tec × Conf.", 16, "numero"),
    ("Compra Sugerida Bruta", "Bruta<br/>|S5| × 1,1", 17, "numero"),
    ("Compra Sugerida", "Compra<br/>sugerida", 19, "numero"),
    ("Saldo 1", "Saldo 1<br/>físico", 13, "numero"),
    ("Saldo 2", "Saldo 2<br/>+ trânsito", 14, "numero"),
    ("Saldo 3", "Saldo 3<br/>+ confec.", 13, "numero"),
    ("Demanda", "Demanda<br/>aberta", 14, "numero"),
    ("Situação do item", "Situação", 22, "situacao"),
]

# A planilha usa rótulos longos com emoji; no PDF cabem versões curtas.
SITUACOES = (
    ("sem cobertura", "Sem cobertura", COR_PERIGO),
    ("só pela confecção", "Confecção", COR_DESTAQUE),
    ("só pelo trânsito", "Trânsito", COR_AVISO),
    ("coberto pelo físico", "Coberto", COR_OK),
    ("sem dados", "Sem dados", COR_MUTED),
)

SUBSTITUICOES = {
    "\u00a0": " ",
    "\u2026": "...",
}

ESTILO_ROTULO_KPI = ParagraphStyle(
    "pdf_rotulo_kpi",
    fontName="Helvetica-Bold",
    fontSize=6.6,
    leading=8,
    textColor=COR_MUTED,
)
ESTILO_VALOR_KPI = ParagraphStyle(
    "pdf_valor_kpi",
    fontName="Helvetica-Bold",
    fontSize=14.5,
    leading=17,
    textColor=COR_PRIMARIA_ESCURA,
)
ESTILO_LEGENDA = ParagraphStyle(
    "pdf_legenda",
    fontName="Helvetica",
    fontSize=7.3,
    leading=9.6,
    textColor=COR_MUTED,
)
ESTILO_CABECALHO = ParagraphStyle(
    "pdf_cabecalho",
    fontName="Helvetica-Bold",
    fontSize=6.8,
    leading=8.1,
    alignment=TA_CENTER,
    textColor=colors.white,
)
ESTILO_CELULA = ParagraphStyle(
    "pdf_celula",
    fontName="Helvetica",
    fontSize=8,
    leading=9.6,
    textColor=COR_TEXTO,
)
ESTILO_CELULA_CENTRO = ParagraphStyle(
    "pdf_celula_centro",
    parent=ESTILO_CELULA,
    alignment=TA_CENTER,
)
ESTILO_NUMERO = ParagraphStyle(
    "pdf_numero",
    fontName="Helvetica",
    fontSize=8,
    leading=9.6,
    alignment=TA_RIGHT,
    textColor=COR_TEXTO,
)
ESTILO_TOTAL = ParagraphStyle(
    "pdf_total",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=9.6,
    alignment=TA_RIGHT,
    textColor=COR_PRIMARIA_ESCURA,
)
ESTILO_TOTAL_ROTULO = ParagraphStyle(
    "pdf_total_rotulo",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=9.6,
    alignment=TA_LEFT,
    textColor=COR_PRIMARIA_ESCURA,
)


def _pdf_texto(valor):
    """Texto seguro para o PDF: normaliza espaços, preserva acentos e escapa."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass

    texto = str(valor)
    for original, substituto in SUBSTITUICOES.items():
        texto = texto.replace(original, substituto)
    texto = " ".join(texto.split())
    # Helvetica usa WinAnsi/cp1252; o que não couber (emojis) é descartado.
    texto = texto.encode("cp1252", "ignore").decode("cp1252")
    return html.escape(texto)


def _pdf_numero(valor):
    """Número no padrão brasileiro para as células do PDF."""
    try:
        if pd.isna(valor):
            return "-"
        numero = float(valor)
    except (TypeError, ValueError):
        return _pdf_texto(valor) or "-"
    if numero == int(numero):
        return f"{int(numero):,}".replace(",", ".")
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _numero(valor):
    """Converte para float sem lançar exceção (para comparações)."""
    try:
        if pd.isna(valor):
            return 0.0
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _texto_tamanho(valor):
    """Quebra faixas de medida em duas linhas centralizadas (ex.: cortinas)."""
    texto = _pdf_texto(valor) or "-"
    if texto.startswith("De ") and " até " in texto:
        inicio, fim = texto.split(" até ", 1)
        return f"{inicio}<br/>até {fim}"
    return texto


def _situacao(valor):
    """Rótulo curto e colorido para a situação do item."""
    texto = _pdf_texto(valor) or "Sem dados"
    chave = texto.casefold()
    for procurado, rotulo, cor in SITUACOES:
        if procurado in chave:
            return Paragraph(f'<font color="#{cor.hexval()[2:]}">{rotulo}</font>', ESTILO_CELULA)
    return Paragraph(texto, ESTILO_CELULA)


class _CanvasPaginado(canvas.Canvas):
    """Canvas que só descobre o total de páginas depois de montar o documento."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estados = []

    def showPage(self):
        self._estados.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._estados)
        for estado in self._estados:
            self.__dict__.update(estado)
            self._numero_pagina(total)
            super().showPage()
        super().save()

    def _numero_pagina(self, total):
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(COR_MUTED)
        self.drawRightString(
            PAGINA[0] - MARGEM_LATERAL,
            ESPACO_RODAPE,
            f"Página {self._pageNumber} de {total}",
        )
        self.restoreState()


def _desenhar_cabecalho(canv, _documento, data_referencia, primeira):
    largura, altura = PAGINA
    canv.saveState()

    # Faixa de acento no topo da página.
    canv.setFillColor(COR_PRIMARIA)
    canv.rect(0, altura - 3 * mm, largura, 3 * mm, stroke=0, fill=1)

    canv.setFillColor(COR_TEXTO)
    canv.setFont("Helvetica-Bold", 17 if primeira else 11)
    titulo = "Compra sugerida" if primeira else "Compra sugerida · continuação"
    canv.drawString(MARGEM_LATERAL, altura - 13.2 * mm, titulo)

    if primeira:
        canv.setFont("Helvetica", 8.3)
        canv.setFillColor(COR_MUTED)
        canv.drawString(
            MARGEM_LATERAL,
            altura - 18.4 * mm,
            "Listagem para reposição de estoque",
        )

    canv.setFont("Helvetica-Bold", 8.4)
    canv.setFillColor(COR_TEXTO)
    canv.drawRightString(
        largura - MARGEM_LATERAL,
        altura - 12.2 * mm,
        "Análise de Estoque",
    )
    canv.setFont("Helvetica", 8)
    canv.setFillColor(COR_MUTED)
    canv.drawRightString(
        largura - MARGEM_LATERAL,
        altura - 16.8 * mm,
        f"Referência: {data_referencia}",
    )

    canv.setStrokeColor(COR_BORDA)
    canv.setLineWidth(0.7)
    canv.line(
        MARGEM_LATERAL,
        altura - 21 * mm,
        largura - MARGEM_LATERAL,
        altura - 21 * mm,
    )
    canv.restoreState()


def _desenhar_rodape(canv, _documento, gerado_em):
    canv.saveState()
    canv.setFont("Helvetica", 7)
    canv.setFillColor(COR_MUTED)
    canv.drawString(MARGEM_LATERAL, ESPACO_RODAPE, "Sistema de Confecção · Análise de Estoque")
    canv.drawCentredString(
        PAGINA[0] / 2,
        ESPACO_RODAPE,
        f"Gerado em {gerado_em}",
    )
    canv.restoreState()


def _tabela_resumo(qtd, total_sugerida, total_bruta, largura):
    rotulos = ("ITENS COM SUGESTÃO", "TOTAL SUGERIDO", "TOTAL BRUTO")
    valores = (
        f"{qtd}",
        f"{_pdf_numero(total_sugerida)} un",
        f"{_pdf_numero(total_bruta)} un",
    )
    celulas = [
        [Paragraph(rotulo, ESTILO_ROTULO_KPI), Paragraph(valor, ESTILO_VALOR_KPI)]
        for rotulo, valor in zip(rotulos, valores)
    ]

    tabela = Table([celulas], colWidths=[largura / 3] * 3)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COR_ZEBRA),
                ("BOX", (0, 0), (-1, -1), 0.5, COR_BORDA),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, COR_BORDA),
                ("LINEABOVE", (0, 0), (-1, 0), 2, COR_PRIMARIA),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tabela


def _colunas_e_larguras(df, largura_disponivel):
    colunas = [coluna for coluna in COLUNAS if coluna[0] in df.columns]
    if not colunas:
        colunas = [COLUNAS[2]]  # Descrição: mantém o documento válido
    largura_fixa = sum(largura for _, _, largura, _ in colunas if largura) * mm
    largura_descricao = max(48 * mm, largura_disponivel - largura_fixa)
    larguras = [
        largura * mm if largura else largura_descricao
        for _, _, largura, _ in colunas
    ]
    # Garante que a tabela nunca ultrapasse a área útil da página.
    excesso = sum(larguras) - largura_disponivel
    if excesso > 0:
        indice_descricao = next(
            i for i, (_, _, largura, _) in enumerate(colunas) if largura is None
        )
        larguras[indice_descricao] = max(40 * mm, larguras[indice_descricao] - excesso)
    return colunas, larguras


def _linha_total(colunas, total_bruta, total_sugerida):
    linha = [""] * len(colunas)
    linha[0] = Paragraph("TOTAL GERAL", ESTILO_TOTAL_ROTULO)
    for indice, (coluna, _, _, _) in enumerate(colunas):
        if coluna == "Compra Sugerida Bruta":
            linha[indice] = Paragraph(_pdf_numero(total_bruta), ESTILO_TOTAL)
        elif coluna == "Compra Sugerida":
            linha[indice] = Paragraph(_pdf_numero(total_sugerida), ESTILO_TOTAL)
    return linha


def gerar_pdf_compra_sugerida(df_pdf, data_referencia=None):
    """Gera a listagem de compra sugerida em PDF (A4 paisagem)."""
    if data_referencia is None:
        data_referencia = date.today().strftime("%d/%m/%Y")
    elif isinstance(data_referencia, (date, datetime)):
        data_referencia = data_referencia.strftime("%d/%m/%Y")
    else:
        data_referencia = str(data_referencia)

    if df_pdf is None:
        df_pdf = pd.DataFrame()
    else:
        df_pdf = df_pdf.copy()

    def soma(nome):
        if nome not in df_pdf.columns:
            return 0
        return pd.to_numeric(df_pdf[nome], errors="coerce").fillna(0).sum()

    total_sugerida = soma("Compra Sugerida")
    total_bruta = soma("Compra Sugerida Bruta")
    qtd_itens = int(len(df_pdf))
    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=PAGINA,
        leftMargin=MARGEM_LATERAL,
        rightMargin=MARGEM_LATERAL,
        topMargin=MARGEM_SUPERIOR,
        bottomMargin=MARGEM_INFERIOR,
        title="Compra Sugerida - Análise de Estoque",
        author="Sistema de Confecção",
        subject="Listagem de compra sugerida para reposição de estoque",
    )

    colunas, larguras = _colunas_e_larguras(df_pdf, documento.width)

    dados = [[Paragraph(titulo, ESTILO_CABECALHO) for _, titulo, _, _ in colunas]]
    for _, linha_df in df_pdf.iterrows():
        bruta = _numero(linha_df.get("Compra Sugerida Bruta"))
        sugerida = _numero(linha_df.get("Compra Sugerida"))
        linha = []
        for coluna, _, _, tipo in colunas:
            valor = linha_df.get(coluna)
            if tipo == "numero":
                numero = _pdf_numero(valor)
                if coluna == "Saldo 5" and _numero(valor) < 0:
                    linha.append(
                        Paragraph(f'<font color="#b42318">{numero}</font>', ESTILO_NUMERO)
                    )
                elif coluna == "Compra Sugerida":
                    if sugerida > 0 and bruta > 0 and sugerida < bruta:
                        # Teto "Tec Faz x Confec" aplicado: sinaliza em âmbar.
                        linha.append(
                            Paragraph(
                                f'<b><font color="#b45309">{numero}</font></b>',
                                ESTILO_NUMERO,
                            )
                        )
                    else:
                        linha.append(
                            Paragraph(
                                f'<b><font color="#312e81">{numero}</font></b>',
                                ESTILO_NUMERO,
                            )
                        )
                else:
                    linha.append(numero)
            elif tipo == "situacao":
                linha.append(_situacao(valor))
            elif tipo == "centro":
                linha.append(
                    Paragraph(_texto_tamanho(valor), ESTILO_CELULA_CENTRO)
                )
            else:
                linha.append(Paragraph(_pdf_texto(valor) or "-", ESTILO_CELULA))
        dados.append(linha)

    if not df_pdf.empty:
        dados.append(_linha_total(colunas, total_bruta, total_sugerida))

    estilo_tabela = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), COR_CABECALHO),
            ("BOX", (0, 0), (-1, -1), 0.5, COR_BORDA),
            ("GRID", (0, 0), (-1, -1), 0.3, COR_BORDA),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COR_ZEBRA]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 2.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
        ]
    )
    for indice, (_, _, _, tipo) in enumerate(colunas):
        if tipo == "numero":
            estilo_tabela.add("ALIGN", (indice, 1), (indice, -1), "RIGHT")
        elif tipo == "centro":
            estilo_tabela.add("ALIGN", (indice, 1), (indice, -1), "CENTER")

    if not df_pdf.empty:
        indice_sugerida = next(
            (i for i, (coluna, _, _, _) in enumerate(colunas) if coluna == "Compra Sugerida"),
            None,
        )
        if indice_sugerida is not None:
            estilo_tabela.add(
                "BACKGROUND",
                (indice_sugerida, 1),
                (indice_sugerida, len(dados) - 2),
                COR_PRIMARIA_CLARA,
            )
        indice_total = len(dados) - 1
        fim_span = min(2, len(colunas) - 1)
        estilo_tabela.add("SPAN", (0, indice_total), (fim_span, indice_total))
        estilo_tabela.add("BACKGROUND", (0, indice_total), (-1, indice_total), COR_PRIMARIA_CLARA)
        estilo_tabela.add("LINEABOVE", (0, indice_total), (-1, indice_total), 1, COR_PRIMARIA)
    else:
        dados.append(
            [
                Paragraph(
                    "Nenhum item com compra sugerida nos filtros atuais.",
                    ESTILO_CELULA,
                )
            ]
            + [""] * (len(colunas) - 1)
        )
        estilo_tabela.add("SPAN", (0, 1), (-1, 1))
        estilo_tabela.add("ALIGN", (0, 1), (-1, 1), "CENTER")

    tabela = Table(dados, colWidths=larguras, repeatRows=1, splitByRow=1)
    tabela.setStyle(estilo_tabela)

    resumo = _tabela_resumo(qtd_itens, total_sugerida, total_bruta, documento.width)
    legenda = Paragraph(
        'Compra sugerida = menor valor entre <b>|Saldo 5| × 1,1</b> (arredondado '
        'para cima) e o teto <b>"Tec Faz x Confec"</b>. Valores em '
        '<font color="#b45309"><b>âmbar</b></font> foram limitados pelo teto. '
        "Saldo 5 negativo indica necessidade de reposição.",
        ESTILO_LEGENDA,
    )
    ordenacao = Paragraph(
        "Itens ordenados pela maior compra sugerida. Totais ao final da listagem.",
        ESTILO_LEGENDA,
    )

    story = [
        resumo,
        Spacer(1, 3 * mm),
        legenda,
        Spacer(1, 1 * mm),
        ordenacao,
        Spacer(1, 4 * mm),
        tabela,
    ]

    def primeira_pagina(canv, doc):
        _desenhar_cabecalho(canv, doc, data_referencia, True)
        _desenhar_rodape(canv, doc, gerado_em)

    def demais_paginas(canv, doc):
        _desenhar_cabecalho(canv, doc, data_referencia, False)
        _desenhar_rodape(canv, doc, gerado_em)

    documento.build(
        story,
        onFirstPage=primeira_pagina,
        onLaterPages=demais_paginas,
        canvasmaker=_CanvasPaginado,
    )
    return buffer.getvalue()
