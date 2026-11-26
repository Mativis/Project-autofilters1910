"""
Visualfil Reflex — interface profissional (React) para produção têxtil
=====================================================================
Versão paralela ao Streamlit, com:

* login e permissões por página aplicadas no cliente e no servidor;
* demandas online lidas do Google Sheets / Apps Script por demanda;
* Kanban online, compra sugerida, dashboards e projeção;
* Kanban de Confecção **offline**: upload local de Pedidos.xlsx + Estoque.xlsx,
  quadro operacional com movimentação, produção parcial, filtros e exportação.

O front-end usa o design system em ``tema.py``; as regras de negócio offline
estão em ``dados.py`` (sem dependência de Streamlit).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import pandas as pd
import reflex as rx
import requests

from . import dados, tema

# ============================ API / CLIENTE ============================


def api(action: str, _usuario: str = "", _senha: str = "", **params: Any) -> dict:
    """Chama o Web App. ``cred_*`` = quem chama; ``usuario`` = alvo (admin)."""
    url = os.getenv("VFCLOUD_URL", "")
    if not url:
        return {"ok": False, "erro": "Configure VFCLOUD_URL no arquivo run.bat (URL do Web App)."}
    extras = dict(params)
    alvo = extras.pop("usuario_alvo", None)
    cred_u = _usuario or os.getenv("VFCLOUD_USUARIO", "")
    cred_s = _senha if _senha else os.getenv("VFCLOUD_SENHA", "")
    corpo = {
        "action": action,
        **extras,
        "usuario": cred_u,
        "senha": cred_s,
        "cred_usuario": cred_u,
        "cred_senha": cred_s,
    }
    if alvo is not None:
        corpo["usuario"] = alvo
    resposta = requests.post(url, json=corpo, timeout=180)
    resposta.raise_for_status()
    return resposta.json()


def ler_xlsx(conteudo: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(conteudo))


def buscar_arquivos(
    demanda_id: str,
    usuario: str,
    senha: str,
    tipos: tuple[str, ...] = ("pedidos", "estoque", "producao"),
) -> tuple[dict, dict, str]:
    """Baixa vários XLSX em uma chamada; usa paralelo como fallback."""
    resposta = api(
        "arquivos_ler", _usuario=usuario, _senha=senha,
        demanda_id=demanda_id, tipos=list(tipos),
    )
    if resposta.get("ok") and "arquivos" in resposta:
        frames: dict[str, pd.DataFrame] = {}
        erros = dict(resposta.get("erros", {}))
        for tipo, conteudo in resposta["arquivos"].items():
            try:
                if isinstance(conteudo, dict) and "colunas" in conteudo:
                    frames[tipo] = pd.DataFrame(conteudo["linhas"], columns=conteudo["colunas"])
                elif isinstance(conteudo, dict):
                    frames[tipo] = ler_xlsx(base64.b64decode(conteudo["base64"]))
                else:
                    frames[tipo] = ler_xlsx(base64.b64decode(conteudo))
            except Exception as exc:
                erros[tipo] = str(exc)
        return frames, erros, "lote"

    def um(tipo: str):
        try:
            r = api("arquivo_ler", _usuario=usuario, _senha=senha,
                    demanda_id=demanda_id, tipo=tipo)
            if not r.get("ok"):
                return tipo, None, r.get("erro", "sem resposta")
            if r.get("colunas") is not None:
                return tipo, pd.DataFrame(r["linhas"], columns=r["colunas"]), None
            return tipo, ler_xlsx(base64.b64decode(r.get("base64", ""))), None
        except Exception as exc:
            return tipo, None, str(exc)

    frames, erros = {}, {}
    with ThreadPoolExecutor(max_workers=len(tipos)) as pool:
        for tipo, frame, erro in pool.map(um, tipos):
            if frame is not None:
                frames[tipo] = frame
            if erro:
                erros[tipo] = erro
    return frames, erros, "paralelo"


def salvar_agregado(demanda_id: str, usuario: str, senha: str, info: dict) -> dict:
    return api(
        "agregado_salvar", _usuario=usuario, _senha=senha, demanda_id=demanda_id,
        dados_json=json.dumps(info, ensure_ascii=False),
    )


def ler_agregado(demanda_id: str, usuario: str, senha: str) -> dict:
    return api("agregado_ler", _usuario=usuario, _senha=senha, demanda_id=demanda_id)


TIPOS = ("pedidos", "estoque", "producao", "projecao")
PAGINAS = (
    "Kanban de Confecção", "Dashboards de Pedidos", "Análise de Estoque",
    "Projeção Futuro", "Projeção por Confecção", "Painel Online", "Administração",
)
NIVEIS = ("visualizacao", "total", "restrito")

CACHE_DADOS: dict[tuple[str, str], dict] = {}
CACHE_TTL = 300


def _chave_cache(demanda_id: str, usuario: str = "") -> tuple[str, str]:
    return (str(usuario or "").lower(), str(demanda_id or ""))


def cache_validar(demanda_id: str, usuario: str = "") -> bool:
    item = CACHE_DADOS.get(_chave_cache(demanda_id, usuario))
    return bool(item) and (time.time() - item.get("ts", 0)) < CACHE_TTL


def cache_guardar(demanda_id: str, info: dict, usuario: str = ""):
    CACHE_DADOS[_chave_cache(demanda_id, usuario)] = {"ts": time.time(), "derivados": info}


def cache_limpar(demanda_id: str = "", usuario: str = ""):
    if demanda_id:
        CACHE_DADOS.pop(_chave_cache(demanda_id, usuario), None)
    elif usuario:
        u = str(usuario or "").lower()
        for chave in list(CACHE_DADOS):
            if chave[0] == u:
                CACHE_DADOS.pop(chave, None)
    else:
        CACHE_DADOS.clear()


# ============================ ESTADO ============================


class State(rx.State):
    # ----- sessão (campos privados não vão para o navegador) -----
    _usuario: str = ""
    _senha: str = ""
    logado: bool = False
    admin: bool = False
    nome: str = ""
    permissoes_minhas: list[dict] = []
    mensagem: str = ""
    tipo_mensagem: str = "info"

    # ----- demandas online -----
    demandas: list[dict] = []
    demanda_opcoes: list[str] = []
    demanda_id: str = ""
    demanda_nome: str = ""
    nova_demanda: str = ""
    nova_fonte: str = ""
    arquivos_info: list[dict] = []
    carregando: bool = False
    diagnostico: str = ""

    pedidos: list[dict] = []
    compra_itens: list[dict] = []
    compra_resumo: list[dict] = []
    total_compra: str = "0"
    capacidade: list[dict] = []
    por_confeccao: list[dict] = []
    por_status: list[dict] = []
    por_prioridade: list[dict] = []
    info_ped: str = "—"
    info_est: str = "—"
    info_prod: str = "—"

    # ----- administração -----
    usuarios: list[dict] = []
    usuario_opcoes: list[str] = []
    permissoes: list[dict] = []
    novo_usuario: str = ""
    novo_nome: str = ""
    nova_senha: str = ""
    novo_admin: bool = False
    perm_usuario: str = ""
    perm_pagina: str = PAGINAS[0]
    perm_nivel: str = "visualizacao"

    # ----- Kanban de Confecção (offline) -----
    _ped_linhas: list[dict] = []
    _est_linhas: list[dict] = []
    _ped_b64: str = ""
    _est_b64: str = ""
    off_ped_nome: str = ""
    off_est_nome: str = ""
    off_pronto: bool = False
    off_processando: bool = False
    off_cards: list[dict] = []
    off_kpis: dict = {}
    off_classificacao: list[dict] = []
    off_confeccoes: list[dict] = []
    off_avisos: list[str] = []
    off_total_qe: str = "0"
    off_negativos: str = "0"
    off_retornos: str = "—"
    off_fator: float = dados.FATOR_PADRAO
    off_desconsiderar_baixo: bool = True
    off_termo: str = ""
    off_segmento: str = "Todos"
    off_prioridade: str = "Todas"
    off_confeccao: str = "Todas"
    off_ordem: str = "Entrega"
    off_ocultar_entregues: bool = False
    off_selecionados: list[str] = []
    off_limite: int = 60
    off_destino_lote: str = "Em andamento"
    off_parcial_chave: str = ""
    off_parcial_pronta: str = "0"
    off_parcial_quebra: str = "0"
    off_mostrar_parcial: bool = False

    # ---------------------------------------------------------------- permissões
    @rx.var
    def pode_online(self) -> bool:
        return self.admin or any(
            str(p.get("pagina", "")) == "Painel Online" for p in self.permissoes_minhas
        )

    @rx.var
    def pode_dashboards(self) -> bool:
        return self.admin or any(
            str(p.get("pagina", "")) == "Dashboards de Pedidos" for p in self.permissoes_minhas
        )

    @rx.var
    def pode_kanban_off(self) -> bool:
        return self.admin or any(
            str(p.get("pagina", "")) == "Kanban de Confecção" for p in self.permissoes_minhas
        )

    @rx.var
    def pode_projecao(self) -> bool:
        return self.admin or any(
            str(p.get("pagina", "")) in ("Projeção Futuro", "Projeção por Confecção")
            for p in self.permissoes_minhas
        )

    @rx.var
    def pode_admin(self) -> bool:
        return bool(self.admin)

    def _acesso(self, pagina: str):
        if not self.logado:
            return rx.redirect("/")
        if self.admin:
            return None
        permitidas = {
            str(p.get("pagina", "")): str(p.get("nivel", ""))
            for p in self.permissoes_minhas
        }
        if permitidas.get(pagina) in NIVEIS:
            return None
        return rx.redirect("/sem-acesso")

    def aviso(self, texto: str, tipo: str = "info"):
        self.mensagem = texto
        self.tipo_mensagem = tipo

    def limpar_aviso(self):
        self.mensagem = ""

    # setters explícitos (evita depender de auto-setters em versões antigas)
    def set_nova_demanda(self, valor: str): self.nova_demanda = valor
    def set_nova_fonte(self, valor: str): self.nova_fonte = valor
    def set_novo_usuario(self, valor: str): self.novo_usuario = valor
    def set_novo_nome(self, valor: str): self.novo_nome = valor
    def set_nova_senha(self, valor: str): self.nova_senha = valor
    def set_novo_admin(self, valor: bool): self.novo_admin = valor
    def set_perm_usuario(self, valor: str): self.perm_usuario = valor
    def set_perm_pagina(self, valor: str): self.perm_pagina = valor
    def set_perm_nivel(self, valor: str): self.perm_nivel = valor
    def set_demanda_nome(self, valor: str): self.selecionar_demanda(valor)
    def set_off_termo(self, valor: str): self.off_termo = valor
    def set_off_segmento(self, valor: str): self.off_segmento = valor
    def set_off_prioridade(self, valor: str): self.off_prioridade = valor
    def set_off_confeccao(self, valor: str): self.off_confeccao = valor
    def set_off_ordem(self, valor: str): self.off_ordem = valor
    def set_off_fator(self, valor: str):
        try:
            self.off_fator = min(3.0, max(1.0, float(str(valor).replace(",", "."))))
        except (TypeError, ValueError):
            pass
        self.reprocessar_offline()
    def set_off_baixo(self, valor: bool):
        self.off_desconsiderar_baixo = valor
        self.reprocessar_offline()
    def set_off_ocultar(self, valor: bool): self.off_ocultar_entregues = valor
    def set_off_destino_lote(self, valor: str): self.off_destino_lote = valor
    def set_parcial_pronta(self, valor: str): self.off_parcial_pronta = valor
    def set_parcial_quebra(self, valor: str): self.off_parcial_quebra = valor

    # ---------------------------------------------------------------- auth
    def entrar(self, form_data: dict):
        try:
            self._usuario = str(form_data.get("usuario", "")).strip()
            self._senha = str(form_data.get("senha", ""))
            resposta = api("login", _usuario=self._usuario, _senha=self._senha)
            if not resposta.get("ok"):
                self.aviso(resposta.get("erro", "Falha no login."), "error")
                return
            self.logado = True
            self.admin = bool(resposta.get("admin"))
            self.nome = resposta.get("nome") or self._usuario
            try:
                perm = api("permissoes_minhas", _usuario=self._usuario, _senha=self._senha)
                self.permissoes_minhas = perm.get("permissoes", [])
            except Exception:
                self.permissoes_minhas = []
            self.aviso("", "info")
            return rx.redirect(self.destino_inicial())
        except Exception as exc:
            self.aviso(str(exc), "error")

    def destino_inicial(self) -> str:
        """Leva o usuário à primeira área que ele realmente pode acessar."""
        if self.admin or any(
            str(p.get("pagina", "")) == "Kanban de Confecção" for p in self.permissoes_minhas
        ):
            return "/kanban-offline"
        if self.pode_online:
            return "/kanban"
        if self.pode_dashboards:
            return "/dashboards"
        if self.pode_projecao:
            return "/projecao"
        return "/sem-acesso"

    def sair(self):
        cache_limpar(usuario=self._usuario)
        self._usuario = self._senha = self.nome = ""
        self.logado = False
        self.admin = False
        self.permissoes_minhas = []
        self.off_cards = []
        self.off_pronto = False
        self.pedidos = []
        self.compra_itens = []
        return rx.redirect("/")

    def verificar_login(self):
        if not self.logado:
            return rx.redirect("/")

    def verificar_admin(self):
        if not self.logado:
            return rx.redirect("/")
        if not self.admin:
            return rx.redirect("/sem-acesso")

    # ---------------------------------------------------------------- carga on_load
    def iniciar_online(self):
        redirect = self._acesso("Painel Online")
        if redirect:
            return redirect
        return self.carregar_demandas()

    def iniciar_dashboards(self):
        redirect = self._acesso("Dashboards de Pedidos")
        if redirect:
            return redirect
        return self.carregar_demandas()

    def iniciar_projecao(self):
        redirect = self._acesso("Projeção Futuro")
        if redirect:
            return redirect
        return self.carregar_demandas()

    def iniciar_admin(self):
        redirect = self.verificar_admin()
        if redirect:
            return redirect
        return self.carregar_admin()

    def iniciar_offline(self):
        return self._acesso("Kanban de Confecção")

    # ---------------------------------------------------------------- demandas
    def carregar_demandas(self):
        redirect = self.verificar_login()
        if redirect:
            return redirect
        try:
            resposta = api("demandas_listar", _usuario=self._usuario, _senha=self._senha)
            self.demandas = resposta.get("demandas", [])
            self.demanda_opcoes = [
                str(d.get("nome", "")) or str(d.get("id", "")) for d in self.demandas
            ]
        except Exception as exc:
            self.aviso(str(exc), "error")

    def selecionar_demanda(self, nome: str):
        self.demanda_nome = nome
        item = next(
            (d for d in self.demandas
             if (str(d.get("nome", "")) or str(d.get("id", ""))) == nome), {}
        )
        self.demanda_id = str(item.get("id", ""))

    def criar_demanda(self):
        if not self.nova_demanda.strip():
            self.aviso("Informe o nome da demanda.", "error")
            return
        try:
            resposta = api(
                "demanda_salvar", _usuario=self._usuario, _senha=self._senha,
                nome=self.nova_demanda.strip(), fonte=self.nova_fonte.strip(),
            )
            if resposta.get("ok"):
                self.nova_demanda = self.nova_fonte = ""
                self.aviso("Demanda criada com sucesso.", "success")
                self.carregar_demandas()
            else:
                self.aviso(resposta.get("erro", "Erro ao criar demanda."), "error")
        except Exception as exc:
            self.aviso(str(exc), "error")

    async def enviar_arquivo(self, files: list[rx.UploadFile]):
        if not self.demanda_id:
            self.aviso("Selecione uma demanda antes de enviar.", "error")
            return
        if not files:
            self.aviso("Selecione um arquivo.", "error")
            return
        arquivo = files[0]
        conteudo = await arquivo.read()
        base = unicodedata.normalize("NFKD", arquivo.filename.split(".")[0])
        base = "".join(ch for ch in base if not unicodedata.combining(ch))
        tipo = re.sub(r"[^a-z0-9]", "", base.lower())
        if tipo not in TIPOS:
            self.aviso(
                f"Nome não reconhecido: {arquivo.filename}. "
                "Use pedidos.xlsx, estoque.xlsx, producao.xlsx ou projecao.xlsx.",
                "error",
            )
            return
        try:
            try:
                frame = pd.read_excel(io.BytesIO(conteudo))
                colunas = [str(c) for c in frame.columns]
                linhas = [
                    [str(v) if v is not None else "" for v in row]
                    for row in frame.itertuples(index=False, name=None)
                ]
            except Exception:
                colunas, linhas = [], []
            resposta = api(
                "arquivo_salvar", _usuario=self._usuario, _senha=self._senha,
                demanda_id=self.demanda_id, tipo=tipo, colunas=colunas, linhas=linhas,
                usar_aba_rapida=bool(colunas), base64=base64.b64encode(conteudo).decode(),
            )
            cache_limpar(self.demanda_id, self._usuario)
            self.aviso(
                f"{tipo}.xlsx enviado." if resposta.get("ok")
                else resposta.get("erro", "Erro no envio."),
                "success" if resposta.get("ok") else "error",
            )
        except Exception as exc:
            self.aviso(str(exc), "error")

    # ---------------------------------------------------------------- dados online
    def carregar_dados(self):
        self._carregar(forcado=False)

    def atualizar_dados(self):
        cache_limpar(self.demanda_id, self._usuario)
        self._carregar(forcado=True)

    def _carregar(self, forcado: bool):
        if not self.demanda_id:
            self.aviso("Selecione uma demanda antes de carregar.", "error")
            return
        if not forcado and cache_validar(self.demanda_id, self._usuario):
            self._aplicar_info(CACHE_DADOS[_chave_cache(self.demanda_id, self._usuario)]["derivados"])
            self.diagnostico = "⚡ Cache local (instantâneo). Use Atualizar para recarregar."
            self.aviso("", "info")
            return

        self.carregando = True
        if not forcado:
            self.diagnostico = "Buscando pré-agregação no servidor..."
            try:
                agg = ler_agregado(self.demanda_id, self._usuario, self._senha)
                if agg.get("ok") and agg.get("dados"):
                    self._aplicar_info(agg["dados"])
                    self.diagnostico = (
                        f"⚡ Pré-agregado de {str(agg.get('atualizado_em', ''))[:10]} · "
                        f"sem download de XLSX · {len(self.pedidos)} pedidos"
                    )
                    self.aviso("", "info")
                    return
            except Exception:
                pass

        try:
            frames, erros, modo = buscar_arquivos(
                self.demanda_id, self._usuario, self._senha
            )
            ped = frames.get("pedidos", pd.DataFrame())
            est = frames.get("estoque", pd.DataFrame())
            prod = frames.get("producao", pd.DataFrame())
            try:
                catalogo = api("catalogo_listar", _usuario=self._usuario, _senha=self._senha).get("catalogo", [])
            except Exception:
                catalogo = []

            self.info_ped = f"{len(ped)} linhas" if not ped.empty else "vazio/ausente"
            self.info_est = f"{len(est)} linhas" if not est.empty else "vazio/ausente"
            self.info_prod = f"{len(prod)} linhas" if not prod.empty else "vazio/ausente"

            self.pedidos = dados.montar_kanban_online(ped, est)
            self.compra_itens, self.compra_resumo, self.total_compra = dados.montar_compra(est, catalogo)
            self.capacidade = dados.montar_capacidade(prod)
            self.por_confeccao = dados.agrupar(self.pedidos, "Confecção")
            self.por_status = dados.agrupar(self.pedidos, "Prioridade")
            self.por_prioridade = dados.agrupar(self.pedidos, "Prioridade")

            info = {
                "pedidos": self.pedidos, "compra_itens": self.compra_itens,
                "compra_resumo": self.compra_resumo, "total_compra": self.total_compra,
                "capacidade": self.capacidade, "por_confeccao": self.por_confeccao,
                "por_status": self.por_status, "por_prioridade": self.por_prioridade,
                "info_ped": self.info_ped, "info_est": self.info_est, "info_prod": self.info_prod,
            }
            cache_guardar(self.demanda_id, info, self._usuario)
            try:
                salvar_agregado(self.demanda_id, self._usuario, self._senha, info)
            except Exception:
                pass

            if erros:
                self.diagnostico = "Modo " + modo + " · " + " | ".join(
                    f"{k}: {v}" for k, v in erros.items()
                )
                self.aviso("Alguns arquivos não carregaram.", "error")
            else:
                self.diagnostico = (
                    f"⚡ {modo} · pedidos {self.info_ped} · estoque {self.info_est} · "
                    f"produção {self.info_prod} · {len(self.pedidos)} pedidos"
                )
                self.aviso("", "info")
        except Exception as exc:
            self.diagnostico = f"Erro geral: {exc}"
            self.aviso(f"Erro ao processar: {exc}", "error")
        finally:
            self.carregando = False

    def _aplicar_info(self, info: dict):
        self.pedidos = info.get("pedidos", [])
        self.compra_itens = info.get("compra_itens", [])
        self.compra_resumo = info.get("compra_resumo", [])
        self.total_compra = info.get("total_compra", "0")
        self.capacidade = info.get("capacidade", [])
        self.por_confeccao = info.get("por_confeccao", [])
        self.por_status = info.get("por_status", [])
        self.por_prioridade = info.get("por_prioridade", [])
        self.info_ped = info.get("info_ped", "—")
        self.info_est = info.get("info_est", "—")
        self.info_prod = info.get("info_prod", "—")

    def testar_conexao(self):
        try:
            resposta = api("ping", _usuario=self._usuario, _senha=self._senha)
            self.diagnostico = str(resposta)
            self.aviso("API respondeu: " + str(resposta.get("versao", "ok")), "success")
        except Exception as exc:
            self.diagnostico = f"Ping falhou: {exc}"
            self.aviso(str(exc), "error")

    def ver_arquivos(self):
        if not self.demanda_id:
            self.aviso("Selecione uma demanda.", "error")
            return
        try:
            resposta = api("arquivos_listar", _usuario=self._usuario, _senha=self._senha,
                           demanda_id=self.demanda_id)
            self.arquivos_info = resposta.get("arquivos", [])
            self.diagnostico = (
                "Arquivos: " + ", ".join(
                    f"{a.get('nome')} ({a.get('tamanho')}b)" for a in self.arquivos_info
                )
            ) if self.arquivos_info else "Nenhum arquivo enviado para esta demanda."
        except Exception as exc:
            self.aviso(str(exc), "error")

    def salvar_analise(self):
        try:
            resposta = api(
                "analise_salvar", _usuario=self._usuario, _senha=self._senha,
                demanda_id=self.demanda_id, nome="Análise Reflex",
                dados_json=json.dumps(
                    {"resumo": self.compra_resumo, "pedidos": len(self.pedidos)},
                    ensure_ascii=False,
                ),
            )
            self.aviso("Análise salva." if resposta.get("ok")
                       else resposta.get("erro", "Erro"), "success" if resposta.get("ok") else "error")
        except Exception as exc:
            self.aviso(str(exc), "error")

    # ---------------------------------------------------------------- admin
    def carregar_admin(self):
        redirect = self.verificar_admin()
        if redirect:
            return redirect
        try:
            self.usuarios = api(
                "usuarios_listar", _usuario=self._usuario, _senha=self._senha
            ).get("usuarios", [])
            self.usuario_opcoes = [
                str(u.get("usuario", "")) for u in self.usuarios if u.get("usuario")
            ]
            self.permissoes = api(
                "permissoes_listar", _usuario=self._usuario, _senha=self._senha
            ).get("permissoes", [])
            self.carregar_demandas()
        except Exception as exc:
            self.aviso(str(exc), "error")

    def criar_usuario(self):
        try:
            resposta = api(
                "usuario_salvar", _usuario=self._usuario, _senha=self._senha,
                usuario_alvo=self.novo_usuario.strip(), nome=self.novo_nome.strip(),
                senha_nova=self.nova_senha, admin=self.novo_admin, ativo=True,
            )
            if resposta.get("ok"):
                self.aviso("Usuário salvo.", "success")
                self.novo_usuario = self.novo_nome = self.nova_senha = ""
                self.carregar_admin()
            else:
                self.aviso(resposta.get("erro", "Erro"), "error")
        except Exception as exc:
            self.aviso(str(exc), "error")

    def salvar_permissao(self):
        try:
            resposta = api(
                "permissao_salvar", _usuario=self._usuario, _senha=self._senha,
                usuario_alvo=self.perm_usuario, pagina=self.perm_pagina, nivel=self.perm_nivel,
            )
            self.aviso("Permissão salva." if resposta.get("ok")
                       else resposta.get("erro", "Erro"), "success" if resposta.get("ok") else "error")
            self.carregar_admin()
        except Exception as exc:
            self.aviso(str(exc), "error")

    # ---------------------------------------------------------------- offline: upload
    async def carregar_offline(self, files: list[rx.UploadFile]):
        if not files:
            self.aviso("Selecione Pedidos.xlsx e Estoque.xlsx.", "error")
            return
        self.off_processando = True
        try:
            for arquivo in files:
                conteudo = await arquivo.read()
                nome = unicodedata.normalize("NFKD", arquivo.filename.split(".")[0])
                nome = "".join(ch for ch in nome if not unicodedata.combining(ch))
                tipo = re.sub(r"[^a-z0-9]", "", nome.lower())
                if "pedido" in tipo:
                    self._ped_b64 = base64.b64encode(conteudo).decode()
                    self.off_ped_nome = arquivo.filename
                elif "estoque" in tipo:
                    self._est_b64 = base64.b64encode(conteudo).decode()
                    self.off_est_nome = arquivo.filename
            if not self._ped_b64 or not self._est_b64:
                falta = "Estoque.xlsx" if self._ped_b64 else "Pedidos.xlsx"
                self.aviso(f"Recebido. Falta enviar {falta}.", "info")
                return
            ped = ler_xlsx(base64.b64decode(self._ped_b64))
            est = ler_xlsx(base64.b64decode(self._est_b64))
            self._ped_linhas = ped.to_dict(orient="records")
            self._est_linhas = est.to_dict(orient="records")
            self.off_pronto = True
            self.off_selecionados = []
            self.off_limite = 60
            self.reprocessar_offline()
        except Exception as exc:
            self.aviso(f"Erro ao ler os arquivos: {exc}", "error")
        finally:
            self.off_processando = False

    def reprocessar_offline(self):
        if not self._ped_linhas or not self._est_linhas:
            return
        ped = pd.DataFrame(self._ped_linhas)
        est = pd.DataFrame(self._est_linhas)
        info = dados.montar_offline(
            ped, est, fator=self.off_fator,
            desconsiderar_baixo=self.off_desconsiderar_baixo,
        )
        # preserva o que já foi operado no quadro
        anteriores = {c["chave"]: c for c in self.off_cards}
        for cartao in info["cards"]:
            antigo = anteriores.get(cartao["chave"])
            if antigo:
                for chave in ("status", "qtd_pronta", "qtd_quebra", "status_por", "status_em"):
                    cartao[chave] = antigo.get(chave, cartao[chave])
        self.off_cards = info["cards"]
        self.off_kpis = info["kpis"]
        self.off_classificacao = info["resumo_classificacao"]
        self.off_confeccoes = info["resumo_confeccao"]
        self.off_avisos = info["avisos"]
        self.off_total_qe = dados.fmt_num(info["total_qe"])
        self.off_negativos = str(info["codigos_negativos"])
        self.off_retornos = info["retornos"]

    # ---------------------------------------------------------------- offline: filtros
    @rx.var
    def off_opcoes_confeccao(self) -> list[str]:
        return ["Todas"] + sorted({str(c.get("confeccao", "")) for c in self.off_cards})

    @rx.var
    def off_opcoes_prioridade(self) -> list[str]:
        return ["Todas"] + list(dados.PRIORIDADES)

    @rx.var
    def off_filtrados(self) -> list[dict]:
        termo = self.off_termo.strip().lower()
        out = []
        for c in self.off_cards:
            if termo and not any(
                termo in str(c.get(chave, "")).lower()
                for chave in ("pedido", "codigo", "item", "confeccao", "marca")
            ):
                continue
            if self.off_prioridade != "Todas" and c.get("prioridade") != self.off_prioridade:
                continue
            if self.off_confeccao != "Todas" and c.get("confeccao") != self.off_confeccao:
                continue
            if self.off_segmento == "Futuros" and c.get("classificacao") != "Aguardando envio":
                continue
            if self.off_segmento == "Abertos" and c.get("classificacao") not in (
                "Aguardando produção", "Aguardando saldo", "Sem classificação"
            ):
                continue
            if self.off_segmento == "Concluídos" and c.get("status") not in ("Pronto", "Entregue"):
                continue
            if self.off_ocultar_entregues and c.get("status") == "Entregue":
                continue
            out.append(dict(c))
        peso = dados.PESO_PRIORIDADE
        if self.off_ordem == "Prioridade":
            out.sort(key=lambda c: (peso.get(c.get("prioridade"), 9), c.get("entrega", "")))
        elif self.off_ordem == "Quantidade":
            out.sort(key=lambda c: -(c.get("saldo") or 0))
        elif self.off_ordem == "Pedido":
            out.sort(key=lambda c: str(c.get("pedido", "")))
        else:
            out.sort(key=lambda c: (peso.get(c.get("prioridade"), 9), c.get("entrega", "")))
        return out

    @rx.var
    def off_col_pendente(self) -> list[dict]:
        return [c for c in self.off_filtrados if c.get("status") == "Pendente"][:self.off_limite]

    @rx.var
    def off_col_andamento(self) -> list[dict]:
        return [c for c in self.off_filtrados if c.get("status") == "Em andamento"][:self.off_limite]

    @rx.var
    def off_col_pronto(self) -> list[dict]:
        return [c for c in self.off_filtrados if c.get("status") == "Pronto"][:self.off_limite]

    @rx.var
    def off_col_entregue(self) -> list[dict]:
        return [c for c in self.off_filtrados if c.get("status") == "Entregue"][:self.off_limite]

    @rx.var
    def off_pode_mostrar_mais(self) -> bool:
        return any(
            sum(c.get("status") == s for c in self.off_filtrados) > self.off_limite
            for s in dados.STATUS
        )

    def mostrar_mais(self):
        self.off_limite += 60

    def mostrar_menos(self):
        self.off_limite = max(60, self.off_limite - 60)

    @rx.var
    def off_qtd_filtrada(self) -> str:
        return str(len(self.off_filtrados))

    # ---------------------------------------------------------------- offline: operação
    def _cartao(self, chave: str) -> dict | None:
        return next((c for c in self.off_cards if c["chave"] == chave), None)

    def mover_off(self, chave: str, destino: str):
        cartao = self._cartao(chave)
        if cartao is None:
            return
        origem = cartao["status"]
        if destino not in dados.TRANSICOES.get(origem, ()):
            self.aviso(f"Transição inválida: {origem} → {destino}.", "error")
            return
        saldo = float(cartao.get("saldo") or 0)
        quebra = float(cartao.get("qtd_quebra") or 0)
        if destino == "Pendente":
            cartao["qtd_quebra"] = 0.0
            cartao["qtd_pronta"] = 0.0
        if destino in ("Pronto", "Entregue"):
            cartao["qtd_pronta"] = max(0.0, saldo - quebra)
        cartao["status"] = destino
        cartao["status_por"] = self.nome or self._usuario
        cartao["status_em"] = datetime.now().strftime("%d/%m %H:%M")
        self.off_selecionados = [c for c in self.off_selecionados if c != chave]
        self.aviso(f"Pedido {cartao['pedido']} movido para {dados.ROTULO_STATUS[destino]}.", "success")

    def selecionar_off(self, chave: str, valor: bool):
        if valor and chave not in self.off_selecionados:
            self.off_selecionados = [*self.off_selecionados, chave]
        elif not valor:
            self.off_selecionados = [c for c in self.off_selecionados if c != chave]

    def selecionar_todos_off(self, valor: bool):
        self.off_selecionados = [c["chave"] for c in self.off_filtrados] if valor else []

    def mover_lote_off(self):
        if not self.off_selecionados:
            self.aviso("Selecione pelo menos um pedido.", "error")
            return
        destino = self.off_destino_lote
        movidos = 0
        for chave in list(self.off_selecionados):
            cartao = self._cartao(chave)
            if cartao and destino in dados.TRANSICOES.get(cartao["status"], ()):
                self.mover_off(chave, destino)
                movidos += 1
        self.off_selecionados = []
        self.aviso(f"{movidos} pedido(s) movido(s) para {dados.ROTULO_STATUS.get(destino, destino)}.", "success")

    def abrir_parcial(self, chave: str):
        cartao = self._cartao(chave)
        if cartao is None:
            return
        self.off_parcial_chave = chave
        self.off_parcial_pronta = str(int(cartao.get("qtd_pronta") or 0))
        self.off_parcial_quebra = str(int(cartao.get("qtd_quebra") or 0))
        self.off_mostrar_parcial = True

    def fechar_parcial(self):
        self.off_mostrar_parcial = False
        self.off_parcial_chave = ""

    def registrar_parcial(self):
        cartao = self._cartao(self.off_parcial_chave)
        if cartao is None:
            self.fechar_parcial()
            return
        try:
            pronta = max(0.0, float(self.off_parcial_pronta.replace(",", ".")))
            quebra = max(0.0, float(self.off_parcial_quebra.replace(",", ".")))
        except (TypeError, ValueError):
            self.aviso("Informe quantidades numéricas válidas.", "error")
            return
        saldo = float(cartao.get("saldo") or 0)
        if pronta + quebra > saldo + 0.001:
            self.aviso(f"Pronta + quebra não pode ultrapassar o saldo ({dados.fmt_num(saldo)}).", "error")
            return
        cartao["qtd_pronta"] = pronta
        cartao["qtd_quebra"] = quebra
        cartao["status_por"] = self.nome or self._usuario
        cartao["status_em"] = datetime.now().strftime("%d/%m %H:%M")
        if pronta + quebra >= saldo - 0.001:
            cartao["status"] = "Pronto"
            cartao["qtd_pronta"] = max(0.0, saldo - quebra)
        elif cartao["status"] == "Pendente" and pronta + quebra > 0:
            cartao["status"] = "Em andamento"
        self.fechar_parcial()
        self.aviso("Produção parcial registrada.", "success")

    def exportar_csv_off(self):
        colunas = (
            "pedido", "codigo", "item", "confeccao", "marca", "qtd", "saldo", "qe",
            "retornado", "retorno_pct", "entrega", "prioridade", "classificacao",
            "status", "qtd_pronta", "qtd_quebra", "status_por", "status_em",
        )
        linhas = [";".join(str(c.get(k, "")).replace(";", " ") for k in colunas)
                  for c in self.off_filtrados]
        csv = ";".join(colunas) + "\n" + "\n".join(linhas)
        return rx.download(
            data="\ufeff" + csv,
            filename="kanban_confeccao_offline.csv",
            mime_type="text/csv;charset=utf-8",
        )

    def limpar_offline(self):
        self._ped_linhas = []
        self._est_linhas = []
        self._ped_b64 = self._est_b64 = ""
        self.off_limite = 60
        self.off_cards = []
        self.off_kpis = {}
        self.off_classificacao = []
        self.off_confeccoes = []
        self.off_pronto = False
        self.off_ped_nome = self.off_est_nome = ""
        self.off_selecionados = []
        self.aviso("Dados locais removidos.", "info")


# ============================ COMPONENTES ============================


def botao(texto: str, icone: str = "", onclick=None, variante: str = "solid",
          tamanho: str = "2", cor: str = "indigo", largura: str = "auto") -> rx.Component:
    return rx.button(
        rx.hstack(
            rx.icon(icone, size=15) if icone else rx.fragment(),
            rx.text(texto),
            spacing="2", align_items="center",
        ),
        on_click=onclick,
        variant=variante,
        color_scheme=cor,
        size=tamanho,
        width=largura,
    )


def campo(label: str, controle: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color=tema.C["muted"], font_weight="600"),
        controle,
        spacing="1", align_items="start", width="100%",
    )


def painel(titulo: str, conteudo: rx.Component, acao: rx.Component | None = None) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading(titulo, size="5", color=tema.C["text"]),
            rx.spacer(),
            acao if acao is not None else rx.fragment(),
            width="100%", align_items="center",
        ),
        conteudo,
        spacing="3", width="100%",
    )


def seletor_demanda() -> rx.Component:
    return tema.superficie(
        rx.vstack(
            rx.hstack(
                campo(
                    "Demanda (Remessa)",
                    rx.select(
                        State.demanda_opcoes, value=State.demanda_nome,
                        on_change=State.set_demanda_nome,
                        placeholder="Selecione a demanda", width="330px",
                    ),
                ),
                rx.vstack(rx.text(" ", size="1"), botao("Carregar", "refresh-cw", State.carregar_dados)),
                botao("Atualizar", "database-zap", State.atualizar_dados, "soft"),
                rx.cond(State.carregando, rx.spinner(size="2")),
                rx.spacer(),
                botao("Testar API", "plug-zap", State.testar_conexao, "soft", "1"),
                botao("Arquivos", "folder-open", State.ver_arquivos, "soft", "1"),
                spacing="3", align_items="end", width="100%", wrap="wrap",
            ),
            rx.hstack(
                tema.chip("Pedidos: " + State.info_ped, tema.C["info"]),
                tema.chip("Estoque: " + State.info_est, tema.C["violet"]),
                tema.chip("Produção: " + State.info_prod, tema.C["warning"]),
                rx.spacer(),
                rx.text(State.diagnostico, size="1", color=tema.C["muted"], text_align="right"),
                spacing="2", width="100%", wrap="wrap",
            ),
            spacing="3", width="100%",
        ),
        padding="1rem",
    )


def kpis_online() -> rx.Component:
    return rx.grid(
        tema.kpi("Pedidos no quadro", State.pedidos.length(), "filtrados por Saldo 2", "package", tema.C["primary"]),
        tema.kpi("Itens para compra", State.compra_itens.length(), "códigos negativos", "shopping-cart", tema.C["danger"]),
        tema.kpi("Total sugerido", State.total_compra, "unidades", "coins", tema.C["warning"]),
        tema.kpi("Confecções", State.por_confeccao.length(), "com pedidos", "users", tema.C["violet"]),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="3", width="100%",
    )


def cartao_online(pedido: rx.Component) -> rx.Component:
    return tema.superficie(
        rx.vstack(
            rx.hstack(
                rx.text("#", color=tema.C["muted"], size="1"),
                rx.text(pedido["Pedido"], weight="bold", size="3"),
                rx.spacer(),
                tema.prioridade_chip(pedido["Prioridade"]),
                spacing="2", width="100%",
            ),
            rx.text(pedido["Item"], size="2", color=tema.C["text"], line_clamp="2"),
            rx.hstack(
                tema.chip(pedido["Código"], tema.C["info"]),
                tema.chip(pedido["Marca"], tema.C["muted"]),
                rx.spacer(),
                rx.text(pedido["Saldo"], size="2", weight="bold"),
                rx.text("un.", size="1", color=tema.C["muted"]),
                spacing="2", width="100%", wrap="wrap",
            ),
            rx.text(pedido["Confecção"], size="1", color=tema.C["muted"]),
            spacing="2", width="100%",
        ),
        class_name="vf-card", padding="0.9rem", min_width="240px",
    )


def coluna_online(titulo: str, cor: str, itens: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(width="9px", height="9px", border_radius="50%", background=cor),
            rx.text(titulo, weight="bold", size="2"),
            rx.badge(itens.length(), variant="soft", color_scheme="gray"),
            spacing="2", align_items="center", width="100%",
        ),
        rx.box(
            rx.foreach(itens, cartao_online),
            class_name="vf-board vf-scroll", padding="0.5rem",
            background="#f8fafc", border_radius="12px", width="100%",
            max_height="560px", overflow_y="auto",
        ),
        spacing="2", flex="1", min_width="260px",
    )


# ---------------------------------------------------------------- Kanban offline

def cor_status_var(status: rx.Component) -> rx.Component:
    return rx.match(
        status,
        ("Pendente", tema.COR_STATUS_PENDENTE),
        ("Em andamento", tema.COR_STATUS_ANDAMENTO),
        ("Pronto", tema.COR_STATUS_PRONTO),
        ("Entregue", tema.COR_STATUS_ENTREGUE),
        tema.C["muted"],
    )


def botao_movimento(cartao: rx.Component, destino: str) -> rx.Component:
    return rx.button(
        dados.ROTULO_MOV[destino],
        size="1",
        variant="soft",
        color_scheme=tema._scheme(tema.CORES_STATUS.get(destino, tema.C["primary"])),
        on_click=State.mover_off(cartao["chave"], destino),
        width="100%",
    )


def movimentos_off(cartao: rx.Component) -> rx.Component:
    return rx.match(
        cartao["status"],
        ("Pendente", botao_movimento(cartao, "Em andamento")),
        ("Em andamento", rx.hstack(
            botao_movimento(cartao, "Pendente"),
            botao_movimento(cartao, "Pronto"),
            spacing="1", width="100%",
        )),
        ("Pronto", rx.hstack(
            botao_movimento(cartao, "Em andamento"),
            botao_movimento(cartao, "Entregue"),
            spacing="1", width="100%",
        )),
        ("Entregue", botao_movimento(cartao, "Pronto")),
        rx.fragment(),
    )


def cartao_off(cartao: rx.Component) -> rx.Component:
    saldo = cartao["saldo"].to(float)
    total = cartao["qtd_pronta"].to(float) + cartao["qtd_quebra"].to(float)
    progresso = rx.cond(
        saldo > 0,
        rx.cond(total > saldo, 100, total / saldo * 100),
        0,
    )
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.checkbox(
                    checked=State.off_selecionados.contains(cartao["chave"]),
                    on_change=lambda v: State.selecionar_off(cartao["chave"], v),
                    size="1",
                ),
                rx.text("#", size="1", color=tema.C["muted"]),
                rx.text(cartao["pedido"], size="2", weight="bold"),
                rx.spacer(),
                rx.badge(
                    cartao["dias"],
                    color_scheme=rx.match(
                        cartao["prioridade"],
                        ("Atrasado", "red"), ("Alta", "amber"), ("Média", "blue"),
                        ("Baixa", "gray"), "gray",
                    ),
                    variant="soft", size="1",
                ),
                spacing="1", width="100%", align_items="center",
            ),
            rx.text(cartao["item"], size="2", line_clamp="2", weight="medium"),
            rx.hstack(
                tema.chip(cartao["codigo"], tema.C["info"]),
                tema.chip(cartao["marca"], tema.C["muted"]),
                rx.spacer(),
                tema.prioridade_chip(cartao["prioridade"]),
                spacing="1", width="100%", wrap="wrap",
            ),
            rx.hstack(
                rx.text("Saldo ", size="1", color=tema.C["muted"]),
                rx.text(cartao["saldo"], size="2", weight="bold"),
                rx.text(" un.", size="1", color=tema.C["muted"]),
                rx.spacer(),
                rx.cond(
                    cartao["qe"].to(float) > 0,
                    tema.chip(f"Q.E {cartao['qe']}", tema.C["danger"]),
                    rx.fragment(),
                ),
                spacing="1", width="100%",
            ),
            rx.cond(
                cartao["entrega"] != "—",
                rx.hstack(
                    rx.icon("calendar-days", size=12, color=tema.C["muted"]),
                    rx.text("Entrega ", size="1", color=tema.C["muted"]),
                    rx.text(cartao["entrega"], size="1"),
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                total > 0,
                rx.vstack(
                    tema.barra(progresso, 100, tema.CORES_STATUS["Pronto"]),
                    rx.text(
                        f"Prontas {cartao['qtd_pronta']} · Quebra {cartao['qtd_quebra']}",
                        size="1", color=tema.C["muted"],
                    ),
                    spacing="1", width="100%",
                ),
                rx.fragment(),
            ),
            rx.hstack(
                movimentos_off(cartao),
                rx.button(
                    rx.icon("circle-dot-dashed", size=14),
                    size="1", variant="soft", color_scheme="violet",
                    on_click=State.abrir_parcial(cartao["chave"]),
                    title="Registrar produção parcial",
                ),
                spacing="1", width="100%",
            ),
            rx.cond(
                cartao["status_em"],
                rx.text(
                    f"{cartao['status_por']} · {cartao['status_em']}",
                    size="1", color=tema.C["muted"],
                ),
                rx.fragment(),
            ),
            spacing="2", width="100%",
        ),
        background=tema.C["surface"],
        border=f"1px solid {tema.C['border']}",
        border_left=f"4px solid {cor_status_var(cartao['status'])}",
        border_radius="12px",
        padding="0.85rem",
        class_name="vf-card",
        width="100%",
    )


def coluna_off(titulo: str, status: str, itens: rx.Component) -> rx.Component:
    cor = tema.CORES_STATUS[status]
    return rx.vstack(
        rx.hstack(
            rx.box(width="10px", height="10px", border_radius="50%", background=cor),
            rx.text(titulo, size="2", weight="bold"),
            rx.badge(itens.length(), variant="soft", color_scheme=tema._scheme(cor)),
            rx.spacer(),
            rx.text("pedidos", size="1", color=tema.C["muted"]),
            spacing="2", width="100%",
        ),
        rx.vstack(
            rx.foreach(itens, cartao_off),
            spacing="2", width="100%", min_height="90px",
        ),
        rx.box(
            rx.vstack(
                spacing="2", width="100%", min_height="90px",
            ),
            width="100%",
        ),
        spacing="2",
        background="#f8fafc",
        border=f"1px solid {tema.C['border']}",
        border_top=f"3px solid {cor}",
        border_radius="14px",
        padding="0.75rem",
        class_name="vf-scroll",
        max_height="620px", overflow_y="auto",
        flex="1", min_width="270px",
    )


def upload_off() -> rx.Component:
    return tema.superficie(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon("file-spreadsheet", size=22, color=tema.C["primary"]),
                    background=tema.C["primary_soft"], border_radius="12px", padding="0.6rem",
                ),
                rx.vstack(
                    rx.text("Carregamento local dos XLSX", size="4", weight="bold"),
                    rx.text(
                        "Pedidos.xlsx e Estoque.xlsx — os arquivos não saem do seu navegador.",
                        size="2", color=tema.C["muted"],
                    ),
                    spacing="0",
                ),
                spacing="3", align_items="center", width="100%",
            ),
            rx.upload(
                rx.vstack(
                    rx.icon("cloud-upload", size=30, color=tema.C["primary"]),
                    rx.text("Arraste os dois arquivos ou clique para selecionar", size="2", weight="medium"),
                    rx.text("Pedidos.xlsx + Estoque.xlsx", size="1", color=tema.C["muted"]),
                    spacing="1", align_items="center", padding="1.2rem",
                ),
                id="upload_off", multiple=True, accept=".xlsx,.xls",
                on_drop=State.carregar_offline,
                border=f"2px dashed {tema.C['border']}",
                border_radius="12px", background="#fbfcff", width="100%",
            ),
            rx.hstack(
                rx.cond(
                    State.off_ped_nome,
                    tema.chip("Pedidos: " + State.off_ped_nome, tema.C["success"]),
                    tema.chip("Pedidos: aguardando", tema.C["muted"]),
                ),
                rx.cond(
                    State.off_est_nome,
                    tema.chip("Estoque: " + State.off_est_nome, tema.C["success"]),
                    tema.chip("Estoque: aguardando", tema.C["muted"]),
                ),
                rx.spacer(),
                rx.cond(State.off_processando, rx.spinner(size="2")),
                botao("Limpar dados", "trash-2", State.limpar_offline, "soft", "1", "red"),
                spacing="2", width="100%", wrap="wrap",
            ),
            spacing="3", width="100%",
        ),
    )


def filtros_off() -> rx.Component:
    return tema.superficie(
        rx.vstack(
            rx.hstack(
                campo("Busca", rx.input(
                    placeholder="Pedido, código, item, confecção ou marca",
                    value=State.off_termo, on_change=State.set_off_termo, width="280px",
                )),
                campo("Visão", rx.select(
                    ["Todos", "Futuros", "Abertos", "Concluídos"],
                    value=State.off_segmento, on_change=State.set_off_segmento, width="150px",
                )),
                campo("Prioridade", rx.select(
                    State.off_opcoes_prioridade, value=State.off_prioridade,
                    on_change=State.set_off_prioridade, width="150px",
                )),
                campo("Confecção", rx.select(
                    State.off_opcoes_confeccao, value=State.off_confeccao,
                    on_change=State.set_off_confeccao, width="220px",
                )),
                campo("Ordem", rx.select(
                    ["Entrega", "Prioridade", "Quantidade", "Pedido"],
                    value=State.off_ordem, on_change=State.set_off_ordem, width="150px",
                )),
                campo("Fator Q.E", rx.input(
                    type="number", step="0.05", min="1", max="3",
                    value=State.off_fator, on_change=State.set_off_fator, width="100px",
                )),
                spacing="3", align_items="end", width="100%", wrap="wrap",
            ),
            rx.hstack(
                rx.checkbox(
                    "Desconsiderar saldo ≤ 4%",
                    checked=State.off_desconsiderar_baixo,
                    on_change=State.set_off_baixo, size="2",
                ),
                rx.checkbox(
                    "Ocultar entregues",
                    checked=State.off_ocultar_entregues,
                    on_change=State.set_off_ocultar, size="2",
                ),
                rx.spacer(),
                rx.text("Exibindo ", size="1", color=tema.C["muted"]),
                rx.text(State.off_qtd_filtrada, size="2", weight="bold"),
                rx.text(" pedidos", size="1", color=tema.C["muted"]),
                spacing="4", align_items="center", width="100%", wrap="wrap",
            ),
            spacing="3", width="100%",
        ),
        padding="1rem",
    )


def barra_lote_off() -> rx.Component:
    return tema.superficie(
        rx.hstack(
            rx.checkbox(
                "Selecionar visíveis", on_change=State.selecionar_todos_off, size="2",
            ),
            rx.text(State.off_selecionados.length(), size="2", weight="bold"),
            rx.text("selecionado(s)", size="1", color=tema.C["muted"]),
            rx.spacer(),
            rx.cond(State.off_limite > 60,
                    botao("Mostrar menos", "chevron-up", State.mostrar_menos, "soft", "1")),
            rx.cond(State.off_pode_mostrar_mais,
                    botao("Mostrar mais", "chevron-down", State.mostrar_mais, "soft", "1")),
            campo("Destino", rx.select(
                ["Pendente", "Em andamento", "Pronto", "Entregue"],
                value=State.off_destino_lote, on_change=State.set_off_destino_lote, width="170px",
            )),
            botao("Mover selecionados", "move-right", State.mover_lote_off, "soft", "2"),
            spacing="3", align_items="end", width="100%", wrap="wrap",
        ),
        padding="0.8rem",
        background="#eef2ff",
        border_color="#c7d2fe",
    )


def kpis_off() -> rx.Component:
    return rx.grid(
        tema.kpi("Pedidos", State.off_kpis.get("pedidos", 0), "no quadro", "package", tema.C["primary"]),
        tema.kpi("Peças em aberto", State.off_kpis.get("unidades", 0), "saldo total", "layers", tema.C["info"]),
        tema.kpi("Atrasados", State.off_kpis.get("atrasado", 0), "prioridade máxima", "triangle-alert", tema.C["danger"]),
        tema.kpi("Q.E. total", State.off_total_qe, "quantidade emergencial", "zap", tema.C["warning"]),
        tema.kpi("Confecções", State.off_kpis.get("confeccoes", 0), "no quadro", "users", tema.C["violet"]),
        columns=rx.breakpoints(initial="2", sm="3", lg="5"),
        spacing="3", width="100%",
    )


def painel_parcial_off() -> rx.Component:
    return rx.cond(
        State.off_mostrar_parcial,
        tema.superficie(
            rx.vstack(
                rx.hstack(
                    rx.icon("circle-dot-dashed", size=20, color=tema.C["violet"]),
                    rx.heading("Produção parcial", size="5"),
                    rx.spacer(),
                    rx.badge(State.off_parcial_chave, variant="soft", color_scheme="violet"),
                    rx.button(rx.icon("x", size=16), on_click=State.fechar_parcial,
                              variant="ghost", size="1"),
                    spacing="2", width="100%", align_items="center",
                ),
                rx.text(
                    "Informe os totais acumulados de peças prontas e quebra. "
                    "A soma não pode ultrapassar o saldo do pedido.",
                    size="2", color=tema.C["muted"],
                ),
                rx.hstack(
                    campo("Prontas", rx.input(
                        type="number", min="0", value=State.off_parcial_pronta,
                        on_change=State.set_parcial_pronta, width="140px",
                    )),
                    campo("Quebra", rx.input(
                        type="number", min="0", value=State.off_parcial_quebra,
                        on_change=State.set_parcial_quebra, width="140px",
                    )),
                    botao("Registrar", "check", State.registrar_parcial),
                    spacing="3", align_items="end", width="100%", wrap="wrap",
                ),
                spacing="3", width="100%",
            ),
            border_color="#c4b5fd", background="#faf5ff",
        ),
        rx.fragment(),
    )


def quadro_off() -> rx.Component:
    return rx.hstack(
        coluna_off("A produzir", "Pendente", State.off_col_pendente),
        coluna_off("Em produção", "Em andamento", State.off_col_andamento),
        coluna_off("Pronto", "Pronto", State.off_col_pronto),
        coluna_off("Entregue", "Entregue", State.off_col_entregue),
        spacing="3", width="100%", align_items="start", wrap="wrap",
    )


def resumos_off() -> rx.Component:
    return rx.grid(
        painel(
            "Rastreabilidade",
            rx.vstack(
                rx.foreach(
                    State.off_classificacao,
                    lambda item: rx.hstack(
                        rx.box(width="10px", height="10px", border_radius="50%",
                               background=item["Cor"]),
                        rx.text(item["Etapa"], size="2", width="160px"),
                        tema.barra(item["Pedidos"], State.off_kpis.get("pedidos", 1), item["Cor"]),
                        rx.text(item["Pedidos"], size="2", weight="bold"),
                        spacing="2", width="100%", align_items="center",
                    ),
                ),
                rx.hstack(
                    rx.text("Retorno de produção: ", size="2", color=tema.C["muted"]),
                    rx.text(State.off_retornos, size="2", weight="bold"),
                    spacing="1",
                ),
                spacing="3", width="100%",
            ),
        ),
        painel(
            "Por confecção",
            rx.box(
                rx.data_table(
                    data=State.off_confeccoes,
                    columns=["Confecção", "Pedidos", "Quantidade", "Saldo", "Q.E", "Retornado"],
                    pagination=True, search=True, sort=True, height="260px", width="100%",
                ),
                width="100%",
            ),
        ),
        columns=rx.breakpoints(initial="1", lg="2"),
        spacing="3", width="100%",
    )


# ============================ PÁGINAS ============================


@rx.page(route="/", title="Entrar — Visualfil")
def login_page() -> rx.Component:
    formulario = rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Acesso à plataforma", size="6", color=tema.C["text"]),
                rx.text("Use seu usuário e senha corporativos.", size="2", color=tema.C["muted"]),
                rx.form(
                    rx.vstack(
                        rx.input(name="usuario", placeholder="Usuário", icon="user-round", width="100%"),
                        rx.input(name="senha", placeholder="Senha", type="password",
                                 icon="lock-keyhole", width="100%"),
                        rx.button("Entrar", type="submit", width="100%", size="3"),
                        spacing="3", width="100%",
                    ),
                    on_submit=State.entrar, width="100%",
                ),
                tema.aviso_ui(State),
                spacing="4", width="100%",
            ),
            width="100%", max_width="380px", padding="1.8rem",
            background=tema.C["surface"], border_radius="16px",
            box_shadow="0 20px 50px rgba(15,23,42,.18)",
        ),
        spacing="3", width="100%", max_width="380px",
    )
    return rx.box(
        rx.el.style("body { background: #ffffff; }"),
        rx.hstack(
            rx.box(tema.painel_login(rx.fragment()),
                   display=["none", "none", "flex"], width="48%", min_height="100vh"),
            rx.center(formulario, width=["100%", "100%", "52%"], background=tema.C["bg"],
                      min_height="100vh", padding="2rem"),
            width="100%", min_height="100vh",
        ),
    )


@rx.page(route="/sem-acesso", title="Sem acesso — Visualfil", on_load=State.verificar_login)
def sem_acesso_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.icon("shield-alert", size=42, color=tema.C["warning"]),
                rx.heading("Sem acesso a esta área", size="6"),
                rx.text("Sua permissão não habilita esta página. Solicite ao administrador.",
                        color=tema.C["muted"], text_align="center"),
                rx.link(rx.button("Voltar ao Kanban", size="3"), href="/kanban-offline"),
                spacing="4", align_items="center", padding="2rem",
            ),
            width="420px",
        ),
        min_height="100vh", background=tema.C["bg"],
    )


@rx.page(route="/kanban-offline", title="Kanban de Confecção (offline) — Visualfil",
         on_load=State.iniciar_offline)
def kanban_offline_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            rx.cond(
                State.off_pronto,
                rx.vstack(
                    tema.superficie(
                        rx.hstack(
                            rx.icon("hard-drive-download", size=18, color=tema.C["success"]),
                            rx.text("Dados locais carregados", size="2", weight="bold"),
                            rx.text(State.off_ped_nome + " · " + State.off_est_nome,
                                    size="1", color=tema.C["muted"]),
                            rx.spacer(),
                            rx.button("Trocar arquivos", size="1", variant="soft",
                                      on_click=State.limpar_offline),
                            spacing="2", width="100%", align_items="center",
                        ),
                        padding="0.7rem", background=tema.C["success_soft"],
                        border_color="#bbf7d0",
                    ),
                    kpis_off(),
                    filtros_off(),
                    barra_lote_off(),
                    painel_parcial_off(),
                    quadro_off(),
                    resumos_off(),
                    rx.hstack(
                        botao("Exportar CSV", "file-down", State.exportar_csv_off, "soft"),
                        rx.button("Imprimir / PDF", on_click=rx.call_script("window.print()"),
                                  variant="soft", color_scheme="gray", icon="printer"),
                        rx.spacer(),
                        rx.foreach(
                            State.off_avisos,
                            lambda aviso: tema.chip(aviso, tema.C["warning"]),
                        ),
                        spacing="2", width="100%", wrap="wrap",
                    ),
                    spacing="3", width="100%",
                ),
                upload_off(),
            ),
            width="100%", spacing="0",
        ),
        ativa="kanban-offline",
        titulo_pagina="Kanban de Confecção",
        subtitulo="Quadro operacional offline — upload local, sem envio de dados",
        state=State,
        acoes=tema.chip("Offline", tema.C["success"]),
    )


@rx.page(route="/kanban", title="Kanban online — Visualfil", on_load=State.iniciar_online)
def kanban_online_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            seletor_demanda(),
            kpis_online(),
            rx.tabs(
                rx.tabs.list(
                    rx.tabs.trigger("Quadro", value="quadro"),
                    rx.tabs.trigger("Tabela", value="tabela"),
                ),
                rx.tabs.content(
                    rx.hstack(
                        coluna_online("Críticos (Saldo 2 negativo)", tema.C["danger"], State.pedidos),
                        spacing="3", width="100%",
                    ),
                    value="quadro", width="100%", padding_top="1rem",
                ),
                rx.tabs.content(
                    tema.tabela(
                        State.pedidos,
                        ["Pedido", "Código", "Item", "Confecção", "Marca", "Qtd", "Saldo", "Prioridade"],
                        "540px",
                    ),
                    value="tabela", width="100%", padding_top="1rem",
                ),
                default_value="quadro", width="100%",
            ),
            spacing="3", width="100%",
        ),
        ativa="kanban-online",
        titulo_pagina="Kanban online",
        subtitulo="Pedidos críticos da demanda carregada diretamente do Drive",
        state=State,
    )


@rx.page(route="/compra", title="Compra sugerida — Visualfil", on_load=State.iniciar_online)
def compra_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            seletor_demanda(),
            rx.grid(
                tema.kpi("Total compra sugerida", State.total_compra, "unidades", "shopping-cart", tema.C["danger"]),
                tema.kpi("Itens discriminados", State.compra_itens.length(), "códigos", "package", tema.C["warning"]),
                tema.kpi("Confecções", State.compra_resumo.length(), "com sugestão", "users", tema.C["violet"]),
                columns=rx.breakpoints(initial="1", sm="3"),
                spacing="3", width="100%",
            ),
            painel("Resumo por confecção", tema.tabela(
                State.compra_resumo, ["Confecção", "Itens", "Compra"], "260px")),
            painel(
                "Compra discriminada por item",
                tema.tabela(
                    State.compra_itens,
                    ["Código", "Item", "Saldo 5", "Tec Faz", "Confecção", "Compra"],
                    "440px",
                ),
                botao("Salvar análise", "save", State.salvar_analise, "soft", "2"),
            ),
            spacing="3", width="100%",
        ),
        ativa="compra",
        titulo_pagina="Compra sugerida",
        subtitulo="Saldo 5 negativo × 1,1 − tecido em estoque (Faz x Confec)",
        state=State,
    )


@rx.page(route="/dashboards", title="Dashboards — Visualfil", on_load=State.iniciar_dashboards)
def dashboards_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            seletor_demanda(),
            rx.grid(
                tema.kpi("Pedidos no quadro", State.pedidos.length(), "na demanda", "package"),
                tema.kpi("Confecções", State.por_confeccao.length(), "com pedidos", "users", tema.C["info"]),
                tema.kpi("Faixas de prioridade", State.por_prioridade.length(), "Atrasado a Baixa", "gauge", tema.C["warning"]),
                columns=rx.breakpoints(initial="1", sm="3"),
                spacing="3", width="100%",
            ),
            painel("Por confecção", tema.tabela(
                State.por_confeccao, ["Grupo", "Pedidos", "Unidades"], "300px")),
            rx.grid(
                painel("Por prioridade", tema.tabela(
                    State.por_prioridade, ["Grupo", "Pedidos", "Unidades"], "240px")),
                painel("Por status", tema.tabela(
                    State.por_status, ["Grupo", "Pedidos", "Unidades"], "240px")),
                columns=rx.breakpoints(initial="1", lg="2"),
                spacing="3", width="100%",
            ),
            spacing="3", width="100%",
        ),
        ativa="dashboards",
        titulo_pagina="Dashboards de pedidos",
        subtitulo="Volume e urgência por confecção, status e prioridade",
        state=State,
    )


@rx.page(route="/projecao", title="Projeção — Visualfil", on_load=State.iniciar_projecao)
def projecao_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            seletor_demanda(),
            rx.grid(
                tema.kpi("Confecções com histórico", State.capacidade.length(),
                         "na produção", "factory", tema.C["violet"]),
                tema.kpi("Itens com sugestão", State.compra_itens.length(),
                         "para compra", "shopping-cart", tema.C["danger"]),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="3", width="100%",
            ),
            rx.callout(
                "Capacidade semanal estimada = volume devolvido por confecção no histórico de produção.",
                color_scheme="blue", width="100%",
            ),
            painel("Capacidade por confecção", tema.tabela(
                State.capacidade, ["Confecção", "Retornos", "Itens"], "340px")),
            painel("Compra sugerida × capacidade", tema.tabela(
                State.compra_resumo, ["Confecção", "Itens", "Compra"], "260px")),
            spacing="3", width="100%",
        ),
        ativa="projecao",
        titulo_pagina="Projeção por confecção",
        subtitulo="Histórico de produção cruzado com a necessidade de compra",
        state=State,
    )


@rx.page(route="/admin", title="Administração — Visualfil", on_load=State.iniciar_admin)
def admin_page() -> rx.Component:
    return tema.shell(
        rx.vstack(
            rx.tabs(
                rx.tabs.list(
                    rx.tabs.trigger("Demandas", value="demandas"),
                    rx.tabs.trigger("Usuários", value="usuarios"),
                    rx.tabs.trigger("Permissões", value="permissoes"),
                ),
                rx.tabs.content(
                    rx.vstack(
                        tema.superficie(
                            rx.hstack(
                                campo("Nome da demanda", rx.input(
                                    placeholder="Ex.: Remessa 05/2026", value=State.nova_demanda,
                                    on_change=State.set_nova_demanda, width="260px")),
                                campo("Fonte", rx.input(
                                    placeholder="Remessa", value=State.nova_fonte,
                                    on_change=State.set_nova_fonte, width="180px")),
                                botao("Criar demanda", "plus", State.criar_demanda),
                                spacing="3", align_items="end", wrap="wrap", width="100%",
                            ),
                        ),
                        seletor_demanda(),
                        rx.upload(
                            rx.vstack(
                                rx.icon("file-up", size=26, color=tema.C["primary"]),
                                rx.text("Enviar XLSX da demanda selecionada", size="2"),
                                rx.text("pedidos / estoque / producao / projecao",
                                        size="1", color=tema.C["muted"]),
                                spacing="1", align_items="center", padding="1.2rem",
                            ),
                            id="upload_admin", multiple=False, accept=".xlsx,.xls",
                            on_drop=State.enviar_arquivo, width="100%",
                            border=f"2px dashed {tema.C['border']}",
                            border_radius="12px", background="#fbfcff",
                        ),
                        tema.tabela(
                            State.demandas,
                            ["id", "nome", "fonte", "criado_em", "atualizado_em"], "280px",
                        ),
                        spacing="3", width="100%",
                    ),
                    value="demandas", width="100%", padding_top="1rem",
                ),
                rx.tabs.content(
                    rx.vstack(
                        tema.superficie(
                            rx.hstack(
                                campo("Usuário", rx.input(
                                    placeholder="login", value=State.novo_usuario,
                                    on_change=State.set_novo_usuario, width="160px")),
                                campo("Nome", rx.input(
                                    placeholder="Nome completo", value=State.novo_nome,
                                    on_change=State.set_novo_nome, width="200px")),
                                campo("Senha", rx.input(
                                    type="password", value=State.nova_senha,
                                    on_change=State.set_nova_senha, width="160px")),
                                rx.checkbox("Admin", checked=State.novo_admin,
                                            on_change=State.set_novo_admin, size="2"),
                                botao("Salvar usuário", "user-plus", State.criar_usuario),
                                spacing="3", align_items="end", wrap="wrap", width="100%",
                            ),
                        ),
                        tema.tabela(State.usuarios, ["usuario", "nome", "admin", "ativo"], "400px"),
                        spacing="3", width="100%",
                    ),
                    value="usuarios", width="100%", padding_top="1rem",
                ),
                rx.tabs.content(
                    rx.vstack(
                        tema.superficie(
                            rx.hstack(
                                campo("Usuário", rx.select(
                                    State.usuario_opcoes, value=State.perm_usuario,
                                    on_change=State.set_perm_usuario, placeholder="Usuário", width="200px")),
                                campo("Página", rx.select(
                                    list(PAGINAS), value=State.perm_pagina,
                                    on_change=State.set_perm_pagina, width="240px")),
                                campo("Nível", rx.select(
                                    list(NIVEIS), value=State.perm_nivel,
                                    on_change=State.set_perm_nivel, width="160px")),
                                botao("Salvar permissão", "shield-check", State.salvar_permissao),
                                spacing="3", align_items="end", wrap="wrap", width="100%",
                            ),
                        ),
                        tema.tabela(State.permissoes, ["usuario", "pagina", "nivel"], "400px"),
                        spacing="3", width="100%",
                    ),
                    value="permissoes", width="100%", padding_top="1rem",
                ),
                default_value="demandas", width="100%",
            ),
            spacing="3", width="100%",
        ),
        ativa="admin",
        titulo_pagina="Administração",
        subtitulo="Demandas, usuários e permissões por página",
        state=State,
        acoes=tema.chip("Somente administradores", tema.C["warning"]),
    )


app = rx.App()
