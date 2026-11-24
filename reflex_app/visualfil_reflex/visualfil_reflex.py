"""
Visualfil Reflex — versão paralela, profissional e otimizada
============================================================
Mesma API do Visualfil Cloud (Google Sheets / Apps Script), com interface
React gerada pelo Reflex: navegação lateral, tema, proteção de rotas,
Kanban online, compra sugerida discriminada e painel administrativo.
"""
from __future__ import annotations

import base64
import io
import os
import re
import unicodedata
from typing import Any

import pandas as pd
import reflex as rx
import requests

# ============================ API ============================


def api(action: str, **dados: Any) -> dict:
    url = os.getenv("VFCLOUD_URL", "")
    if not url:
        return {"ok": False, "erro": "Configure VFCLOUD_URL no arquivo run.bat (URL do Web App)."}
    corpo = {
        "action": action,
        "usuario": os.getenv("VFCLOUD_USUARIO", ""),
        "senha": os.getenv("VFCLOUD_SENHA", ""),
        **dados,
    }
    resposta = requests.post(url, json=corpo, timeout=180)
    resposta.raise_for_status()
    return resposta.json()


def normalizar_cod(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\D", "", texto).lstrip("0")


def ler_xlsx(conteudo: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(conteudo))


def fmt(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


TIPOS = ("pedidos", "estoque", "producao", "projecao")
PAGINAS = (
    "Kanban de Confecção", "Dashboards de Pedidos", "Análise de Estoque",
    "Projeção Futuro", "Projeção por Confecção", "Painel Online", "Administração",
)
NIVEIS = ("visualizacao", "total", "restrito")

# ============================ ESTADO ============================


class State(rx.State):
    # sessão
    usuario: str = ""
    senha: str = ""
    logado: bool = False
    admin: bool = False
    nome: str = ""
    mensagem: str = ""
    tipo_mensagem: str = "info"

    # demandas
    demandas: list[dict] = []
    demanda_opcoes: list[str] = []
    demanda_id: str = ""
    demanda_nome: str = ""
    nova_demanda: str = ""
    nova_fonte: str = ""
    arquivos_info: list[dict] = []

    # dados
    pedidos: list[dict] = []
    compra_itens: list[dict] = []
    compra_resumo: list[dict] = []
    total_compra: str = "0"
    carregando: bool = False

    # dashboards / projeção
    capacidade: list[dict] = []
    por_confeccao: list[dict] = []
    por_status: list[dict] = []
    por_prioridade: list[dict] = []

    # admin
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

    # ---------- helpers ----------
    def aviso(self, texto: str, tipo: str = "info"):
        self.mensagem = texto
        self.tipo_mensagem = tipo

    def definir_usuario(self, valor: str): self.usuario = valor
    def definir_senha(self, valor: str): self.senha = valor
    def set_nova_demanda(self, valor: str): self.nova_demanda = valor
    def set_nova_fonte(self, valor: str): self.nova_fonte = valor
    def set_novo_usuario(self, valor: str): self.novo_usuario = valor
    def set_novo_nome(self, valor: str): self.novo_nome = valor
    def set_nova_senha(self, valor: str): self.nova_senha = valor
    def set_novo_admin(self, valor: bool): self.novo_admin = valor
    def set_perm_usuario(self, valor: str): self.perm_usuario = valor
    def set_perm_pagina(self, valor: str): self.perm_pagina = valor
    def set_perm_nivel(self, valor: str): self.perm_nivel = valor

    url_temp: str = ""

    # ---------- autenticação ----------
    def entrar(self):
        try:
            os.environ["VFCLOUD_USUARIO"] = self.usuario.strip()
            os.environ["VFCLOUD_SENHA"] = self.senha
            r = api("login")
            if r.get("ok"):
                self.logado = True
                self.admin = bool(r.get("admin"))
                self.nome = r.get("nome") or self.usuario
                self.aviso("", "info")
                return rx.redirect("/kanban")
            self.aviso(r.get("erro", "Falha no login."), "error")
        except Exception as e:
            self.aviso(str(e), "error")

    def sair(self):
        self.logado = False
        self.admin = False
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
            return rx.redirect("/kanban")

    # ---------- demandas ----------
    def carregar_demandas(self):
        verificacao = self.verificar_login()
        if verificacao:
            return verificacao
        try:
            r = api("demandas_listar")
            self.demandas = r.get("demandas", [])
            self.demanda_opcoes = [
                str(d.get("nome", "")) or str(d.get("id", "")) for d in self.demandas
            ]
        except Exception as e:
            self.aviso(str(e), "error")

    def selecionar_demanda(self, nome: str):
        self.demanda_nome = nome
        d = next((x for x in self.demandas if
                  (str(x.get("nome", "")) or str(x.get("id", ""))) == nome), {})
        self.demanda_id = str(d.get("id", ""))

    def criar_demanda(self):
        if not self.nova_demanda.strip():
            self.aviso("Informe o nome da demanda.", "error")
            return
        try:
            r = api("demanda_salvar", nome=self.nova_demanda.strip(),
                    fonte=self.nova_fonte.strip())
            if r.get("ok"):
                self.nova_demanda = ""
                self.nova_fonte = ""
                self.aviso("Demanda criada.", "success")
                self.carregar_demandas()
            else:
                self.aviso(r.get("erro", "Erro ao criar."), "error")
        except Exception as e:
            self.aviso(str(e), "error")

    async def enviar_arquivo(self, files: list[rx.UploadFile]):
        if not self.demanda_id:
            self.aviso("Selecione uma demanda.", "error")
            return
        if not files:
            self.aviso("Selecione um arquivo.", "error")
            return
        arquivo = files[0]
        dados = await arquivo.read()
        tipo = arquivo.filename.split(".")[0].lower().replace(" ", "")
        if tipo not in TIPOS:
            tipo = "pedidos"
        try:
            r = api("arquivo_salvar", demanda_id=self.demanda_id, tipo=tipo,
                    base64=base64.b64encode(dados).decode())
            self.aviso(f"{tipo}.xlsx enviado." if r.get("ok") else r.get("erro", "Erro"),
                       "success" if r.get("ok") else "error")
        except Exception as e:
            self.aviso(str(e), "error")

    # ---------- carregamento de dados ----------
    def carregar_dados(self):
        if not self.demanda_id:
            self.aviso("Selecione uma demanda.", "error")
            return
        self.carregando = True
        try:
            def ler(tipo):
                r = api("arquivo_ler", demanda_id=self.demanda_id, tipo=tipo)
                return ler_xlsx(base64.b64decode(r["base64"])) if r.get("ok") else pd.DataFrame()

            ped, est = ler("pedidos"), ler("estoque")
            prod = ler("producao")
            self.pedidos = self._montar_kanban(ped, est)
            self.compra_itens, self.compra_resumo, self.total_compra = self._montar_compra(est)
            self.capacidade = self._montar_capacidade(prod)
            self.por_confeccao = self._agrupar(self.pedidos, "Confecção")
            self.por_status = self._agrupar(self.pedidos, "Status")
            self.por_prioridade = self._agrupar(self.pedidos, "Prioridade") if self.pedidos and "Prioridade" in self.pedidos[0] else []
            self.aviso("", "info")
        except Exception as e:
            self.aviso(str(e), "error")
        finally:
            self.carregando = False

    def _agrupar(self, dados: list[dict], chave: str) -> list[dict]:
        if not dados:
            return []
        mapa: dict[str, dict] = {}
        for item in dados:
            k = str(item.get(chave, "")) or "—"
            if k not in mapa:
                mapa[k] = {"Grupo": k, "Pedidos": 0, "Unidades": 0.0}
            mapa[k]["Pedidos"] += 1
            mapa[k]["Unidades"] += float(item.get("Saldo", 0) or 0)
        out = list(mapa.values())
        out.sort(key=lambda x: x["Unidades"], reverse=True)
        return out

    def _montar_capacidade(self, prod: pd.DataFrame) -> list[dict]:
        if prod.empty:
            return []
        col_conf = next((c for c in prod.columns if "fornecedor" in str(c).lower()), None)
        col_qtd = next((c for c in prod.columns
                        if "qtd" in str(c).lower() and "retorn" in str(c).lower()), None)
        col_cod = next((c for c in prod.columns if "cód" in str(c).lower() and "confec" in str(c).lower()), None)
        if not col_conf or not col_qtd:
            return []
        p = prod.copy()
        p["_qtd"] = pd.to_numeric(p[col_qtd], errors="coerce").fillna(0)
        g = p.groupby(col_conf).agg(
            Retornos=("_qtd", "sum"),
            Itens=(col_cod, "nunique") if col_cod else ("_qtd", "count"),
        ).reset_index().sort_values("Retornos", ascending=False)
        return [{"Confecção": str(r[col_conf]), "Retornos": float(r["Retornos"]),
                 "Itens": int(r["Itens"])} for _, r in g.iterrows()][:100]

    def _montar_kanban(self, ped: pd.DataFrame, est: pd.DataFrame) -> list[dict]:
        if ped.empty or est.empty:
            return []
        ped, est = ped.copy(), est.copy()
        cod_est = (est["Cód Confec"].map(normalizar_cod) if "Cód Confec" in est.columns
                   else pd.Series(dtype=str))
        saldo2 = (pd.to_numeric(est.get("Saldo 2"), errors="coerce").fillna(0)
                  if "Saldo 2" in est.columns else pd.Series(0, index=est.index))
        codigos = set(cod_est[saldo2 < 0]) - {""}
        marcas = {}
        if "Marca" in est.columns:
            for c, m in zip(cod_est, est["Marca"]):
                if c and pd.notna(m):
                    marcas[c] = str(m).strip()
        ped["_cod"] = ped["Cód Confec"].map(normalizar_cod) if "Cód Confec" in ped.columns else ""
        kb = ped[ped["_cod"].isin(codigos)].copy()
        out = []
        for _, r in kb.iterrows():
            out.append({
                "Pedido": str(r.get("Compra", "")),
                "Código": str(r.get("_cod", "")),
                "Item": str(r.get("Confeccionado", ""))[:55],
                "Confecção": str(r.get("Confecção", "")),
                "Marca": marcas.get(str(r.get("_cod", "")), "—"),
                "Qtd": float(pd.to_numeric(r.get("Qtd"), errors="coerce") or 0),
                "Saldo": float(pd.to_numeric(r.get("Saldo"), errors="coerce") or 0),
                "Status": str(r.get("Status", "")),
                "Prioridade": str(r.get("Prioridade", "") or "Baixa"),
            })
        return out[:500]

    def _montar_compra(self, est: pd.DataFrame):
        if est.empty or "Saldo 5" not in est.columns:
            return [], [], "0"
        est = est.copy()
        saldo5 = pd.to_numeric(est["Saldo 5"], errors="coerce").fillna(0)
        neg = est[saldo5 < 0].copy()
        tec = (pd.to_numeric(neg.get('Tec Faz "x" Confec'), errors="coerce").fillna(0)
               if 'Tec Faz "x" Confec' in neg.columns else 0)
        neg["Compra"] = ((saldo5[neg.index].abs() * 1.10) - tec).clip(lower=0).round()
        neg["_cod"] = neg["Cód Confec"].map(normalizar_cod) if "Cód Confec" in neg.columns else ""
        itens = [{
            "Código": str(r.get("_cod", "")),
            "Item": str(r.get("Descrição", ""))[:55],
            "Saldo 5": float(r.get("Saldo 5", 0)),
            "Tec Faz": float(tec.get(r.name, 0)) if hasattr(tec, "get") else 0.0,
            "Compra": float(r.get("Compra", 0)),
        } for _, r in neg.iterrows()]
        itens.sort(key=lambda x: x["Compra"], reverse=True)
        resumo_df = (neg.assign(_conf="Sem confecção cadastrada")
                     .groupby("_conf").agg(Itens=("_cod", "count"), Compra=("Compra", "sum"))
                     .reset_index())
        resumo = [{"Confecção": str(r["_conf"]), "Itens": int(r["Itens"]),
                   "Compra": float(r["Compra"])} for _, r in resumo_df.iterrows()]
        resumo.sort(key=lambda x: x["Compra"], reverse=True)
        return itens[:500], resumo, fmt(sum(x["Compra"] for x in itens))

    def salvar_analise(self):
        try:
            r = api("analise_salvar", demanda_id=self.demanda_id,
                    nome="Análise Reflex", dados_json=__import__("json").dumps(
                        {"resumo": self.compra_resumo, "pedidos": len(self.pedidos)}))
            self.aviso("Análise salva." if r.get("ok") else r.get("erro", "Erro"),
                       "success" if r.get("ok") else "error")
        except Exception as e:
            self.aviso(str(e), "error")

    # ---------- admin ----------
    def carregar_admin(self):
        verificacao = self.verificar_admin()
        if verificacao:
            return verificacao
        try:
            self.usuarios = api("usuarios_listar").get("usuarios", [])
            self.usuario_opcoes = [str(u.get("usuario", "")) for u in self.usuarios if u.get("usuario")]
            self.permissoes = api("permissoes_listar").get("permissoes", [])
            self.carregar_demandas()
        except Exception as e:
            self.aviso(str(e), "error")

    def criar_usuario(self):
        try:
            r = api("usuario_salvar", usuario=self.novo_usuario.strip(),
                    nome=self.novo_nome.strip(), senha=self.nova_senha,
                    admin=self.novo_admin, ativo=True)
            if r.get("ok"):
                self.aviso("Usuário salvo.", "success")
                self.novo_usuario = self.novo_nome = self.nova_senha = ""
                self.carregar_admin()
            else:
                self.aviso(r.get("erro", "Erro"), "error")
        except Exception as e:
            self.aviso(str(e), "error")

    def salvar_permissao(self):
        try:
            r = api("permissao_salvar", usuario=self.perm_usuario,
                    pagina=self.perm_pagina, nivel=self.perm_nivel)
            self.aviso("Permissão salva." if r.get("ok") else r.get("erro", "Erro"),
                       "success" if r.get("ok") else "error")
            self.carregar_admin()
        except Exception as e:
            self.aviso(str(e), "error")


# ============================ UI ============================

TEMA = {
    "font_family": "Inter, system-ui, sans-serif",
    "primary": "#4f46e5",
    "surface": "#ffffff",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "muted": "#64748b",
}


def aviso_ui() -> rx.Component:
    return rx.cond(
        State.mensagem,
        rx.callout(State.mensagem,
                   color_scheme=rx.cond(State.tipo_mensagem == "error", "red",
                                        rx.cond(State.tipo_mensagem == "success", "green", "blue")),
                   width="100%"),
    )


def shell(conteudo: rx.Component) -> rx.Component:
    return rx.box(
        rx.theme(accent_color="indigo", radius="medium"),
        rx.hstack(
            # sidebar
            rx.vstack(
                rx.heading("⚡ Visualfil", size="6", color="white"),
                rx.text("Plataforma de produção", size="2", color="#c7d2fe"),
                rx.divider(color="#312e81"),
                rx.link(rx.hstack(rx.text("📋"), rx.text("Kanban")), href="/kanban",
                        color="white", width="100%"),
                rx.link(rx.hstack(rx.text("🛒"), rx.text("Compra sugerida")), href="/compra",
                        color="white", width="100%"),
                rx.link(rx.hstack(rx.text("📊"), rx.text("Dashboards")), href="/dashboards",
                        color="white", width="100%"),
                rx.link(rx.hstack(rx.text("📅"), rx.text("Projeção")), href="/projecao",
                        color="white", width="100%"),
                rx.cond(State.admin,
                        rx.link(rx.hstack(rx.text("⚙️"), rx.text("Administração")),
                                href="/admin", color="white", width="100%")),
                rx.spacer(),
                rx.text(State.nome, size="2", color="#c7d2fe"),
                rx.button("Sair", on_click=State.sair, variant="soft", color_scheme="indigo",
                          width="100%"),
                bg="#312e81", padding="1.25rem", min_height="100vh", width="250px",
                spacing="3",
            ),
            # conteúdo
            rx.vstack(conteudo, aviso_ui(), padding="1.5rem", width="100%", spacing="4"),
            width="100%", min_height="100vh", bg="#f8fafc",
        ),
    )


def metrica(titulo: str, valor: rx.Component, subtitulo: str = "", cor: str = "#4f46e5"):
    return rx.card(
        rx.vstack(
            rx.text(titulo, size="2", color=TEMA["muted"]),
            rx.heading(valor, size="7", color=cor),
            rx.cond(subtitulo, rx.text(subtitulo, size="1", color=TEMA["muted"])),
            spacing="1", align_items="start",
        ), width="100%",
    )


def tabela(dados: list[dict], colunas: list[str], altura: str = "380px"):
    return rx.card(
        rx.data_table(data=dados, columns=colunas, pagination=True, search=True,
                      sort=True, width="100%", height=altura),
        width="100%",
    )


def seletor_demanda() -> rx.Component:
    return rx.hstack(
        rx.select(State.demanda_opcoes, value=State.demanda_nome,
                  on_change=State.selecionar_demanda,
                  placeholder="Selecione a demanda", width="320px"),
        rx.button("Carregar dados", on_click=State.carregar_dados),
        rx.cond(State.carregando, rx.spinner()),
        spacing="3", width="100%",
    )


# ============================ PÁGINAS ============================


@rx.page(route="/", title="Entrar — Visualfil")
def login_page():
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("⚡ Visualfil", size="8"),
                rx.text("Acesso à plataforma de produção", color=TEMA["muted"]),
                rx.input(placeholder="Usuário", value=State.usuario,
                         on_change=State.definir_usuario, width="100%"),
                rx.input(placeholder="Senha", type="password", value=State.senha,
                         on_change=State.definir_senha, width="100%"),
                rx.button("Entrar", on_click=State.entrar, width="100%", size="3"),
                aviso_ui(),
                spacing="4", width="420px", padding="2rem",
            ),
        ), min_height="100vh", bg="#eef2ff",
    )


