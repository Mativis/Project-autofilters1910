"""
Serviço de dados para o app Flask.
Espelha nucleo.py do Streamlit. Processamento stateless.
"""
import io
import math

import numpy as np
import pandas as pd


def load_excel(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = df.columns.str.strip()
    return df


def normalizar_cod(valor):
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


def para_texto(serie):
    if serie is None:
        return pd.Series(dtype="object")
    try:
        return serie.astype("string").fillna("").astype(str)
    except Exception:
        return serie.map(lambda v: "" if pd.isna(v) else str(v))


def _texto(valor, padrao=""):
    if valor is None:
        return padrao
    try:
        if pd.isna(valor):
            return padrao
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    return texto if texto else padrao


def preparar_pedidos(df):
    if df is None:
        return None
    df = df.copy()
    for antes, depois in (("Dt Emissão", "Dt Emissao"), ("Dt Emissao ", "Dt Emissao")):
        if antes in df.columns and depois not in df.columns:
            df = df.rename(columns={antes: depois})
    for coluna in ("Cód Confec", "Compra", "Confeccionado", "Confecção", "Qtd", "Saldo"):
        if coluna not in df.columns:
            df[coluna] = np.nan
    if "Dt Entrega" not in df.columns:
        df["Dt Entrega"] = pd.NaT
    df["Cód Confec_norm"] = df["Cód Confec"].map(normalizar_cod)
    df["Cód Confec"] = df["Cód Confec_norm"]
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
    df["Eficacia"] = np.where(df["Qtd"] > 0, df["Saldo"] / df["Qtd"], np.nan)
    return df


def preparar_estoque(df):
    if df is None:
        return None
    df = df.copy()
    if "Cód Confec" not in df.columns:
        df["Cód Confec"] = np.nan
    df["Cód Confec_norm"] = df["Cód Confec"].map(normalizar_cod)
    for coluna in ["Saldo 1", "Saldo 2", "Saldo 3", "Saldo 4", "Saldo 5",
                   "Em Trânsito", "Em Confecção", "Carteira sem Fat", "Empenhado",
                   "Estoque", "Saldo Compra", "Qtd. Cortado", 'Tec Faz "x" Confec',
                   "Cons. Unitário", "Cons Unitario"]:
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
    if "Cons Unitario" in df.columns and "Cons. Unitário" not in df.columns:
        df["Cons. Unitário"] = df["Cons Unitario"]
    if "Cons. Unitário" not in df.columns:
        df["Cons. Unitário"] = np.nan
    for coluna, padrao in [("Situação", "Sem Situação"), ("Coleção", "Sem Coleção"),
                           ("Segmento", "Sem Segmento"), ("Tipo Produto", "Sem Tipo")]:
        if coluna in df.columns:
            df[coluna] = df[coluna].map(lambda v, p=padrao: _texto(v, p))
    return df


def fmt_num(valor):
    try:
        if pd.isna(valor):
            return "—"
        num = float(valor)
        if num == int(num) and abs(num) < 1e15:
            return f"{int(num):,}".replace(",", ".")
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def fmt_data(valor):
    if pd.isna(valor):
        return "—"
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


def localizar_coluna(df, *nomes):
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes:
        if nome in df.columns:
            return nome
        chave = str(nome).strip().lower()
        if chave in mapa:
            return mapa[chave]
    return None


def coluna_texto(df, *nomes, padrao=""):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series([padrao] * len(df), index=df.index, dtype="object")
    return para_texto(df[coluna]).str.strip().replace("", padrao)


def coluna_numero(df, *nomes):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[coluna], errors="coerce")


def coluna_data(df, *nomes):
    coluna = localizar_coluna(df, *nomes)
    if coluna is None:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    return pd.to_datetime(df[coluna], errors="coerce")


def df_to_records(df):
    """Converte DataFrame para lista de dicts serializável (JSON)."""
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                rec[col] = None
            elif isinstance(v, (pd.Timestamp,)):
                rec[col] = v.strftime("%d/%m/%Y")
            elif isinstance(v, (np.integer,)):
                rec[col] = int(v)
            elif isinstance(v, (np.floating,)):
                rec[col] = float(v)
            elif isinstance(v, (np.bool_,)):
                rec[col] = bool(v)
            else:
                rec[col] = v
        out.append(rec)
    return out


# ==================== PROCESSAMENTO: KANBAN ====================

def processar_kanban(df_pedidos_raw, df_estoque_raw):
    df_pedidos = preparar_pedidos(df_pedidos_raw)
    df_estoque = preparar_estoque(df_estoque_raw) if df_estoque_raw is not None else None
    if df_pedidos is None:
        return None
    codigos_kanban = set()
    if df_estoque is not None and "Saldo 2" in df_estoque.columns:
        mask = df_estoque["Saldo 2"] < 0
        codigos_kanban = set(df_estoque.loc[mask, "Cód Confec_norm"].dropna().tolist())
    if codigos_kanban:
        df_pedidos = df_pedidos[df_pedidos["Cód Confec_norm"].isin(codigos_kanban)].copy()
    grupos = []
    for conf, g in df_pedidos.groupby("Confecção"):
        itens = []
        for _, row in g.iterrows():
            qtd = row.get("Qtd", 0) or 0
            saldo = row.get("Saldo", 0) or 0
            qe = 0
            try:
                qe = math.ceil(saldo * 1.10)
                if qe > saldo:
                    qe = int(saldo)
            except Exception:
                qe = 0
            itens.append({
                "compra": str(int(row["Compra"])) if pd.notna(row.get("Compra")) else "",
                "cod_confec": row.get("Cód Confec", ""),
                "confeccionado": row.get("Confeccionado", ""),
                "qtd": qtd,
                "saldo": saldo,
                "qe": qe,
                "prioridade": row.get("Prioridade", "Baixa"),
                "dt_entrega": fmt_data(row.get("Dt Entrega")),
                "marca": row.get("Marca", ""),
            })
        grupos.append({"confeccao": conf, "itens": itens, "total_qtd": sum(i["qtd"] for i in itens), "total_saldo": sum(i["saldo"] for i in itens)})
    return grupos


