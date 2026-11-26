"""Design system do Visualfil Reflex.

Componentes visuais reutilizáveis, paleta única e helpers de estilo.
Nenhuma dependência de Streamlit: este módulo é FastAPI/React puro via Reflex.
"""
from __future__ import annotations

from typing import Any

import reflex as rx

# ---------------------------------------------------------------- paleta
C: dict[str, str] = {
    "primary": "#4f46e5",
    "primary_dark": "#312e81",
    "primary_soft": "#eef2ff",
    "bg": "#f6f8fc",
    "surface": "#ffffff",
    "text": "#0f172a",
    "muted": "#64748b",
    "border": "#e2e8f0",
    "success": "#16a34a",
    "success_soft": "#dcfce7",
    "warning": "#d97706",
    "warning_soft": "#fef3c7",
    "danger": "#dc2626",
    "danger_soft": "#fee2e2",
    "info": "#0891b2",
    "info_soft": "#cffafe",
    "violet": "#7c3aed",
    "violet_soft": "#ede9fe",
}

CORES_STATUS: dict[str, str] = {
    "Pendente": "#0284c7",
    "Em andamento": "#d97706",
    "Pronto": "#059669",
    "Entregue": "#7a879c",
}

# Atalhos usados pelo quadro (evitam strings repetidas).
COR_STATUS_PENDENTE = CORES_STATUS["Pendente"]
COR_STATUS_ANDAMENTO = CORES_STATUS["Em andamento"]
COR_STATUS_PRONTO = CORES_STATUS["Pronto"]
COR_STATUS_ENTREGUE = CORES_STATUS["Entregue"]
CORES_PRIORIDADE: dict[str, str] = {
    "Atrasado": C["danger"],
    "Alta": C["warning"],
    "Média": "#2563eb",
    "Baixa": C["muted"],
}

FONTE = "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"


def css_global() -> rx.Component:
    """CSS único para o app inteiro (evita estilos espalhados)."""
    return rx.el.style(
        f"""
        * {{ font-family: {FONTE}; }}
        body {{ background: {C['bg']}; color: {C['text']}; margin: 0; }}
        .vf-card {{ transition: transform .16s ease, box-shadow .16s ease; }}
        .vf-card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 24px rgba(15,23,42,.08); }}
        .vf-nav a {{ text-decoration: none; }}
        .vf-nav-item {{ transition: background .15s ease, color .15s ease; }}
        .vf-nav-item:hover {{ background: rgba(255,255,255,.12); }}
        .vf-chip {{ letter-spacing: .02em; }}
        .vf-board {{ min-height: 78px; }}
        .vf-scroll::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        .vf-scroll::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 8px; }}
        """
    )


# ---------------------------------------------------------------- primitivas
def superficie(*conteudo: rx.Component, **props: Any) -> rx.Component:
    estilo = dict(
        background=C["surface"],
        border=f"1px solid {C['border']}",
        border_radius="14px",
        box_shadow="0 1px 3px rgba(15,23,42,.04)",
        padding="1.1rem",
        width="100%",
    )
    estilo.update(props)
    return rx.box(*conteudo, **estilo)


def titulo(texto: str, subtitulo: str = "", icone: str = "") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon(icone, size=26, color=C["primary"]) if icone else rx.fragment(),
            rx.heading(texto, size="7", color=C["text"], font_weight="700"),
            align_items="center", spacing="3",
        ),
        rx.cond(subtitulo, rx.text(subtitulo, size="2", color=C["muted"])),
        spacing="1", width="100%",
    )


def secao(nome: str, conteudo: rx.Component, acao: rx.Component | None = None) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading(nome, size="5", color=C["text"]),
            rx.spacer(),
            acao if acao is not None else rx.fragment(),
            width="100%", align_items="center",
        ),
        conteudo,
        spacing="3", width="100%",
    )


def kpi(
    rotulo: str,
    valor: rx.Component | str,
    rodape: str = "",
    icone: str = "chart-column",
    cor: str = C["primary"],
) -> rx.Component:
    return superficie(
        rx.hstack(
            rx.box(
                rx.icon(icone, size=18, color=cor),
                background="#e0e7ff" if cor == C["primary"] else f"{cor}1a",
                border_radius="10px", padding="0.55rem",
            ),
            rx.vstack(
                rx.text(rotulo, size="1", color=C["muted"], text_transform="uppercase",
                        letter_spacing=".06em"),
                rx.heading(valor, size="6", color=C["text"], font_weight="700"),
                rx.cond(rodape, rx.text(rodape, size="1", color=C["muted"])),
                spacing="1", align_items="start", flex="1",
            ),
            align_items="start", spacing="3", width="100%",
        ),
        class_name="vf-card",
    )


