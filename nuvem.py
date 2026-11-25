"""
Visualfil Cloud — cliente Python do backend online (Google Sheets / Apps Script)
==============================================================================

Toda a persistência (usuários, permissões, demandas, XLSX, catálogo por
confecção e análises salvas) fica no Google Sheets/Drive através do Web App
definido em `appscript/VisualfilCloud.gs`.

Configuração (em ordem de prioridade):
  1) campos na tela de login (gravados em st.session_state);
  2) st.secrets: vfcloud_url, vfcloud_usuario, vfcloud_senha;
  3) variáveis de ambiente: VFCLOUD_URL, VFCLOUD_USUARIO, VFCLOUD_SENHA.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import streamlit as st

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

CHAVE_URL = "vf_url"
CHAVE_USER = "vf_usuario_config"
CHAVE_SENHA = "vf_senha_config"
CHAVE_SESSAO = "vf_sessao"

PAGINAS = (
    "Kanban de Confecção",
    "Dashboards de Pedidos",
    "Análise de Estoque",
    "Projeção Futuro",
    "Projeção por Confecção",
    "Painel Online",
    "Administração",
)
NIVEIS = ("visualizacao", "total", "restrito")

# ============================ PERFORMANCE ============================

CACHE_DADOS: dict[str, dict] = {}
CACHE_TTL = 300


def cache_validar(demanda_id: str) -> bool:
    item = CACHE_DADOS.get(demanda_id)
    return bool(item and (time.time() - item.get("ts", 0)) < CACHE_TTL)


def cache_guardar(demanda_id: str, dados: dict):
    CACHE_DADOS[demanda_id] = {"ts": time.time(), "dados": dados}


def cache_ler(demanda_id: str) -> dict:
    return (CACHE_DADOS.get(demanda_id) or {}).get("dados", {})


def cache_limpar(demanda_id: str = ""):
    if demanda_id:
        CACHE_DADOS.pop(demanda_id, None)
    else:
        CACHE_DADOS.clear()


def arquivos_ler(demanda_id: str, tipos=("pedidos", "estoque", "producao")):
    """Lê vários XLSX em UMA chamada; fallback paralelo para backend antigo.
    Devolve (bytes_por_tipo, erros, modo)."""
    r = call("arquivos_ler", demanda_id=demanda_id, tipos=list(tipos), timeout=240)
    if r.get("ok") and "arquivos" in r:
        dados, erros = {}, dict(r.get("erros", {}))
        for tipo, conteudo in r["arquivos"].items():
            try:
                if isinstance(conteudo, dict) and "colunas" in conteudo:
                    dados[tipo] = _df_de_linhas(conteudo.get("colunas"), conteudo.get("linhas"))
                elif isinstance(conteudo, dict) and "base64" in conteudo:
                    dados[tipo] = base64.b64decode(conteudo["base64"])
                else:
                    dados[tipo] = base64.b64decode(conteudo)
            except Exception as exc:
                erros[tipo] = str(exc)
        return dados, erros, "lote"

    def um(tipo):
        try:
            resp = call("arquivo_ler", demanda_id=demanda_id, tipo=tipo, timeout=240)
            if not resp.get("ok"):
                return tipo, None, resp.get("erro", "sem resposta")
            if resp.get("colunas") is not None:
                return tipo, _df_de_linhas(resp.get("colunas"), resp.get("linhas")), None
            return tipo, base64.b64decode(resp.get("base64", "")), None
        except Exception as exc:
            return tipo, None, str(exc)

    dados, erros = {}, {}
    with ThreadPoolExecutor(max_workers=len(tipos)) as pool:
        for tipo, conteudo, erro in pool.map(um, tipos):
            if conteudo is not None:
                dados[tipo] = conteudo
            if erro:
                erros[tipo] = erro
    return dados, erros, "paralelo"


def agregado_salvar(demanda_id: str, dados: dict) -> dict:
    return call("agregado_salvar", demanda_id=demanda_id,
                dados_json=json.dumps(dados, ensure_ascii=False))


def agregado_ler(demanda_id: str) -> dict:
    return call("agregado_ler", demanda_id=demanda_id)



def _secrets(nome: str) -> str:
    try:
        return str(st.secrets.get(nome, "") or "")
    except Exception:
        return ""


def configurar(url: str = "", usuario: str = "", senha: str = "") -> None:
    """Grava a configuração do Web App na sessão."""
    if url:
        st.session_state[CHAVE_URL] = url.strip()
    if usuario:
        st.session_state[CHAVE_USER] = usuario.strip()
    if senha:
        st.session_state[CHAVE_SENHA] = senha


def url() -> str:
    return str(
        st.session_state.get(CHAVE_URL)
        or _secrets("vfcloud_url")
        or os.getenv("VFCLOUD_URL", "")
        or ""
    ).strip()


def credenciais() -> tuple[str, str]:
    usuario = str(
        st.session_state.get(CHAVE_USER)
        or _secrets("vfcloud_usuario")
        or os.getenv("VFCLOUD_USUARIO", "")
        or ""
    ).strip()
    senha = str(
        st.session_state.get(CHAVE_SENHA)
        or _secrets("vfcloud_senha")
        or os.getenv("VFCLOUD_SENHA", "")
        or ""
    ).strip()
    return usuario, senha


def call(action: str, usuario: str = "", senha: str = "", timeout: int = 180, **dados: Any) -> dict:
    """Chama o Web App. Devolve dict com ok=True/False."""
    if requests is None:
        raise RuntimeError("Dependência ausente: instale `requests`.")
    endpoint = url()
    if not endpoint:
        raise RuntimeError("Informe a URL do Web App do Visualfil Cloud.")
    u, s = credenciais()
    payload = {
        "action": action,
        "usuario": usuario or u,
        "senha": senha or s,
        **dados,
    }
    resposta = requests.post(endpoint, json=payload, timeout=timeout)
    if resposta.status_code >= 400:
        raise RuntimeError(f"HTTP {resposta.status_code}: {resposta.text[:200]}")
    try:
        resultado = resposta.json()
    except ValueError:
        trecho = re.sub(r"\s+", " ", resposta.text[:200])
        raise RuntimeError(f"O servidor não respondeu JSON. Trecho: {trecho}")
    if not isinstance(resultado, dict):
        raise RuntimeError("Resposta inesperada do servidor.")
    return resultado


# ============================ sessão / login ============================

def login(usuario: str, senha: str) -> dict:
    resultado = call("login", usuario=usuario, senha=senha, timeout=40)
    if resultado.get("ok"):
        configurar(usuario=usuario, senha=senha)
        st.session_state[CHAVE_SESSAO] = {
            "usuario": resultado.get("usuario") or usuario,
            "nome": resultado.get("nome") or usuario,
            "admin": bool(resultado.get("admin")),
        }
    return resultado


def logout() -> None:
    st.session_state.pop(CHAVE_SESSAO, None)


def logado() -> bool:
    return bool(st.session_state.get(CHAVE_SESSAO))


def usuario_atual() -> dict:
    return st.session_state.get(CHAVE_SESSAO) or {}


def eh_admin() -> bool:
    return bool(usuario_atual().get("admin"))


def permissoes() -> dict[str, str]:
    """Mapa {pagina: nivel} do usuário atual."""
    if eh_admin():
        return {p: "total" for p in PAGINAS}
    if not logado():
        return {}
    try:
        r = call("permissoes_listar", timeout=40)
    except Exception:
        return {}
    usuario = str(usuario_atual().get("usuario", "")).lower()
    return {
        str(x.get("pagina", "")): str(x.get("nivel", "visualizacao")).lower()
        for x in r.get("permissoes", [])
        if str(x.get("usuario", "")).lower() == usuario
    }


def nivel_pagina(pagina: str) -> str:
    perms = st.session_state.get("vf_permissoes_cache") or permissoes()
    return perms.get(pagina, "restrito")


def pode(pagina: str, nivel_minimo: str = "visualizacao") -> bool:
    ordem = {"restrito": 0, "visualizacao": 1, "total": 2}
    return ordem.get(nivel_pagina(pagina), -1) >= ordem.get(nivel_minimo, 1)


def carregar_permissoes() -> None:
    st.session_state["vf_permissoes_cache"] = permissoes()


# ============================ demandas ============================

def demandas() -> list[dict]:
    return call("demandas_listar", timeout=60).get("demandas", [])


def salvar_demanda(id: str, nome: str, fonte: str) -> dict:
    return call("demanda_salvar", id=id, nome=nome, fonte=fonte)


def excluir_demanda(id: str) -> dict:
    return call("demanda_excluir", id=id)


# ============================ arquivos ============================

def _valor_json(v):
    """Converts numpy/pandas scalars into JSON-safe values for Sheets."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        import numpy as np
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
    except Exception:
        pass
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    return str(v)


