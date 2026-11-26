"""Processamento de dados do Visualfil Reflex (sem dependência de Streamlit).

Porta, para a versão Reflex, as regras do núcleo clássico:
normalização de códigos/datas, prioridade, rastreabilidade, quantidade
emergencial (Q.E.), montagem do Kanban offline e das visões online.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date
from typing import Any

import pandas as pd

# ---------------------------------------------------------------- constantes
STATUS = ("Pendente", "Em andamento", "Pronto", "Entregue")
ROTULO_STATUS = {
    "Pendente": "A produzir",
    "Em andamento": "Em produção",
    "Pronto": "Pronto",
    "Entregue": "Entregue",
}
TRANSICOES = {
    "Pendente": ("Em andamento",),
    "Em andamento": ("Pendente", "Pronto"),
    "Pronto": ("Em andamento", "Entregue"),
    "Entregue": ("Pronto",),
}
ROTULO_MOV = {
    "Pendente": "← Voltar",
    "Em andamento": "→ Iniciar",
    "Pronto": "✓ Pronto",
    "Entregue": "📦 Entregar",
}
PESO_PRIORIDADE = {"Atrasado": 0, "Alta": 1, "Média": 2, "Baixa": 3}
PRIORIDADES = ("Atrasado", "Alta", "Média", "Baixa")

MAPA_STATUS_RASTREABILIDADE = {
    "ORCAMENTO": "Aguardando envio",
    "EM SEPARACAO": "Aguardando envio",
    "PEDIDO": "Aguardando envio",
    "PEDIDO C/ FORN": "Aguardando produção",
    "FAT. PARCIAL": "Aguardando saldo",
}
BUCKETS_RASTREABILIDADE = (
    "Aguardando envio", "Aguardando produção", "Aguardando saldo", "Sem classificação",
)
CORES_RASTREABILIDADE = {
    "Aguardando envio": "#667eea",
    "Aguardando produção": "#ef6c00",
    "Aguardando saldo": "#2e7d32",
    "Sem classificação": "#94a3b8",
}
FATOR_PADRAO = 1.10
LIMITE_BAIXO = 0.04


# ---------------------------------------------------------------- helpers
def normalizar_cod(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        num = float(valor)
        if num == int(num):
            return str(int(num))
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    return texto[:-2] if texto.endswith(".0") else texto


def para_datetime_serie(serie: pd.Series) -> pd.Series:
    """Converte datas mistas (ISO com fuso, str, date, Timestamp) em naive."""
    def converter(valor: Any):
        try:
            if pd.isna(valor):
                return pd.NaT
            ts = pd.Timestamp(valor)
            return ts.tz_localize(None) if ts.tzinfo is not None else ts
        except (TypeError, ValueError, OverflowError):
            return pd.NaT
    return pd.Series([converter(v) for v in serie], index=serie.index)


def classificar_rastreabilidade(status: Any) -> str:
    if status is None or (isinstance(status, float) and pd.isna(status)):
        return "Sem classificação"
    texto = unicodedata.normalize("NFKD", str(status))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    chave = re.sub(r"\s+", " ", texto.upper()).strip()
    return MAPA_STATUS_RASTREABILIDADE.get(chave, "Sem classificação")


def calcular_prioridade(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return "Baixa"
    try:
        dia = pd.Timestamp(valor).normalize().date()
    except (TypeError, ValueError, OverflowError):
        return "Baixa"
    dias = (dia - date.today()).days
    if dias < 0:
        return "Atrasado"
    if dias > 30:
        return "Baixa"
    if dias > 15:
        return "Média"
    return "Alta"


def fmt_data(valor: Any) -> str:
    try:
        if valor is None or pd.isna(valor):
            return "—"
        return pd.Timestamp(valor).strftime("%d/%m/%Y")
    except (TypeError, ValueError, OverflowError):
        return "—"


def fmt_num(valor: Any) -> str:
    try:
        return f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def texto_dias(valor: Any) -> str:
    try:
        if valor is None or pd.isna(valor):
            return "sem data"
        dias = (pd.Timestamp(valor).normalize().date() - date.today()).days
    except (TypeError, ValueError, OverflowError):
        return "sem data"
    if dias < 0:
        return f"{abs(dias)}d atrasado"
    if dias == 0:
        return "hoje"
    return f"{dias}d"


# ---------------------------------------------------------------- preparação
def preparar_pedidos(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None:
        return None
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for antes, depois in (("Dt Emissão", "Dt Emissao"), ("Dt Entrega ", "Dt Entrega")):
        if antes in df.columns and depois not in df.columns:
            df = df.rename(columns={antes: depois})
    for coluna in ("Compra", "Cód Confec", "Confeccionado", "Qtd", "Saldo", "Status",
                   "Dt Entrega", "Confecção"):
        if coluna not in df.columns:
            df[coluna] = pd.NA
    df["_cod"] = df["Cód Confec"].map(normalizar_cod)
    df["Cód Confec"] = df["_cod"]
    df["Dt Entrega"] = para_datetime_serie(df["Dt Entrega"])
    if "Dt Emissao" in df.columns:
        df["Dt Emissao"] = para_datetime_serie(df["Dt Emissao"])
    for coluna in ("Qtd", "Saldo", "QtdRet", "Qtd Ret", "Saldo 2"):
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    for coluna in ("Confecção", "Confeccionado", "Status", "Marca"):
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()
        if coluna == "Confecção":
            df[coluna] = df[coluna].replace("", "Sem Confecção")
    df["Prioridade"] = df["Dt Entrega"].map(calcular_prioridade)
    df["Classificação"] = df["Status"].map(classificar_rastreabilidade)
    return df


def preparar_estoque(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None:
        return None
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "Cód Confec" not in df.columns:
        df["Cód Confec"] = pd.NA
    df["_cod"] = df["Cód Confec"].map(normalizar_cod)
    for coluna in ("Saldo 1", "Saldo 2", "Saldo 3", "Saldo 4", "Saldo 5", "Em Trânsito",
                   'Tec Faz "x" Confec', "Cons. Unitário", "Cons Unitario"):
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    if "Cons Unitario" in df.columns and "Cons. Unitário" not in df.columns:
        df["Cons. Unitário"] = df["Cons Unitario"]
    if "Marca" in df.columns:
        df["Marca"] = df["Marca"].fillna("").astype(str).str.strip().replace("", "—")
    else:
        df["Marca"] = "—"
    if "Descrição" not in df.columns:
        df["Descrição"] = ""
    return df


def saldo2_por_codigo(est: pd.DataFrame) -> dict[str, float]:
    if est.empty or "Saldo 2" not in est.columns:
        return {}
    out: dict[str, float] = {}
    for cod, valor in zip(est["_cod"], pd.to_numeric(est["Saldo 2"], errors="coerce")):
        if cod and pd.notna(valor):
            out[cod] = float(valor)
    return out


def calcular_qe(saldo2: Any, saldo_pedido: Any, fator: float = FATOR_PADRAO) -> int:
    if saldo2 is None or pd.isna(saldo2) or saldo_pedido is None or pd.isna(saldo_pedido):
        return 0
    bruto = math.ceil(abs(float(saldo2)) * float(fator))
    teto = int(max(0, float(saldo_pedido)))
    return int(max(0, min(bruto, teto)))


def distribuir_qe(df: pd.DataFrame, mapa_saldo2: dict[str, float],
                  fator: float = FATOR_PADRAO) -> pd.DataFrame:
    """Q.E. calculada uma vez por código e distribuída aos pedidos mais urgentes."""
    resultado = df.copy()
    resultado["Q.E"] = 0
    if resultado.empty:
        return resultado
    saldo = pd.to_numeric(resultado["Saldo"], errors="coerce").fillna(0).clip(lower=0)
    aux = pd.DataFrame({
        "_saldo": saldo,
        "_prioridade": resultado["Prioridade"].map(PESO_PRIORIDADE).fillna(9),
        "_entrega": resultado["Dt Entrega"],
        "_pedido": resultado["Compra"].astype(str),
    }, index=resultado.index).sort_values(
        ["_prioridade", "_entrega", "_pedido"], kind="stable", na_position="last"
    )
    for codigo, grupo in aux.groupby(resultado["_cod"], sort=False):
        restante = calcular_qe(mapa_saldo2.get(codigo), grupo["_saldo"].sum(), fator)
        for indice, capacidade in zip(grupo.index, grupo["_saldo"]):
            if restante <= 0:
                break
            quantidade = min(restante, math.floor(float(capacidade or 0)))
            if quantidade > 0:
                resultado.at[indice, "Q.E"] = int(quantidade)
                restante -= int(quantidade)
    return resultado


# ---------------------------------------------------------------- Kanban offline
def montar_offline(
    ped_raw: pd.DataFrame | None,
    est_raw: pd.DataFrame | None,
    fator: float = FATOR_PADRAO,
    desconsiderar_baixo: bool = True,
) -> dict:
    """Monta todo o estado do Kanban de Confecção offline.

    Devolve: cards, kpis, resumo_classificacao, resumo_confeccao, avisos,
    total_qe, codigos_negativos, retornos.
    """
    if ped_raw is None or est_raw is None:
        return {"cards": [], "kpis": {}, "resumo_classificacao": [],
                "resumo_confeccao": [], "avisos": [], "total_qe": 0,
                "codigos_negativos": 0, "retornos": "—"}

    avisos: list[str] = []
    ped = preparar_pedidos(ped_raw)
    est = preparar_estoque(est_raw)
    faltando = [c for c in ("Compra", "Cód Confec", "Confeccionado", "Qtd", "Saldo")
                if c not in ped.columns]
    if faltando:
        avisos.append("Colunas ausentes no Pedidos.xlsx: " + ", ".join(faltando))
        return {"cards": [], "kpis": {}, "resumo_classificacao": [],
                "resumo_confeccao": [], "avisos": avisos, "total_qe": 0,
                "codigos_negativos": 0, "retornos": "—"}
    if "Saldo 2" not in est.columns:
        avisos.append("Estoque.xlsx sem coluna 'Saldo 2' — Q.E. será zero.")

    mapa_saldo2 = saldo2_por_codigo(est)
    marcas = dict(zip(est["_cod"], est.get("Marca", pd.Series(dtype=str))))
    qtdret_col = "QtdRet" if "QtdRet" in ped.columns else (
        "Qtd Ret" if "Qtd Ret" in ped.columns else None
    )
    qtdret = (pd.to_numeric(ped[qtdret_col], errors="coerce").fillna(0)
              if qtdret_col else pd.Series(0.0, index=ped.index))
    qtd = pd.to_numeric(ped["Qtd"], errors="coerce").fillna(0)

    if desconsiderar_baixo:
        limite = qtd * LIMITE_BAIXO
        remover = pd.to_numeric(ped["Saldo"], errors="coerce").fillna(0) <= limite
        if remover.any():
            avisos.append(f"{int(remover.sum())} pedido(s) com saldo ≤ 4% da quantidade foram desconsiderados.")
            ped = ped[~remover].copy()
            qtdret = qtdret.loc[ped.index]
            qtd = qtd.loc[ped.index]

    ped = distribuir_qe(ped, mapa_saldo2, fator)

    cards: list[dict] = []
    for i, (_, r) in enumerate(ped.iterrows()):
        cod = str(r.get("_cod", ""))
        try:
            pedido = str(int(float(r["Compra"]))) if pd.notna(r["Compra"]) else str(r["Compra"])
        except (TypeError, ValueError):
            pedido = str(r.get("Compra", ""))
        entrega = r.get("Dt Entrega", pd.NaT)
        saldo = float(pd.to_numeric(r.get("Saldo"), errors="coerce") or 0)
        qtd_v = float(qtd.get(r.name, 0) or 0)
        retornado = float(qtdret.get(r.name, 0) or 0)
        cards.append({
            "chave": f"{pedido}|{cod}|{i}",
            "pedido": pedido,
            "codigo": cod,
            "item": str(r.get("Confeccionado", ""))[:70],
            "confeccao": str(r.get("Confecção", "") or "Sem Confecção"),
            "marca": str(marcas.get(cod, "—") or "—"),
            "qtd": qtd_v,
            "saldo": saldo,
            "retornado": retornado,
            "retorno_pct": round(min(100, retornado / qtd_v * 100), 1) if qtd_v > 0 else 0.0,
            "qe": int(r.get("Q.E", 0) or 0),
            "entrega": fmt_data(entrega),
            "dias": texto_dias(entrega),
            "prioridade": str(r.get("Prioridade", "Baixa")),
            "classificacao": str(r.get("Classificação", "Sem classificação")),
            "status": "Pendente",
            "qtd_pronta": 0.0,
            "qtd_quebra": 0.0,
            "status_por": "",
            "status_em": "",
        })

    kpis = {
        "pedidos": len(cards),
        "confeccoes": len({c["confeccao"] for c in cards}),
        "atrasado": sum(c["prioridade"] == "Atrasado" for c in cards),
        "alta": sum(c["prioridade"] == "Alta" for c in cards),
        "media": sum(c["prioridade"] == "Média" for c in cards),
        "baixa": sum(c["prioridade"] == "Baixa" for c in cards),
        "unidades": sum(c["saldo"] for c in cards),
    }
    resumo_classificacao = []
    for etapa in BUCKETS_RASTREABILIDADE:
        grupo = [c for c in cards if c["classificacao"] == etapa]
        if grupo:
            resumo_classificacao.append({
                "Etapa": etapa, "Pedidos": len(grupo),
                "Unidades": sum(c["saldo"] for c in grupo),
                "Cor": CORES_RASTREABILIDADE[etapa],
            })
    resumo_confeccao = []
    for conf in sorted({c["confeccao"] for c in cards}):
        grupo = [c for c in cards if c["confeccao"] == conf]
        resumo_confeccao.append({
            "Confecção": conf,
            "Pedidos": len(grupo),
            "Quantidade": sum(c["qtd"] for c in grupo),
            "Saldo": sum(c["saldo"] for c in grupo),
            "Q.E": sum(c["qe"] for c in grupo),
            "Retornado": sum(c["retornado"] for c in grupo),
        })
    total_ret = sum(c["retornado"] for c in cards)
    total_qtd = sum(c["qtd"] for c in cards)
    retornos = f"{fmt_num(total_ret)} de {fmt_num(total_qtd)} ({round(total_ret / total_qtd * 100, 1) if total_qtd else 0}%)"
    return {
        "cards": cards,
        "kpis": kpis,
        "resumo_classificacao": resumo_classificacao,
        "resumo_confeccao": resumo_confeccao,
        "avisos": avisos,
        "total_qe": sum(c["qe"] for c in cards),
        "codigos_negativos": sum(v < 0 for v in mapa_saldo2.values()),
        "retornos": retornos,
    }


# ---------------------------------------------------------------- visões online
def montar_kanban_online(ped: pd.DataFrame, est: pd.DataFrame) -> list[dict]:
    if ped.empty or est.empty:
        return []
    ped, est = preparar_pedidos(ped) or ped, preparar_estoque(est) or est
    codigos = set(c for c, v in saldo2_por_codigo(est).items() if v < 0)
    marcas = dict(zip(est["_cod"] if "_cod" in est.columns else [],
                      est.get("Marca", pd.Series(dtype=str))))
    out = []
    for _, r in ped.iterrows():
        cod = normalizar_cod(r.get("Cód Confec"))
        if cod not in codigos:
            continue
        out.append({
            "Pedido": str(r.get("Compra", "")),
            "Código": cod,
            "Item": str(r.get("Confeccionado", ""))[:55],
            "Confecção": str(r.get("Confecção", "")),
            "Marca": str(marcas.get(cod, "—")),
            "Qtd": float(pd.to_numeric(r.get("Qtd"), errors="coerce") or 0),
            "Saldo": float(pd.to_numeric(r.get("Saldo"), errors="coerce") or 0),
            "Prioridade": str(r.get("Prioridade", "Baixa")),
        })
    return out[:500]


def montar_compra(est: pd.DataFrame, catalogo: list[dict] | None = None) -> tuple[list[dict], list[dict], str]:
    if est.empty or "Saldo 5" not in est.columns:
        return [], [], "0"
    est = est.copy()
    saldo5 = pd.to_numeric(est["Saldo 5"], errors="coerce").fillna(0)
    neg = est[saldo5 < 0].copy()
    if neg.empty:
        return [], [], "0"
    tec = (pd.to_numeric(neg.get('Tec Faz "x" Confec'), errors="coerce").fillna(0)
           if 'Tec Faz "x" Confec' in neg.columns else 0)
    base = (saldo5[neg.index].abs() * 1.10).round(0)
    compra = (base - tec).clip(lower=0).round()
    mapa_conf = {}
    for item in (catalogo or []):
        cod = normalizar_cod(item.get("codigo"))
        conf = str(item.get("confeccao") or "").strip()
        if cod and conf:
            mapa_conf[cod] = conf
    cods = neg["Cód Confec"].map(normalizar_cod)
    confs = cods.map(mapa_conf).fillna("Sem confecção cadastrada")
    itens = [{
        "Código": str(cod),
        "Item": str(r.get("Descrição", ""))[:55],
        "Saldo 5": float(saldo5.get(r.name, 0)),
        "Confecção": str(confs.get(r.name, "")),
        "Tec Faz": float(tec.get(r.name, 0)) if hasattr(tec, "get") else 0.0,
        "Compra": float(compra.get(r.name, 0)),
    } for _, r in neg.iterrows()]
    itens.sort(key=lambda x: x["Compra"], reverse=True)
    mapa: dict[str, dict] = {}
    for item in itens:
        g = mapa.setdefault(item["Confecção"], {"Confecção": item["Confecção"], "Itens": 0, "Compra": 0.0})
        g["Itens"] += 1
        g["Compra"] += item["Compra"]
    resumo = sorted(mapa.values(), key=lambda x: x["Compra"], reverse=True)
    return itens[:500], resumo, fmt_num(sum(x["Compra"] for x in itens))


def montar_capacidade(prod: pd.DataFrame) -> list[dict]:
    if prod.empty:
        return []
    col_conf = next((c for c in prod.columns if "fornecedor" in str(c).lower()), None)
    col_qtd = next((c for c in prod.columns
                    if "qtd" in str(c).lower() and "retorn" in str(c).lower()), None)
    if not col_conf or not col_qtd:
        return []
    p = prod.copy()
    p["_q"] = pd.to_numeric(p[col_qtd], errors="coerce").fillna(0)
    g = p.groupby(col_conf)["_q"].sum().sort_values(ascending=False)
    return [{"Confecção": str(k), "Retornos": float(v)} for k, v in g.items()][:100]


def agrupar(dados: list[dict], chave: str) -> list[dict]:
    mapa: dict[str, dict] = {}
    for item in dados:
        k = str(item.get(chave, "")) or "—"
        g = mapa.setdefault(k, {"Grupo": k, "Pedidos": 0, "Unidades": 0.0})
        g["Pedidos"] += 1
        g["Unidades"] += float(item.get("Saldo", item.get("saldo", 0)) or 0)
    return sorted(mapa.values(), key=lambda x: x["Unidades"], reverse=True)
