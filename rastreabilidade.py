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