def chip(texto: rx.Component | str, cor: str = C["primary"], suave: bool = True) -> rx.Component:
    return rx.badge(
        texto,
        variant="soft",
        color_scheme=_scheme(cor),
        border_radius="999px",
        padding="0.15rem 0.55rem",
        font_size="0.72rem",
        class_name="vf-chip",
    )


def _scheme(cor: str) -> str:
    mapa = {
        C["danger"]: "red", C["warning"]: "amber", C["success"]: "green",
        C["info"]: "cyan", C["violet"]: "violet", C["muted"]: "gray",
        C["primary"]: "indigo", "#3b82f6": "blue", "#22c55e": "green",
        "#10b981": "green", "#64748b": "gray", "#f59e0b": "amber",
        "#0284c7": "sky", "#d97706": "amber", "#059669": "green",
        "#7a879c": "gray", "#2563eb": "blue",
    }
    return mapa.get(cor, "indigo")


def status_chip(status: str) -> rx.Component:
    return chip(status, CORES_STATUS.get(status, C["muted"]))


def prioridade_chip(prioridade: str) -> rx.Component:
    return chip(prioridade, CORES_PRIORIDADE.get(prioridade, C["muted"]))


def tabela(dados: rx.Component | list[dict], colunas: list[str], altura: str = "360px") -> rx.Component:
    return superficie(
        rx.data_table(
            data=dados,
            columns=colunas,
            pagination=True,
            search=True,
            sort=True,
            width="100%",
            height=altura,
        ),
        padding="0.5rem",
    )


def vazio(mensagem: str, icone: str = "inbox", acao: rx.Component | None = None) -> rx.Component:
    return superficie(
        rx.vstack(
            rx.icon(icone, size=32, color=C["muted"]),
            rx.text(mensagem, color=C["muted"], size="2", text_align="center"),
            acao if acao is not None else rx.fragment(),
            align_items="center", spacing="2", padding="2rem", width="100%",
        )
    )


def barra(valor: rx.Component, total: rx.Component, cor: str = C["primary"]) -> rx.Component:
    valor = valor.to(float) if hasattr(valor, "to") else valor
    total = total.to(float) if hasattr(total, "to") else total
    return rx.box(
        rx.box(
            height="100%",
            width=rx.cond(total > 0, rx.cond(valor > total, "100%", f"calc({valor} / {total} * 100%)"), "0%"),
            background=cor, border_radius="999px",
        ),
        height="8px", width="100%", background="#e2e8f0", border_radius="999px",
    )


# ---------------------------------------------------------------- layout
NAV: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("OPERAÇÃO", [
        ("Kanban Online", "/kanban", "layout-dashboard", "kanban-online"),
        ("Kanban Confecção", "/kanban-offline", "clipboard-list", "kanban-offline"),
    ]),
    ("ANÁLISE", [
        ("Compra sugerida", "/compra", "shopping-cart", "compra"),
        ("Dashboards", "/dashboards", "chart-no-axes-column-increasing", "dashboards"),
        ("Projeção", "/projecao", "calendar-days", "projecao"),
    ]),
    ("SISTEMA", [
        ("Administração", "/admin", "settings", "admin"),
    ]),
]


def _item_nav(rotulo: str, href: str, icone: str, chave: str, ativa: str) -> rx.Component:
    selecionado = chave == ativa
    return rx.link(
        rx.hstack(
            rx.icon(icone, size=17),
            rx.text(rotulo, size="2", font_weight="500"),
            spacing="3", align_items="center",
            padding="0.55rem 0.75rem",
            border_radius="9px",
            color="white" if selecionado else "#c7d2fe",
            background="rgba(255,255,255,.16)" if selecionado else "transparent",
            width="100%",
            class_name="vf-nav-item",
        ),
        href=href, width="100%", class_name="vf-nav",
    )


