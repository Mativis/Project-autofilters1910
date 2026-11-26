"""Design system do Visualfil Reflex.

Componentes visuais reutilizáveis, paleta única e helpers de estilo.
Nenhuma dependência de Streamlit: este módulo é FastAPI/React puro via Reflex.
"""
from __future__ import annotations

from typing import Any

import reflex as rx

# ---------------------------------------------------------------- paleta
C: dict[str, str] = {
    # Tendência 2026 aplicada: "Command Center" B2B SaaS — bento/modular,
    # hierarquia em pirâmide invertida (KPIs -> contexto -> detalhe),
    # alta densidade com clareza e escala comercial.
    "primary": "#2563eb",
    "primary_dark": "#0b1220",
    "primary_soft": "#dbeafe",
    "bg": "#f3f6fb",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "text": "#0f172a",
    "muted": "#475569",
    "border": "#e6edf5",
    "success": "#059669",
    "success_soft": "#d1fae5",
    "warning": "#d97706",
    "warning_soft": "#fef3c7",
    "danger": "#dc2626",
    "danger_soft": "#fee2e2",
    "info": "#0284c7",
    "info_soft": "#e0f2fe",
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
    """CSS global: estilo 'Command Center' B2B, modular e escalável."""
    return rx.el.style(
        f"""
        * {{ font-family: {FONTE}; box-sizing: border-box; }}
        body {{ background: {C['bg']}; color: {C['text']}; margin: 0; }}
        .vf-card {{ transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }}
        .vf-card:hover {{ transform: translateY(-1px); border-color: #bfdbfe; box-shadow: 0 8px 28px rgba(37,99,235,.08); }}
        .vf-nav a {{ text-decoration: none; }}
        .vf-nav-item {{ transition: background .15s ease, color .15s ease, border-color .15s ease; border: 1px solid transparent; }}
        .vf-nav-item:hover {{ background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.08); }}
        .vf-chip {{ letter-spacing: .03em; font-weight: 600; }}
        .vf-board {{ min-height: 84px; }}
        .vf-surface {{ backdrop-filter: saturate(120%); }}
        .vf-kpi {{ position: relative; overflow: hidden; }}
        .vf-kpi:before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background: linear-gradient(90deg, rgba(37,99,235,.9), rgba(37,99,235,0)); opacity:.55; }}
        .vf-scroll::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        .vf-scroll::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 8px; }}
        .vf-table [data-radix-scroll-area-viewport] {{ background: {C['surface']}; }}
        @media (max-width: 900px) {{
            .vf-page-pad {{ padding: 1rem !important; }}
        }}
        """
    )


# ---------------------------------------------------------------- primitivas
def superficie(*conteudo: rx.Component, **props: Any) -> rx.Component:
    """Módulo base (bento): reutilizável, com borda suave e raio consistente."""
    estilo = dict(
        background=C["surface"],
        border=f"1px solid {C['border']}",
        border_radius="16px",
        box_shadow="0 1px 2px rgba(15,23,42,.03)",
        padding="1.15rem",
        width="100%",
        class_name="vf-surface",
    )
    # permite compor class_name sem perder a base
    extra_class = props.pop("class_name", "")
    if extra_class:
        estilo["class_name"] = f"{estilo['class_name']} {extra_class}"
    estilo.update(props)
    return rx.box(*conteudo, **estilo)


def titulo(texto: str, subtitulo: str = "", icone: str = "") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(
                rx.icon(icone, size=20, color=C["primary"]),
                background=C["primary_soft"], border_radius="10px", padding="0.45rem",
            ) if icone else rx.fragment(),
            rx.heading(texto, size="7", color=C["text"], font_weight="700", letter_spacing="-0.02em"),
            align_items="center", spacing="3",
        ),
        rx.cond(subtitulo, rx.text(subtitulo, size="2", color=C["muted"], line_height="1.5")),
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
    fundo = C["primary_soft"] if cor == C["primary"] else f"{cor}14"
    return superficie(
        rx.hstack(
            rx.vstack(
                rx.text(rotulo, size="1", color=C["muted"], text_transform="uppercase",
                        letter_spacing=".08em", font_weight="600"),
                rx.heading(valor, size="7", color=C["text"], font_weight="700",
                           letter_spacing="-0.03em", line_height="1.1"),
                rx.cond(rodape, rx.text(rodape, size="1", color=C["muted"])),
                spacing="1", align_items="start", flex="1",
            ),
            rx.box(
                rx.icon(icone, size=18, color=cor),
                background=fundo, border_radius="12px", padding="0.6rem",
                border=f"1px solid {cor}22",
            ),
            align_items="start", justify="between", spacing="3", width="100%",
        ),
        class_name="vf-card vf-kpi",
        padding="1rem 1.1rem",
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
        rx.box(
            rx.data_table(
                data=dados,
                columns=colunas,
                pagination=True,
                search=True,
                sort=True,
                width="100%",
                height=altura,
            ),
            width="100%",
            class_name="vf-table",
        ),
        padding="0.35rem",
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
            rx.box(width="3px", height="18px", border_radius="3px",
                   background="#60a5fa" if selecionado else "transparent"),
            rx.icon(icone, size=17, color="#f1f5f9" if selecionado else "#cbd5e1"),
            rx.text(rotulo, size="2", font_weight="550",
                    color="#ffffff" if selecionado else "#e2e8f0"),
            spacing="2", align_items="center",
            padding="0.55rem 0.65rem",
            border_radius="10px",
            background="rgba(59,130,246,.14)" if selecionado else "transparent",
            border=f"1px solid {'rgba(59,130,246,.22)' if selecionado else 'transparent'}",
            width="100%",
            class_name="vf-nav-item",
        ),
        href=href, width="100%", class_name="vf-nav",
    )