def salvar_arquivo(demanda_id: str, tipo: str, arquivo_bytes: bytes) -> dict:
    """Saves the XLSX in Drive AND writes its rows into a sheet tab in the main
    spreadsheet, so later reads are fast (no XLSX download/parse)."""
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(arquivo_bytes))
        colunas = [str(c) for c in df.columns]
        linhas = [[_valor_json(v) for v in row] for row in df.itertuples(index=False, name=None)]
        # limite de segurança do payload do Apps Script
        if len(linhas) > 50000:
            linhas = linhas[:50000]
    except Exception:
        colunas, linhas = [], []
    return call(
        "arquivo_salvar",
        demanda_id=demanda_id,
        tipo=tipo,
        colunas=colunas,
        linhas=linhas,
        base64=base64.b64encode(arquivo_bytes).decode("ascii"),
        timeout=240,
    )


def _df_de_linhas(colunas, linhas) -> "pd.DataFrame":
    import pandas as pd
    return pd.DataFrame(linhas or [], columns=colunas or [])


def ler_arquivo(demanda_id: str, tipo: str):
    """Devolve DataFrame quando a aba rápida existe; bytes do XLSX em fallback."""
    r = call("arquivo_ler", demanda_id=demanda_id, tipo=tipo, timeout=240)
    if r.get("colunas") is not None:
        return _df_de_linhas(r.get("colunas"), r.get("linhas"))
    return base64.b64decode(r.get("base64", ""))