def sidebar(ativa: str, nome, admin, state) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(
                rx.icon("zap", size=20, color="white"),
                background="#6366f1", border_radius="11px", padding="0.45rem",
            ),
            rx.vstack(
                rx.text("Visualfil", color="white", font_weight="700", size="4"),
                rx.text("Produção inteligente", color="#a5b4fc", size="1"),
                spacing="0",
            ),
            spacing="3", align_items="center",
        ),
        rx.divider(color="rgba(255,255,255,.14)", margin_y="0.5rem"),
        *[
            rx.vstack(
                rx.text(grupo, size="1", color="#818cf8", letter_spacing=".1em",
                        font_weight="700", padding_x="0.75rem"),
                *[
                    rx.cond(
                        rx.match(
                            chave,
                            ("kanban-offline", state.pode_kanban_off),
                            ("kanban-online", state.pode_online),
                            ("compra", state.pode_online),
                            ("dashboards", state.pode_dashboards),
                            ("projecao", state.pode_projecao),
                            ("admin", state.admin),
                            True,
                        ),
                        _item_nav(rotulo, href, icone, chave, ativa),
                    )
                    for rotulo, href, icone, chave in itens
                ],
                spacing="1", width="100%",
            )
            for grupo, itens in NAV
        ],
        rx.spacer(),
        rx.box(
            rx.hstack(
                rx.avatar(fallback=rx.cond(nome, nome, "U"), size="2", color_scheme="indigo"),
                rx.vstack(
                    rx.text(rx.cond(nome, nome, "Usuário"), color="white", size="2", font_weight="600"),
                    rx.text(rx.cond(state.admin, "Administrador", "Operador"), color="#a5b4fc", size="1"),
                    spacing="0",
                ),
                spacing="2", align_items="center",
            ),
            width="100%", padding_top="0.75rem", border_top="1px solid rgba(255,255,255,.14)",
        ),
        background=f"linear-gradient(180deg, {C['primary_dark']} 0%, #1e1b4b 100%)",
        min_height="100vh", width="248px", padding="1.1rem", spacing="3",
        flex_shrink="0",
    )


def aviso_ui(state) -> rx.Component:
    return rx.cond(
        state.mensagem,
        rx.callout(
            state.mensagem,
            color_scheme=rx.cond(
                state.tipo_mensagem == "error", "red",
                rx.cond(state.tipo_mensagem == "success", "green", "blue"),
            ),
            width="100%",
        ),
    )


def shell(
    conteudo: rx.Component,
    ativa: str,
    titulo_pagina: str,
    subtitulo: str = "",
    acoes: rx.Component | None = None,
    state=None,
) -> rx.Component:
    return rx.box(
        css_global(),
        rx.hstack(
            rx.box(sidebar(ativa, state.nome, state.admin, state),
                   display=["none", "none", "flex"], flex_shrink="0"),
            rx.vstack(
                rx.hstack(
                    rx.vstack(titulo(titulo_pagina, subtitulo), spacing="0"),
                    rx.spacer(),
                    acoes if acoes is not None else rx.fragment(),
                    rx.button(
                        "Sair", on_click=state.sair, variant="soft", color_scheme="gray",
                        icon="log-out", size="2",
                    ),
                    width="100%", align_items="center", spacing="3", wrap="wrap",
                    padding="1rem 1.5rem",
                    background=C["surface"], border_bottom=f"1px solid {C['border']}",
                ),
                rx.box(
                    conteudo,
                    aviso_ui(state),
                    width="100%", padding="1.5rem", spacing="4",
                    class_name="vf-scroll",
                    flex="1",
                    overflow_y="auto",
                ),
                width="100%", min_height="100vh", spacing="0",
            ),
            width="100%", min_height="100vh", background=C["bg"], align_items="stretch",
        ),
    )


# ---------------------------------------------------------------- login
def painel_login(formulario: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(rx.icon("zap", size=30, color="white"),
                   background="rgba(255,255,255,.16)", border_radius="14px", padding="0.7rem"),
            rx.heading("Visualfil", size="8", color="white"),
            spacing="3", align_items="center",
        ),
        rx.heading("Produção sob controle, de ponta a ponta.", size="6", color="white",
                   margin_top="2rem"),
        rx.text(
            "Kanban de confecção, compra sugerida, projeção e demandas online "
            "em uma única plataforma.",
            color="#c7d2fe", size="3", line_height="1.6",
        ),
        rx.vstack(
            rx.hstack(rx.icon("circle-check", color="#a5b4fc"),
                      rx.text("Quadro offline com upload local dos XLSX", color="white", size="2")),
            rx.hstack(rx.icon("circle-check", color="#a5b4fc"),
                      rx.text("Leitura online por demanda (Remessa)", color="white", size="2")),
            rx.hstack(rx.icon("circle-check", color="#a5b4fc"),
                      rx.text("Permissões por usuário e por página", color="white", size="2")),
            spacing="3", margin_top="1.5rem", align_items="start",
        ),
        formulario,
        spacing="3", width="100%", max_width="520px",
        padding="2.5rem",
        background=f"linear-gradient(145deg, {C['primary']} 0%, {C['primary_dark']} 100%)",
        min_height="100vh", justify="center",
    )