def sidebar(ativa: str, nome, admin, state) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(
                rx.icon("layers-3", size=20, color="white"),
                background="linear-gradient(135deg, #3b82f6, #2563eb)",
                border_radius="12px", padding="0.5rem",
                box_shadow="0 8px 24px rgba(37,99,235,.35)",
            ),
            rx.vstack(
                rx.text("Visualfil", color="white", font_weight="700", size="4",
                        letter_spacing="-0.02em"),
                rx.text("Production Command Center", color="#bfdbfe", size="1"),
                spacing="0",
            ),
            spacing="3", align_items="center",
        ),
        rx.box(height="1px", background="rgba(255,255,255,.08)", width="100%", margin_y="0.4rem"),
        *[
            rx.vstack(
                rx.text(grupo, size="1", color="#94a3b8", letter_spacing=".12em",
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
                rx.avatar(fallback=rx.cond(nome, nome, "U"), size="2", color_scheme="blue"),
                rx.vstack(
                    rx.text(rx.cond(nome, nome, "Usuário"), color="#f1f5f9", size="2", font_weight="600"),
                    rx.text(rx.cond(state.admin, "Administrador", "Operador"), color="#cbd5e1", size="1"),
                    spacing="0",
                ),
                spacing="2", align_items="center",
            ),
            width="100%", padding="0.75rem", border_radius="12px",
            background="rgba(255,255,255,.04)", border="1px solid rgba(255,255,255,.06)",
        ),
        background=f"linear-gradient(180deg, {C['primary_dark']} 0%, #111827 100%)",
        min_height="100vh", width="256px", padding="1rem", spacing="3",
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
                    rx.hstack(
                        acoes if acoes is not None else rx.fragment(),
                        rx.button(
                            "Sair", on_click=state.sair, variant="soft", color_scheme="gray",
                            icon="log-out", size="2",
                        ),
                        spacing="2", align_items="center",
                    ),
                    width="100%", align_items="center", spacing="3", wrap="wrap",
                    padding="1.1rem 1.5rem",
                    background="rgba(255,255,255,.92)",
                    border_bottom=f"1px solid {C['border']}",
                    position="sticky", top="0", z_index="10",
                    backdrop_filter="blur(10px)",
                ),
                rx.box(
                    rx.vstack(
                        aviso_ui(state),
                        conteudo,
                        spacing="4", width="100%",
                        max_width="1680px", margin_x="auto",
                    ),
                    width="100%", padding="1.5rem",
                    class_name="vf-scroll vf-page-pad",
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
            rx.box(rx.icon("layers-3", size=28, color="white"),
                   background="linear-gradient(135deg, #3b82f6, #2563eb)",
                   border_radius="14px", padding="0.7rem",
                   box_shadow="0 12px 30px rgba(37,99,235,.4)"),
            rx.vstack(
                rx.text("Visualfil", size="7", color="white", font_weight="700",
                        letter_spacing="-0.03em"),
                rx.text("Production Command Center", size="2", color="#dbeafe"),
                spacing="0",
            ),
            spacing="3", align_items="center",
        ),
        rx.heading("Visão operacional para escalar produção.", size="7", color="white",
                   margin_top="2.2rem", letter_spacing="-0.03em", line_height="1.15"),
        rx.text(
            "Kanban offline, demandas online, compra sugerida e projeção em uma "
            "plataforma modular — pronta para crescer com a operação.",
            color="#e2e8f0", size="3", line_height="1.7", max_width="520px",
        ),
        rx.vstack(
            *[
                rx.hstack(
                    rx.box(rx.icon(icone, size=16, color="#dbeafe"),
                           background="rgba(147,197,253,.14)", border_radius="8px", padding="0.35rem"),
                    rx.text(txt, color="#f8fafc", size="2"),
                    spacing="3", align_items="center",
                )
                for icone, txt in [
                    ("layout-dashboard", "Quadro operacional offline com upload local"),
                    ("cloud", "Demandas online por Remessa, leitura sob demanda"),
                    ("shield-check", "Permissões por usuário e trilha de ações"),
                    ("chart-column-increasing", "KPIs, compra sugerida e projeção escalável"),
                ]
            ],
            spacing="3", margin_top="1.5rem", align_items="start",
        ),
        formulario,
        spacing="4", width="100%", max_width="560px",
        padding="3rem",
        background=f"radial-gradient(ellipse at top left, #1e3a5f 0%, {C['primary_dark']} 55%, #0f172a 100%)",
        min_height="100vh", justify="center",
    )