@rx.page(route="/kanban", title="Kanban — Visualfil", on_load=State.carregar_demandas)
def kanban_page():
    return shell(
        rx.vstack(
            rx.heading("📋 Kanban online", size="7"),
            seletor_demanda(),
            rx.hstack(
                metrica("Pedidos", rx.text(State.pedidos.length()), "na demanda"),
                metrica("Pedidos carregados", rx.text(State.pedidos.length()), "visão salva", "#0891b2"),
                metrica("Registros", rx.text(State.pedidos.length()), "na demanda", "#7c3aed"),
                width="100%", spacing="3",
            ),
            tabela(State.pedidos,
                   ["Pedido", "Código", "Item", "Confecção", "Marca", "Qtd", "Saldo", "Status"]),
            width="100%", spacing="4",
        )
    )


@rx.page(route="/compra", title="Compra sugerida — Visualfil", on_load=State.carregar_demandas)
def compra_page():
    return shell(
        rx.vstack(
            rx.heading("🛒 Compra sugerida", size="7"),
            seletor_demanda(),
            rx.hstack(
                metrica("Total compra sugerida", State.total_compra, "unidades", "#dc2626"),
                metrica("Itens discriminados", rx.text(State.compra_itens.length()), "códigos", "#ea580c"),
                metrica("Confecções", rx.text(State.compra_resumo.length()), "com sugestão", "#4338ca"),
                width="100%", spacing="3",
            ),
            rx.heading("Resumo por confecção", size="5"),
            tabela(State.compra_resumo, ["Confecção", "Itens", "Compra"], "260px"),
            rx.heading("Discriminado por item", size="5"),
            tabela(State.compra_itens, ["Código", "Item", "Saldo 5", "Tec Faz", "Compra"]),
            rx.button("💾 Salvar análise", on_click=State.salvar_analise),
            width="100%", spacing="4",
        )
    )