def arquivar_demanda(demanda_id: str) -> dict:
    return call("demanda_arquivar", demanda_id=demanda_id, timeout=240)


def desarquivar_demanda(demanda_id: str) -> dict:
    return call("demanda_desarquivar", demanda_id=demanda_id, timeout=240)


def listar_arquivos(demanda_id: str) -> list[dict]:
    return call("arquivos_listar", demanda_id=demanda_id, timeout=60).get("arquivos", [])


# ============================ usuários / permissões ============================

def usuarios() -> list[dict]:
    return call("usuarios_listar", timeout=60).get("usuarios", [])


def salvar_usuario(usuario: str, nome: str, senha: str, admin: bool, ativo: bool) -> dict:
    return call(
        "usuario_salvar",
        usuario=usuario, nome=nome, senha=senha, admin=admin, ativo=ativo,
    )


def todas_permissoes() -> list[dict]:
    return call("permissoes_listar", timeout=60).get("permissoes", [])


def salvar_permissao(usuario: str, pagina: str, nivel: str) -> dict:
    return call("permissao_salvar", usuario=usuario, pagina=pagina, nivel=nivel)


# ============================ catálogo por confecção ============================

def catalogo() -> list[dict]:
    return call("catalogo_listar", timeout=60).get("catalogo", [])


def salvar_catalogo(itens: list[dict]) -> dict:
    return call("catalogo_salvar", itens=itens, timeout=240)


def excluir_catalogo(codigo: str) -> dict:
    return call("catalogo_excluir", codigo=codigo)


# ============================ análises salvas ============================

def salvar_analise(demanda_id: str, nome: str, dados: dict) -> dict:
    return call(
        "analise_salvar",
        demanda_id=demanda_id,
        nome=nome,
        dados_json=json.dumps(dados, ensure_ascii=False),
    )


def analises() -> list[dict]:
    return call("analises_listar", timeout=60).get("analises", [])
