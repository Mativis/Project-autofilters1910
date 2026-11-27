"""Design system Visualfil Reflex — production-ready UI.

Command Center B2B: claro, denso, responsivo, navegação consistente.
Sem dependência de Streamlit.
"""
from __future__ import annotations

from typing import Any

import reflex as rx

# ---------------------------------------------------------------- palette
C: dict[str, str] = {
    "primary": "#2563eb",
    "primary_dark": "#0b1220",
    "primary_soft": "#dbeafe",
    "bg": "#f3f6fb",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "text": "#0f172a",
    "muted": "#475569",
    "muted_2": "#64748b",
    "border": "#e6edf5",
    "border_strong": "#cbd5e1",
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
    "Entregue": "#64748b",
}
COR_STATUS_PENDENTE = CORES_STATUS["Pendente"]
COR_STATUS_ANDAMENTO = CORES_STATUS["Em andamento"]
COR_STATUS_PRONTO = CORES_STATUS["Pronto"]
COR_STATUS_ENTREGUE = CORES_STATUS["Entregue"]
CORES_PRIORIDADE: dict[str, str] = {
    "Atrasado": C["danger"],
    "Alta": C["warning"],
    "Média": "#2563eb",
    "Baixa": C["muted_2"],
}

FONTE = "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"

NAV: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    ("OPERAÇÃO", [
        ("Kanban Online", "/kanban", "layout-dashboard", "kanban-online"),
        ("Kanban Confecção (Offline)", "/kanban-offline", "clipboard-list", "kanban-offline"),
    ]),
    ("ANÁLISE", [
        ("Compra sugerida", "/compra", "shopping-cart", "compra"),
        ("Dashboards", "/dashboards", "chart-no-axes-column-increasing", "dashboards"),
        ("Projeção", "/projecao", "calendar-days", "projecao"),
    ]),
    ("SISTEMA", [
        ("Arquivos", "/arquivos", "folder-open", "arquivos"),
        ("Administração", "/admin", "settings", "admin"),
    ]),
]


def css_global() -> rx.Component:
    return rx.el.style(
        f"""
        * {{ font-family: {FONTE}; box-sizing: border-box; }}
        :root, .light, .light-theme, .radix-themes {{ color-scheme: light !important; }}
        body, .radix-themes {{ background: {C['bg']}; color: {C['text']}; margin: 0; }}
        a {{ text-decoration: none; color: inherit; }}
        .vf-surface {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.03); }}
        .vf-card {{ transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }}
        .vf-card:hover {{ transform: translateY(-1px); border-color: #bfdbfe; box-shadow: 0 8px 28px rgba(37,99,235,.08); }}
        .vf-kpi {{ position: relative; overflow: hidden; }}
        .vf-kpi:before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background: linear-gradient(90deg, rgba(37,99,235,.85), rgba(37,99,235,0)); opacity:.5; }}
        .vf-nav-item {{ transition: background .15s ease, border-color .15s ease, color .15s ease; border:1px solid transparent; border-radius:10px; }}
        .vf-nav-item:hover {{ background: rgba(255,255,255,.07); border-color: rgba(255,255,255,.08); }}
        .vf-scroll::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        .vf-scroll::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 8px; }}
        .vf-page {{ width:100%; max-width: 1680px; margin: 0 auto; }}
        /* Radix contrast fixes */
        .rt-Card {{ color: {C['text']} !important; background-color: {C['surface']} !important; border-color: {C['border']} !important; }}
        .rt-TextFieldInput, .rt-TextAreaInput, .rt-SelectTrigger {{ color:{C['text']} !important; background:#fff !important; border-color:{C['border_strong']} !important; }}
        .rt-TextFieldInput::placeholder, .rt-TextAreaInput::placeholder {{ color:#64748b !important; opacity:1; }}
        .rt-TableRoot, .rt-TableCell, .rt-TableColumnHeaderCell {{ color:{C['text']}; }}
        .rt-TabsTrigger {{ color:#334155; font-weight:500; }}
        .rt-TabsTrigger[data-state='active'] {{ color:{C['primary']}; font-weight:600; }}
        .rt-Badge {{ font-weight:600; }}
        @media (max-width: 1024px) {{ .vf-desktop-sidebar {{ display:none !important; }} .vf-mobile-menu {{ display:inline-flex !important; }} }}
        @media (min-width: 1025px) {{ .vf-mobile-menu {{ display:none !important; }} }}
        @media (max-width: 768px) {{ .vf-page-pad {{ padding: 1rem !important; }} .vf-topbar {{ padding: 0.85rem 1rem !important; }} }}
        """
    )