@rx.page(route="/admin", title="Admin — Visualfil", on_load=State.carregar_admin)
def admin_page():
    return shell(
        rx.vstack(
            rx.heading("⚙️ Administração", size="7"),
            rx.tabs(
                rx.tabs.list(
                    rx.tabs.trigger("Demandas", value="demandas"),
                    rx.tabs.trigger("Usuários", value="usuarios"),
                    rx.tabs.trigger("Permissões", value="permissoes"),
                ),
                rx.tabs.content(
                    rx.vstack(
                        rx.hstack(
                            rx.input(placeholder="Nome da demanda", value=State.nova_demanda,
                                     on_change=State.set_nova_demanda, width="250px"),
                            rx.input(placeholder="Fonte (Remessa)", value=State.nova_fonte,
                                     on_change=State.set_nova_fonte, width="250px"),
                            rx.button("Criar demanda", on_click=State.criar_demanda),
                            spacing="3",
                        ),
                        seletor_demanda(),
                        rx.upload(
                            rx.vstack(rx.text("📤 Arraste um XLSX ou clique"),
                                      rx.text("pedidos / estoque / producao / projecao",
                                              size="1", color=TEMA["muted"])),
                            id="upload_xlsx", multiple=False,
                            on_drop=State.enviar_arquivo, width="100%",
                        ),
                        tabela(State.demandas,
                               ["id", "nome", "fonte", "criado_em", "atualizado_em"], "260px"),
                        spacing="3", width="100%",
                    ), value="demandas",
                ),
                rx.tabs.content(
                    rx.vstack(
                        rx.hstack(
                            rx.input(placeholder="Usuário", value=State.novo_usuario,
                                     on_change=State.set_novo_usuario, width="180px"),
                            rx.input(placeholder="Nome", value=State.novo_nome,
                                     on_change=State.set_novo_nome, width="180px"),
                            rx.input(placeholder="Senha", type="password", value=State.nova_senha,
                                     on_change=State.set_nova_senha, width="180px"),
                            rx.checkbox("Admin", checked=State.novo_admin,
                                        on_change=State.set_novo_admin),
                            rx.button("Salvar usuário", on_click=State.criar_usuario),
                            spacing="3", wrap="wrap",
                        ),
                        tabela(State.usuarios, ["usuario", "nome", "admin", "ativo"]),
                        spacing="3", width="100%",
                    ), value="usuarios",
                ),
                rx.tabs.content(
                    rx.vstack(
                        rx.hstack(
                            rx.select(State.usuario_opcoes,
                                      value=State.perm_usuario,
                                      on_change=State.set_perm_usuario,
                                      placeholder="Usuário", width="200px"),
                            rx.select(list(PAGINAS), value=State.perm_pagina,
                                      on_change=State.set_perm_pagina, width="220px"),
                            rx.select(list(NIVEIS), value=State.perm_nivel,
                                      on_change=State.set_perm_nivel, width="160px"),
                            rx.button("Salvar permissão", on_click=State.salvar_permissao),
                            spacing="3", wrap="wrap",
                        ),
                        tabela(State.permissoes, ["usuario", "pagina", "nivel"]),
                        spacing="3", width="100%",
                    ), value="permissoes",
                ),
                width="100%",
            ),
            width="100%", spacing="4",
        )
    )


