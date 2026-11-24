"""
Visualfil Reflex — versão paralela otimizada do Visualfil
=========================================================
Protótipo em Reflex (Python puro → React) com:
  · login contra o mesmo backend do Visualfil Cloud (Apps Script);
  · Kanban online lendo os XLSX salvos por demanda;
  · Compra sugerida por confecção, discriminada por item.

Roda em paralelo ao Streamlit, sem alterar o sistema atual.
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


def api(action: str, usuario: str = "", senha: str = "", **dados: Any) -> dict:
    url = os.getenv("VFCLOUD_URL", "")
    if not url:
        return {"ok": False, "erro": "Defina VFCLOUD_URL (URL do Web App do Visualfil Cloud)."}
    corpo = {"action": action, "usuario": usuario, "senha": senha, **dados}
    resposta = requests.post(url, json=corpo, timeout=180)
    resposta.raise_for_status()
    return resposta.json()


def normalizar_cod(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\D", "", texto).strip()
    return texto.lstrip("0")


def ler_xlsx(bytes_arquivo: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(bytes_arquivo))


# ============================ ESTADO ============================


class State(rx.State):
    url: str = os.getenv("VFCLOUD_URL", "")
    usuario: str = ""
    senha: str = ""
    logado: bool = False
    admin: bool = False
    nome: str = ""
    mensagem: str = ""

    demandas: list[dict] = []
    demanda_opcoes: list[str] = []
    demanda_id: str = ""
    demanda_nome: str = ""

    pedidos: list[dict] = []
    compra_itens: list[dict] = []
    compra_resumo: list[dict] = []
    total_compra: str = ""
    carregando: bool = False

    def definir_url(self, valor: str):
        self.url = valor

    def definir_usuario(self, valor: str):
        self.usuario = valor

    def definir_senha(self, valor: str):
        self.senha = valor

    def entrar(self):
        try:
            os.environ["VFCLOUD_URL"] = self.url.strip()
            r = api("login", usuario=self.usuario.strip(), senha=self.senha)
            if r.get("ok"):
                self.logado = True
                self.admin = bool(r.get("admin"))
                self.nome = r.get("nome") or self.usuario
                self.mensagem = ""
                return rx.redirect("/kanban")
            self.mensagem = r.get("erro", "Falha no login.")
        except Exception as e:
            self.mensagem = str(e)

    def sair(self):
        self.logado = False
        self.admin = False
        self.pedidos = []
        self.compra_itens = []
        return rx.redirect("/")

    def carregar_demandas(self):
        try:
            r = api("demandas_listar", usuario=self.usuario, senha=self.senha)
            self.demandas = r.get("demandas", [])
            self.demanda_opcoes = [
                str(d.get("nome", "")) or str(d.get("id", "")) for d in self.demandas
            ]
            self.mensagem = ""
        except Exception as e:
            self.mensagem = str(e)

    def selecionar_demanda(self, nome: str):
        self.demanda_nome = nome
        d = next((x for x in self.demandas if (str(x.get("nome", "")) or str(x.get("id", ""))) == nome), {})
        self.demanda_id = str(d.get("id", ""))

    def carregar_dados(self):
        if not self.demanda_id:
            self.mensagem = "Selecione uma demanda."
            return
        self.carregando = True
        try:
            r = api("arquivo_ler", usuario=self.usuario, senha=self.senha,
                    demanda_id=self.demanda_id, tipo="pedidos")
            ped = ler_xlsx(base64.b64decode(r["base64"])) if r.get("ok") else pd.DataFrame()
            r2 = api("arquivo_ler", usuario=self.usuario, senha=self.senha,
                     demanda_id=self.demanda_id, tipo="estoque")
            est = ler_xlsx(base64.b64decode(r2["base64"])) if r2.get("ok") else pd.DataFrame()

            pedidos = self._montar_kanban(ped, est)
            self.pedidos = pedidos
            self.compra_itens, self.compra_resumo, total = self._montar_compra(est, ped)
            self.total_compra = total
            self.mensagem = ""
        except Exception as e:
            self.mensagem = str(e)
        finally:
            self.carregando = False

    def _montar_kanban(self, ped: pd.DataFrame, est: pd.DataFrame) -> list[dict]:
        if ped.empty or est.empty:
            return []
        ped = ped.copy()
        est = est.copy()
        cod_est = est["Cód Confec"].map(normalizar_cod) if "Cód Confec" in est.columns else est.get("Código", pd.Series(dtype=str))
        saldo2 = pd.to_numeric(est.get("Saldo 2"), errors="coerce").fillna(0) if "Saldo 2" in est.columns else pd.Series(0, index=est.index)
        codigos = set(cod_est[saldo2 < 0]) - {""}
        marca_map = {}
        if "Marca" in est.columns:
            for c, m in zip(cod_est, est["Marca"]):
                if c and pd.notna(m):
                    marca_map[c] = str(m).strip()
        ped["_cod"] = ped["Cód Confec"].map(normalizar_cod) if "Cód Confec" in ped.columns else ""
        kb = ped[ped["_cod"].isin(codigos)].copy()
        if kb.empty:
            return []
        saida = []
        for _, r in kb.iterrows():
            saida.append({
                "Pedido": str(r.get("Compra", "")),
                "Código": str(r.get("_cod", "")),
                "Item": str(r.get("Confeccionado", ""))[:60],
                "Confecção": str(r.get("Confecção", "")),
                "Marca": marca_map.get(str(r.get("_cod", "")), "—"),
                "Qtd": float(pd.to_numeric(r.get("Qtd"), errors="coerce") or 0),
                "Saldo": float(pd.to_numeric(r.get("Saldo"), errors="coerce") or 0),
                "Status": str(r.get("Status", "")),
            })
        return saida[:500]

    def _montar_compra(self, est: pd.DataFrame, ped: pd.DataFrame):
        if est.empty or "Saldo 5" not in est.columns:
            return [], [], "0"
        est = est.copy()
        saldo5 = pd.to_numeric(est["Saldo 5"], errors="coerce").fillna(0)
        neg = est[saldo5 < 0].copy()
        neg["_cod"] = neg["Cód Confec"].map(normalizar_cod) if "Cód Confec" in neg.columns else ""
        tec = pd.to_numeric(neg.get('Tec Faz "x" Confec'), errors="coerce").fillna(0) if 'Tec Faz "x" Confec' in neg.columns else 0
        neg["Compra"] = ((saldo5[neg.index].abs() * 1.10) - tec).clip(lower=0).round()
        itens = []
        for _, r in neg.iterrows():
            itens.append({
                "Código": str(r.get("_cod", "")),
                "Item": str(r.get("Descrição", ""))[:60],
                "Saldo 5": float(r.get("Saldo 5", 0)),
                "Tec Faz": float(tec.get(r.name, 0)) if hasattr(tec, "get") else 0.0,
                "Compra": float(r.get("Compra", 0)),
            })
        itens.sort(key=lambda x: x["Compra"], reverse=True)
        resumo = neg.assign(_conf="Sem confecção cadastrada").groupby("_conf").agg(
            Itens=("_cod", "count"), Compra=("Compra", "sum")
        ).reset_index().to_dict("records")
        resumo = [{"Confecção": str(r["_conf"]), "Itens": int(r["Itens"]), "Compra": float(r["Compra"])} for r in resumo]
        resumo.sort(key=lambda x: x["Compra"], reverse=True)
        total = f"{sum(x['Compra'] for x in itens):,.0f}".replace(",", ".")
        return itens[:500], resumo, total


# ============================ COMPONENTES ============================


def header() -> rx.Component:
    return rx.hstack(
        rx.heading("⚡ Visualfil Reflex", size="6"),
        rx.spacer(),
        rx.cond(State.logado, rx.text(State.nome), rx.text("")),
        rx.cond(State.logado, rx.button("Sair", on_click=State.sair, variant="soft")),
        width="100%", padding="1rem", border_bottom="1px solid #e2e8f0",
    )


def tabela(dados: list[dict], colunas: list[str]) -> rx.Component:
    return rx.data_table(
        data=dados,
        columns=colunas,
        pagination=True,
        search=True,
        sort=True,
        width="100%",
    )


# ============================ PÁGINAS ============================


@rx.page(route="/", title="Entrar — Visualfil Reflex")
def login_page() -> rx.Component:
    return rx.container(
        header(),
        rx.vstack(
            rx.heading("Acesso ao Visualfil Reflex", size="7"),
            rx.text("Versão paralela otimizada — mesma API do Visualfil Cloud."),
            rx.input(placeholder="URL do Web App (…/exec)", value=State.url,
                     on_change=State.definir_url, width="100%"),
            rx.hstack(
                rx.input(placeholder="Usuário", value=State.usuario,
                         on_change=State.definir_usuario, width="50%"),
                rx.input(placeholder="Senha", type="password", value=State.senha,
                         on_change=State.definir_senha, width="50%"),
                width="100%",
            ),
            rx.button("Entrar", on_click=State.entrar, width="100%"),
            rx.cond(State.mensagem, rx.callout(State.mensagem, color_scheme="red")),
            max_width="520px", margin_top="4rem", spacing="4",
        ),
    )


@rx.page(route="/kanban", title="Kanban — Visualfil Reflex", on_load=State.carregar_demandas)
def kanban_page() -> rx.Component:
    return rx.container(
        header(),
        rx.vstack(
            rx.heading("📋 Kanban online", size="7"),
            rx.hstack(
                rx.select(State.demanda_opcoes, value=State.demanda_nome,
                          on_change=State.selecionar_demanda,
                          placeholder="Selecione a demanda", width="300px"),
                rx.button("Carregar", on_click=State.carregar_dados),
                rx.cond(State.carregando, rx.spinner()),
                spacing="3",
            ),
            rx.cond(State.mensagem, rx.callout(State.mensagem, color_scheme="red")),
            rx.cond(
                State.pedidos,
                tabela(State.pedidos, ["Pedido", "Código", "Item", "Confecção", "Marca", "Qtd", "Saldo", "Status"]),
                rx.text("Nenhum pedido carregado."),
            ),
            spacing="4", width="100%",
        ),
    )


@rx.page(route="/compra", title="Compra sugerida — Visualfil Reflex", on_load=State.carregar_demandas)
def compra_page() -> rx.Component:
    return rx.container(
        header(),
        rx.vstack(
            rx.heading("🛒 Compra sugerida", size="7"),
            rx.hstack(
                rx.select(State.demanda_opcoes, value=State.demanda_nome,
                          on_change=State.selecionar_demanda,
                          placeholder="Selecione a demanda", width="300px"),
                rx.button("Carregar", on_click=State.carregar_dados),
                spacing="3",
            ),
            rx.card(rx.vstack(rx.text("Total compra sugerida"),
                              rx.heading(State.total_compra, size="7")), width="100%"),
            rx.heading("Por confecção", size="5"),
            rx.cond(State.compra_resumo,
                    tabela(State.compra_resumo, ["Confecção", "Itens", "Compra"]),
                    rx.text("Sem dados.")),
            rx.heading("Discriminado por item", size="5"),
            rx.cond(State.compra_itens,
                    tabela(State.compra_itens, ["Código", "Item", "Saldo 5", "Tec Faz", "Compra"]),
                    rx.text("Sem dados.")),
            spacing="4", width="100%",
        ),
    )


app = rx.App()