# ---------------------------------------------------------------- primitives
def superficie(*children: rx.Component, **props: Any) -> rx.Component:
    cls = props.pop("class_name", "")
    base = {"class_name": f"vf-surface {cls}".strip(), "padding": "1.15rem", "width": "100%"}
    base.update(props)
    return rx.box(*children, **base)


def secao(titulo: str, conteudo: rx.Component, acao: rx.Component | None = None, subtitulo: str = "") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.heading(titulo, size="4", color=C["text"], letter_spacing="-0.01em"),
                rx.cond(subtitulo != "", rx.text(subtitulo, size="2", color=C["muted"]), rx.fragment()),
                spacing="1", align_items="start",
            ),
            rx.spacer(),
            acao if acao is not None else rx.fragment(),
            width="100%", align_items="start", wrap="wrap", gap="0.75rem",
        ),
        conteudo,
        spacing="3", width="100%",
    )


def kpi(rotulo: str, valor: rx.Component | str, rodape: str = "", icone: str = "chart-column", cor: str = C["primary"]) -> rx.Component:
    fundo = f"{cor}14"
    return superficie(
        rx.hstack(
            rx.vstack(
                rx.text(rotulo, size="1", color="#334155", text_transform="uppercase", letter_spacing=".08em", font_weight="700"),
                rx.heading(valor, size="7", color=C["text"], font_weight="700", letter_spacing="-0.03em", line_height="1.1"),
                rx.cond(rodape != "", rx.text(rodape, size="1", color=C["muted"]), rx.fragment()),
                spacing="1", align_items="start", flex="1",
            ),
            rx.box(rx.icon(icone, size=18, color=cor), background=fundo, border=f"1px solid {cor}22", border_radius="12px", padding="0.6rem"),
            align_items="start", justify="between", width="100%", spacing="3",
        ),
        class_name="vf-surface vf-card vf-kpi",
        padding="1rem 1.1rem",
    )


def _scheme(cor: str) -> str:
    mapa = {
        C["danger"]: "red", C["warning"]: "amber", C["success"]: "green", C["info"]: "sky",
        C["violet"]: "violet", C["muted"]: "gray", C["primary"]: "blue", "#2563eb": "blue",
        "#0284c7": "sky", "#d97706": "amber", "#059669": "green", "#64748b": "gray", "#dc2626": "red",
    }
    return mapa.get(cor, "blue")


def chip(texto: rx.Component | str, cor: str = C["primary"], suave: bool = True) -> rx.Component:
    return rx.badge(texto, variant="soft" if suave else "solid", color_scheme=_scheme(cor), radius="full", size="1")


def status_chip(status: str) -> rx.Component:
    return chip(status, CORES_STATUS.get(status, C["muted"]))


def prioridade_chip(prioridade: str) -> rx.Component:
    return chip(prioridade, CORES_PRIORIDADE.get(prioridade, C["muted"]))


def vazio(mensagem: str, icone: str = "inbox", acao: rx.Component | None = None) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(rx.icon(icone, size=24, color=C["muted_2"]), background=C["surface_alt"], border=f"1px solid {C['border']}", border_radius="14px", padding="0.8rem"),
            rx.text(mensagem, size="2", color=C["muted"], text_align="center", max_width="420px"),
            acao if acao is not None else rx.fragment(),
            spacing="3", align_items="center", padding="2rem 1rem",
        ),
        width="100%", min_height="180px",
    )