@rx.page(route="/dashboards", title="Dashboards — Visualfil", on_load=State.carregar_demandas)
def dashboards_page():
    return shell(
        rx.vstack(
            rx.heading("📊 Dashboards de pedidos", size="7"),
            seletor_demanda(),
            rx.hstack(
                metrica("Pedidos no quadro", rx.text(State.pedidos.length()), "na demanda"),
                metrica("Confecções", rx.text(State.por_confeccao.length()), "com pedidos", "#0891b2"),
                metrica("Status", rx.text(State.por_status.length()), "diferentes", "#7c3aed"),
                metrica("Prioridades", rx.text(State.por_prioridade.length()), "faixas", "#ea580c"),
                width="100%", spacing="3",
            ),
            rx.heading("Por confecção", size="5"),
            tabela(State.por_confeccao, ["Grupo", "Pedidos", "Unidades"], "240px"),
            rx.hstack(
                rx.vstack(rx.heading("Por status", size="5"),
                          tabela(State.por_status, ["Grupo", "Pedidos", "Unidades"], "220px"),
                          width="50%"),
                rx.vstack(rx.heading("Por prioridade", size="5"),
                          tabela(State.por_prioridade, ["Grupo", "Pedidos", "Unidades"], "220px"),
                          width="50%"),
                width="100%", spacing="4",
            ),
            width="100%", spacing="4",
        )
    )


@rx.page(route="/projecao", title="Projeção — Visualfil", on_load=State.carregar_demandas)
def projecao_page():
    return shell(
        rx.vstack(
            rx.heading("📅 Projeção por confecção", size="7"),
            seletor_demanda(),
            rx.hstack(
                metrica("Confecções com histórico", rx.text(State.capacidade.length()),
                        "no arquivo de produção", "#7c3aed"),
                rx.vstack(
                    rx.text("Capacidade semanal = volume retornado por confecção no histórico online.",
                            color=TEMA["muted"], size="2"),
                    width="100%",
                ),
                width="100%", spacing="4",
            ),
            rx.heading("Capacidade por confecção", size="5"),
            tabela(State.capacidade, ["Confecção", "Retornos", "Itens"]),
            rx.heading("Compra sugerida × capacidade", size="5"),
            tabela(State.compra_resumo, ["Confecção", "Itens", "Compra"], "260px"),
            width="100%", spacing="4",
        )
    )


app = rx.App()
