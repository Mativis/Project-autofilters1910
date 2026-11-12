"""
Rastreabilidade dos pedidos
---------------------------
Regras compartilhadas entre a Projeção por Confecção e o Kanban de Confecção:
em qual etapa do fluxo cada pedido está e quais cores/legendas representam
cada etapa.

Fica em um módulo próprio (em vez de `nucleo.py`) para que seja recarregado
sem depender do cache de módulos do Streamlit.
"""

import re
import unicodedata

# Etapas do fluxo, na ordem em que aparecem nas telas
BUCKETS_RASTREABILIDADE = (
    "Aguardando envio",
    "Aguardando produção",
    "Aguardando saldo",
)

# Status do arquivo de Pedidos -> etapa do fluxo
MAPA_STATUS_RASTREABILIDADE = {
    "ORCAMENTO": "Aguardando envio",
    "EM SEPARACAO": "Aguardando envio",
    "PEDIDO": "Aguardando envio",
    "PEDIDO C/ FORN": "Aguardando produção",
    "FAT. PARCIAL": "Aguardando saldo",
}

CORES_RASTREABILIDADE = {
    "Aguardando envio": "#667eea",
    "Aguardando produção": "#ef6c00",
    "Aguardando saldo": "#2e7d32",
}

SEM_CLASSIFICACAO = "Sem classificação"

# Fundos suaves (impressão/Excel) para o selo de cada etapa
CORES_SUAVES_RASTREABILIDADE = {
    "Aguardando envio": "#eef0ff",
    "Aguardando produção": "#fff3e0",
    "Aguardando saldo": "#e8f5e9",
    SEM_CLASSIFICACAO: "#f1f3f5",
}

# Sufixo de classe CSS de cada etapa (ex.: kb-stage-dot.envio)
CLASSES_RASTREABILIDADE = {
    "Aguardando envio": "envio",
    "Aguardando produção": "producao",
    "Aguardando saldo": "saldo",
    SEM_CLASSIFICACAO: "sem-classificacao",
}


def classe_rastreabilidade(etapa):
    """Sufixo de classe CSS da etapa (para os selos de classificação)."""
    return CLASSES_RASTREABILIDADE.get(etapa, "sem-classificacao")


def classificar_rastreabilidade(status):
    """Classifica o status do pedido em uma das etapas de rastreabilidade.

    Ignora acentos, caixa e espaços extras (``"Orçamento"`` e
    ``"ORCAMENTO"`` caem na mesma etapa).
    """
    if status is None:
        return SEM_CLASSIFICACAO
    texto = unicodedata.normalize("NFKD", str(status))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    chave = re.sub(r"\s+", " ", texto.upper()).strip()
    return MAPA_STATUS_RASTREABILIDADE.get(chave, SEM_CLASSIFICACAO)