def barra(valor, total, cor: str = C["primary"]) -> rx.Component:
    valor_n = valor.to(float) if hasattr(valor, "to") else rx.Var.create(valor).to(float)
    total_n = total.to(float) if hasattr(total, "to") else rx.Var.create(total).to(float)
    pct = rx.cond(total_n > 0, (valor_n * 100 / total_n).to(int), 0)
    largura = rx.cond(pct > 100, "100%", pct.to(str) + "%")
    return rx.box(
        rx.box(width=largura, height="100%", background=cor, border_radius="999px"),
        width="100%", height="8px", background="#e2e8f0", border_radius="999px", overflow="hidden",
    )


def tabela(dados: rx.Var | list[dict], colunas: list[str], altura: str = "360px") -> rx.Component:
    def celula(linha, c):
        val = linha[c]
        return rx.table.cell(
            rx.cond(val, val.to_string(), rx.cond(val == 0, "0", "—")),
            style={"fontSize": "0.82rem", "color": C["text"], "whiteSpace": "nowrap"},
        )

    return superficie(
        rx.box(
            rx.cond(
                dados.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(*[
                            rx.table.column_header_cell(
                                c, style={"color": "#334155", "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": ".04em", "fontWeight": "700", "whiteSpace": "nowrap"},
                            ) for c in colunas
                        ])
                    ),
                    rx.table.body(
                        rx.foreach(
                            dados,
                            lambda linha: rx.table.row(*[celula(linha, c) for c in colunas], _hover={"background": C["surface_alt"]}),
                        )
                    ),
                    variant="surface", size="1", width="100%",
                ),
                vazio("Nenhum dado disponível para esta seleção.", "database"),
            ),
            width="100%", max_height=altura, overflow="auto", class_name="vf-scroll",
        ),
        padding="0.35rem",
    )


# ---------------------------------------------------------------- navigation / layout
def _pode(chave: str, state) -> rx.Var:
    return rx.match(
        chave,
        ("kanban-offline", state.pode_kanban_off),
        ("kanban-online", state.pode_online),
        ("compra", state.pode_online),
        ("dashboards", state.pode_dashboards),
        ("projecao", state.pode_projecao),
        ("arquivos", state.pode_online),
        ("admin", state.admin),
        True,
    )


def _nav_item(rotulo: str, href: str, icone: str, chave: str, ativa: str) -> rx.Component:
    selecionado = chave == ativa
    return rx.link(
        rx.hstack(
            rx.box(width="3px", height="18px", border_radius="3px", background="#60a5fa" if selecionado else "transparent"),
            rx.icon(icone, size=17, color="#f8fafc" if selecionado else "#cbd5e1"),
            rx.text(rotulo, size="2", weight="medium", color="#ffffff" if selecionado else "#e2e8f0"),
            spacing="2", align_items="center", padding="0.58rem 0.7rem", width="100%",
            background="rgba(59,130,246,.14)" if selecionado else "transparent",
            border=f"1px solid {'rgba(59,130,246,.22)' if selecionado else 'transparent'}",
            class_name="vf-nav-item",
        ),
        href=href, width="100%",
    )