# ==================== PROCESSAMENTO: DASHBOARDS ====================

def processar_dashboards(df_pedidos_raw, df_estoque_raw):
    df_pedidos = preparar_pedidos(df_pedidos_raw)
    df_estoque = preparar_estoque(df_estoque_raw) if df_estoque_raw is not None else None
    if df_pedidos is None:
        return None
    qtd_total = float(df_pedidos["Qtd"].sum()) if "Qtd" in df_pedidos.columns else 0
    saldo_total = float(df_pedidos["Saldo"].sum()) if "Saldo" in df_pedidos.columns else 0
    eficacia = (saldo_total / qtd_total) if qtd_total else 0
    n_atrasados = int((df_pedidos["Prioridade"] == "Atrasado").sum()) if "Prioridade" in df_pedidos.columns else 0
    top_marcas = []
    if "Marca" in df_pedidos.columns:
        top_marcas = df_pedidos.groupby("Marca").agg(Pedidos=("Compra", "count"), Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum")).sort_values("Qtd", ascending=False).head(10).reset_index()
        top_marcas = df_to_records(top_marcas)
    top_codigos = []
    if "Cód Confec" in df_pedidos.columns:
        top_codigos = df_pedidos.groupby(["Cód Confec", "Confeccionado"]).agg(Qtd=("Qtd", "sum"), Saldo=("Saldo", "sum")).sort_values("Qtd", ascending=False).head(10).reset_index()
        top_codigos = df_to_records(top_codigos)
    status_counts = {}
    if "Status" in df_pedidos.columns:
        status_counts = df_pedidos["Status"].value_counts().to_dict()
    return {
        "kpi": {"pedidos": len(df_pedidos), "qtd_total": qtd_total, "saldo_total": saldo_total, "eficacia": eficacia, "atrasados": n_atrasados},
        "top_marcas": top_marcas,
        "top_codigos": top_codigos,
        "status_counts": status_counts,
    }


# ==================== PROCESSAMENTO: ESTOQUE ====================

def processar_estoque(df_estoque_raw, df_pedidos_raw):
    df_estoque = preparar_estoque(df_estoque_raw)
    if df_estoque is None:
        return None
    compra_sugerida = []
    tecido_sugerido = []
    if "Saldo 5" in df_estoque.columns:
        tec_col = 'Tec Faz "x" Confec'
        cons_col = "Cons. Unitário"
        for _, row in df_estoque.iterrows():
            s5 = row.get("Saldo 5")
            if pd.isna(s5) or s5 >= 0:
                continue
            tec_faz = row.get(tec_col, 0)
            cons = row.get(cons_col, 0)
            if pd.isna(tec_faz):
                tec_faz = 0
            if pd.isna(cons):
                cons = 0
            compra = abs(s5) * 1.10
            if tec_faz:
                compra = min(compra, tec_faz)
            compra = math.ceil(compra)
            compra_sugerida.append({"cod_confec": row.get("Cód Confec_norm", ""), "descricao": row.get("Descrição", ""), "marca": row.get("Marca", ""), "saldo5": float(s5), "tec_faz": float(tec_faz), "compra_sugerida": int(compra)})
            calc = float(s5) + float(tec_faz)
            tecido = 0.0
            if calc < 0:
                tecido = (abs(calc) * 1.10) * float(cons)
            if tecido > 0:
                tecido_sugerido.append({"cod_confec": row.get("Cód Confec_norm", ""), "descricao": row.get("Descrição", ""), "saldo5": float(s5), "tecido_sugerido": round(tecido, 3)})
    saldo2_total = float(df_estoque["Saldo 2"].sum()) if "Saldo 2" in df_estoque.columns else 0
    saldo5_neg = int((df_estoque["Saldo 5"] < 0).sum()) if "Saldo 5" in df_estoque.columns else 0
    return {
        "saldo2_total": saldo2_total,
        "saldo5_negativos": saldo5_neg,
        "compra_sugerida": compra_sugerida,
        "tecido_sugerido": tecido_sugerido,
        "total_compra": sum(c["compra_sugerida"] for c in compra_sugerida),
        "total_tecido": sum(t["tecido_sugerido"] for t in tecido_sugerido),
    }


# ==================== PROCESSAMENTO: PROJEÇÃO ====================

def processar_projecao(df_proj_raw, df_pedidos_raw, df_estoque_raw, params):
    if df_proj_raw is None:
        return None
    # (implementação simplificada - retorna dados processados)
    return {"status": "ok", "params": params}