def _nav_conteudo(ativa: str, state) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(rx.icon("layers-3", size=20, color="white"), background="linear-gradient(135deg,#3b82f6,#2563eb)", border_radius="12px", padding="0.5rem", box_shadow="0 8px 24px rgba(37,99,235,.35)"),
            rx.vstack(
                rx.text("Visualfil", color="#fff", weight="bold", size="4", letter_spacing="-0.02em"),
                rx.text("Production Command Center", color="#bfdbfe", size="1"),
                spacing="0",
            ),
            spacing="3", align_items="center", width="100%",
        ),
        rx.box(height="1px", background="rgba(255,255,255,.08)", width="100%"),
        *[
            rx.vstack(
                rx.text(grupo, size="1", color="#94a3b8", weight="bold", letter_spacing=".12em", padding_x="0.75rem"),
                *[rx.cond(_pode(chave, state), _nav_item(rotulo, href, icone, chave, ativa), rx.fragment()) for rotulo, href, icone, chave in itens],
                spacing="1", width="100%",
            )
            for grupo, itens in NAV
        ],
        rx.spacer(),
        rx.box(
            rx.hstack(
                rx.avatar(fallback=rx.cond(state.nome != "", state.nome, "U"), size="2", radius="full", color_scheme="blue"),
                rx.vstack(
                    rx.text(rx.cond(state.nome != "", state.nome, "Usuário"), color="#f8fafc", size="2", weight="medium"),
                    rx.text(rx.cond(state.admin, "Administrador", "Operador"), color="#cbd5e1", size="1"),
                    spacing="0", align_items="start",
                ),
                spacing="2", align_items="center",
            ),
            width="100%", padding="0.75rem", border_radius="12px", background="rgba(255,255,255,.04)", border="1px solid rgba(255,255,255,.06)",
        ),
        spacing="4", width="100%", min_height="100%",
        padding="1rem",
        background="linear-gradient(180deg, #0b1220 0%, #111827 100%)",
    )


def sidebar(ativa: str, state) -> rx.Component:
    return rx.box(
        _nav_conteudo(ativa, state),
        width="272px", min_width="272px", min_height="100vh", display=["none", "none", "none", "block"],
        class_name="vf-desktop-sidebar", position="sticky", top="0", align_self="stretch",
    )


def mobile_nav(ativa: str, state) -> rx.Component:
    return rx.drawer.root(
        rx.drawer.trigger(
            rx.button(rx.icon("menu", size=18), variant="soft", color_scheme="gray", size="2", class_name="vf-mobile-menu"),
        ),
        rx.drawer.overlay(),
        rx.drawer.portal(
            rx.drawer.content(
                _nav_conteudo(ativa, state),
                width="290px", max_width="88vw", padding="0", background="#0f172a",
            )
        ),
        direction="left",
    )


def aviso_ui(state) -> rx.Component:
    return rx.cond(
        state.mensagem != "",
        rx.callout.root(
            rx.callout.icon(rx.icon(rx.cond(state.tipo_mensagem == "error", "triangle-alert", rx.cond(state.tipo_mensagem == "success", "circle-check", "info")), size=16)),
            rx.callout.text(state.mensagem),
            color_scheme=rx.cond(state.tipo_mensagem == "error", "red", rx.cond(state.tipo_mensagem == "success", "green", "blue")),
            variant="soft", width="100%",
        ),
        rx.fragment(),
    )


def overlay_carregando(state) -> rx.Component:
    ativo = rx.cond(state.carregando, True, state.off_processando)
    return rx.cond(
        ativo,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color=C["primary"]),
                    rx.text(rx.cond(state.off_processando, "Processando arquivos locais...", "Carregando dados..."), size="3", weight="medium", color=C["text"]),
                    rx.text(rx.cond(state.diagnostico != "", state.diagnostico, "Aguarde alguns instantes."), size="2", color=C["muted"], text_align="center", max_width="440px"),
                    spacing="3", align_items="center", background=C["surface"], border=f"1px solid {C['border']}", border_radius="16px", padding="1.5rem 2rem", box_shadow="0 20px 60px rgba(15,23,42,.18)",
                ),
                width="100%", height="100%",
            ),
            position="fixed", inset="0", z_index="999", background="rgba(243,246,251,.72)", backdrop_filter="blur(3px)",
        ),
        rx.fragment(),
    )


def topbar(titulo_pagina: str, subtitulo: str, acoes: rx.Component | None, state, ativa: str) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.hstack(
                mobile_nav(ativa, state),
                rx.vstack(
                    rx.heading(titulo_pagina, size="6", color=C["text"], letter_spacing="-0.02em"),
                    rx.cond(subtitulo != "", rx.text(subtitulo, size="2", color=C["muted"]), rx.fragment()),
                    spacing="0", align_items="start",
                ),
                spacing="3", align_items="center",
            ),
            rx.spacer(),
            rx.hstack(
                acoes if acoes is not None else rx.fragment(),
                rx.button("Sair", on_click=state.sair, variant="soft", color_scheme="gray", size="2"),
                spacing="2", align_items="center", wrap="wrap", justify="end",
            ),
            width="100%", align_items="center", justify="between", gap="0.75rem", wrap="wrap",
        ),
        padding="1rem 1.5rem", background="rgba(255,255,255,.92)", border_bottom=f"1px solid {C['border']}",
        position="sticky", top="0", z_index="20", backdrop_filter="blur(10px)", class_name="vf-topbar",
    )


def shell(conteudo: rx.Component, ativa: str, titulo_pagina: str, subtitulo: str = "", acoes: rx.Component | None = None, state=None) -> rx.Component:
    return rx.box(
        css_global(),
        overlay_carregando(state),
        rx.hstack(
            sidebar(ativa, state),
            rx.vstack(
                topbar(titulo_pagina, subtitulo, acoes, state, ativa),
                rx.box(
                    rx.vstack(aviso_ui(state), conteudo, spacing="4", width="100%", class_name="vf-page"),
                    width="100%", padding="1.5rem", class_name="vf-scroll vf-page-pad", flex="1", overflow_y="auto",
                ),
                width="100%", min_height="100vh", spacing="0", min_width="0",
            ),
            width="100%", min_height="100vh", align_items="stretch", spacing="0", background=C["bg"],
        ),
        width="100%", min_height="100vh",
    )


# ---------------------------------------------------------------- login
def painel_login(formulario: rx.Component) -> rx.Component:
    recursos = [
        ("layout-dashboard", "Kanban offline e online por demanda"),
        ("shield-check", "Permissões por página e perfis"),
        ("shopping-cart", "Compra sugerida e indicadores"),
        ("calendar-days", "Projeção e capacidade operacional"),
    ]
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(rx.icon("layers-3", size=26, color="white"), background="linear-gradient(135deg,#3b82f6,#2563eb)", border_radius="14px", padding="0.65rem", box_shadow="0 12px 30px rgba(37,99,235,.4)"),
                rx.vstack(rx.text("Visualfil", size="7", color="white", weight="bold", letter_spacing="-0.03em"), rx.text("Production Command Center", size="2", color="#dbeafe"), spacing="0"),
                spacing="3", align_items="center",
            ),
            rx.heading("Gestão de produção pronta para uso diário.", size="8", color="white", letter_spacing="-0.03em", line_height="1.15", max_width="620px"),
            rx.text("Acompanhe confecção, compras e projeção em uma interface única, com acesso por perfil e dados por demanda.", color="#dbeafe", size="3", line_height="1.7", max_width="560px"),
            rx.grid(
                *[
                    rx.box(
                        rx.hstack(
                            rx.box(rx.icon(icone, size=16, color="#bfdbfe"), background="rgba(147,197,253,.14)", border="1px solid rgba(147,197,253,.2)", border_radius="10px", padding="0.45rem"),
                            rx.text(txt, color="#f8fafc", size="2"),
                            spacing="3", align_items="center",
                        ),
                        padding="0.85rem", border_radius="12px", background="rgba(255,255,255,.04)", border="1px solid rgba(255,255,255,.08)",
                    ) for icone, txt in recursos
                ],
                columns=rx.breakpoints(initial="1", sm="2"), spacing="3", width="100%",
            ),
            formulario,
            spacing="5", width="100%", max_width="620px", margin="0 auto",
        ),
        width="100%", min_height="100vh", padding=["2rem", "2.5rem", "3rem"],
        background=f"radial-gradient(ellipse at top left,#1e3a5f 0%,{C['primary_dark']} 55%,#0f172a 100%)",
        display="flex", align_items="center", justify_content="center",
    )
