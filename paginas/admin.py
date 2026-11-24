"""
Administração do Visualfil Cloud
---------------------------------
Usuários, permissões por página, demandas (nome/fonte) e atualização dos XLSX.
Somente administradores.
"""
import io
import re
from datetime import date

import pandas as pd
import streamlit as st

import nuvem as cloud
from nucleo import aplicar_estilo_comum, fmt_num

st.set_page_config(page_title="Administração — Visualfil", page_icon="⚙️", layout="wide")
aplicar_estilo_comum()

if not cloud.logado():
    st.warning("Faça login em **🔐 Entrar** para acessar esta página.")
    st.stop()
if not cloud.eh_admin():
    st.error("Acesso restrito a administradores.")
    st.stop()

st.title("⚙️ Administração do Visualfil Cloud")

aba_usuarios,aba_perms,aba_demandas,aba_catalogo = st.tabs(
    ["👥 Usuários", "🔑 Permissões", "📁 Demandas e XLSX", "🏭 Catálogo por confecção"]
)

# ============================== USUÁRIOS ==============================
with aba_usuarios:
    st.markdown("### Usuários cadastrados")
    try:
        lista = cloud.usuarios()
    except Exception as erro:
        st.error(f"Erro ao listar usuários: {erro}")
        lista = []
    if lista:
        st.dataframe(
            pd.DataFrame(lista)[["usuario", "nome", "admin", "ativo"]],
            width="stretch", hide_index=True,
        )
    else:
        st.info("Nenhum usuário cadastrado.")

    with st.expander("➕ Novo usuário / editar senha", expanded=False):
        with st.form("form_usuario"):
            c1, c2 = st.columns(2)
            with c1:
                usu = st.text_input("Usuário (login)").strip().lower()
                nome = st.text_input("Nome")
            with c2:
                senha = st.text_input("Senha", type="password")
                admin = st.checkbox("Administrador")
                ativo = st.checkbox("Ativo", value=True)
            if st.form_submit_button("Salvar usuário"):
                if not usu or not senha:
                    st.error("Informe usuário e senha.")
                else:
                    try:
                        r = cloud.salvar_usuario(usu, nome or usu, senha, admin, ativo)
                        if r.get("ok"):
                            st.success(f"Usuário {usu} salvo.")
                            st.rerun()
                        else:
                            st.error(r.get("erro", "Erro ao salvar."))
                    except Exception as erro:
                        st.error(str(erro))

# ============================== PERMISSÕES ==============================
with aba_perms:
    st.markdown("### Permissões por página")
    st.caption(
        "**Visualização** → pode ver; **Total** → pode operar/exportar; "
        "**Restrito** → sem acesso. Administradores têm acesso total."
    )
    try:
        perms = cloud.todas_permissoes()
        usuarios = cloud.usuarios()
    except Exception as erro:
        st.error(f"Erro ao carregar permissões: {erro}")
        perms, usuarios = [], []

    mapa_perms = {
        (str(p.get("usuario", "")).lower(), str(p.get("pagina", ""))): str(p.get("nivel", "visualizacao")).lower()
        for p in perms
    }
    usuarios_norm = [str(u.get("usuario", "")).lower() for u in usuarios if u.get("usuario")]

    if not usuarios_norm:
        st.info("Cadastre usuários antes de definir permissões.")
    else:
        usuario_sel = st.selectbox("Usuário", usuarios_norm)
        mudancas = []
        for pagina in cloud.PAGINAS:
            atual = mapa_perms.get((usuario_sel, pagina), "restrito")
            nivel = st.radio(
                pagina,
                options=cloud.NIVEIS,
                index=cloud.NIVEIS.index(atual) if atual in cloud.NIVEIS else 2,
                key=f"perm_{usuario_sel}_{pagina}",
                horizontal=True,
            )
            if nivel != atual:
                mudancas.append((pagina, nivel))
        if st.button("💾 Salvar permissões", type="primary"):
            erros = []
            for pagina, nivel in mudancas:
                try:
                    r = cloud.salvar_permissao(usuario_sel, pagina, nivel)
                    if not r.get("ok"):
                        erros.append(r.get("erro", pagina))
                except Exception as erro:
                    erros.append(str(erro))
            if erros:
                st.error("Erros: " + "; ".join(erros))
            else:
                st.session_state.pop("vf_permissoes_cache", None)
                st.success("Permissões salvas.")
                st.rerun()

# ============================== DEMANDAS ==============================
with aba_demandas:
    st.markdown("### Demandas (nome e fonte/remessa)")
    try:
        demandas = cloud.demandas()
    except Exception as erro:
        st.error(f"Erro ao listar demandas: {erro}")
        demandas = []
    if demandas:
        st.dataframe(pd.DataFrame(demandas), width="stretch", hide_index=True)
    else:
        st.info("Nenhuma demanda cadastrada.")

    with st.expander("➕ Nova demanda / editar", expanded=False):
        with st.form("form_demanda"):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome da demanda")
            with c2:
                fonte = st.text_input("Fonte (Remessa)")
            if st.form_submit_button("Salvar demanda"):
                if not nome.strip():
                    st.error("Informe o nome da demanda.")
                else:
                    r = cloud.salvar_demanda("", nome.strip(), fonte.strip())
                    if r.get("ok"):
                        st.success("Demanda criada.")
                        st.rerun()
                    else:
                        st.error(r.get("erro", "Erro ao salvar."))

    st.markdown("### 📤 Enviar / atualizar XLSX de uma demanda")
    if demandas:
        opcoes = {f"{d.get('nome')}  (fonte: {d.get('fonte') or '—'})": d.get("id") for d in demandas}
        escolha = st.selectbox("Demanda", list(opcoes))
        did = opcoes[escolha]
        try:
            arquivos = {a.get("nome"): a for a in cloud.listar_arquivos(did)}
        except Exception:
            arquivos = {}
        for tipo in ("pedidos", "estoque", "producao", "projecao"):
            info = arquivos.get(f"{tipo}.xlsx")
            st.caption(
                f"**{tipo}** — "
                + (f"enviado em {info.get('atualizado_em', '')[:10]} ({fmt_num(info.get('tamanho', 0))} bytes)"
                   if info else "não enviado")
            )
        tipos = st.multiselect("Atualizar arquivos", ["pedidos", "estoque", "producao", "projecao"])
        uplods = {}
        cols = st.columns(len(tipos) or 1)
        for col, tipo in zip(cols, tipos):
            with col:
                uplods[tipo] = st.file_uploader(f"{tipo}.xlsx", type=["xlsx", "xls"], key=f"up_{did}_{tipo}")
        if st.button("⬆️ Enviar arquivos", type="primary"):
            erros = []
            for tipo, arquivo in uplods.items():
                if arquivo is None:
                    continue
                try:
                    r = cloud.salvar_arquivo(did, tipo, arquivo.getvalue())
                    if not r.get("ok"):
                        erros.append(f"{tipo}: {r.get('erro')}")
                except Exception as erro:
                    erros.append(f"{tipo}: {erro}")
            if erros:
                st.error("; ".join(erros))
            else:
                st.success("Arquivos enviados/atualizados.")
                st.rerun()
        if st.button("🗑️ Excluir demanda", type="secondary"):
            cloud.excluir_demanda(did)
            st.warning("Demanda excluída.")
            st.rerun()

# ============================== CATÁLOGO ==============================
with aba_catalogo:
    st.markdown("### Itens confeccionados por confecção")
    st.caption(
        "Cadastre aqui a listagem de itens já produzidos por cada confecção "
        "(mesma ideia da aba **Por Confecção** da Projeção por Confecção). "
        "Ela alimenta a compra sugerida e a análise online."
    )
    try:
        cat = cloud.catalogo()
    except Exception as erro:
        st.error(f"Erro ao carregar catálogo: {erro}")
        cat = []
    if cat:
        st.dataframe(pd.DataFrame(cat), width="stretch", hide_index=True, height=320)

    st.markdown("#### Importar planilha de itens confeccionados")
    st.caption("Colunas usadas: Confecção/Fornecedor, Cód Confec/Código, Confeccionado/Item, Tipo Confec./Tipo, Medida, Marca.")
    uploaded = st.file_uploader("Planilha de itens (.xlsx)", type=["xlsx", "xls"], key="up_catalogo")
    if uploaded is not None:
        try:
            bruto = pd.read_excel(io.BytesIO(uploaded.getvalue()))
            bruto.columns = [str(c).strip() for c in bruto.columns]
            def achar(*nomes):
                for n in nomes:
                    for c in bruto.columns:
                        if c.strip().lower() == n.strip().lower():
                            return c
                return None
            c_conf = achar("Confecção", "Fornecedor", "Confeccao")
            c_cod = achar("Cód Confec", "Código", "Cod Confec")
            c_item = achar("Confeccionado", "Item", "Produto")
            c_tipo = achar("Tipo Confec.", "Tipo", "Tipo do Confeccionado")
            c_tam = achar("Medida", "Tamanho")
            c_marca = achar("Marca")
            if c_cod is None:
                st.error("Não encontrei a coluna de código (Cód Confec / Código).")
            else:
                itens = []
                for _, row in bruto.iterrows():
                    cod = str(row[c_cod]).strip()
                    if cod in ("", "nan", "None"):
                        continue
                    itens.append({
                        "confeccao": str(row[c_conf]).strip() if c_conf else "",
                        "codigo": cod,
                        "item": str(row[c_item]).strip() if c_item else "",
                        "tipo": str(row[c_tipo]).strip() if c_tipo else "",
                        "tamanho": str(row[c_tam]).strip() if c_tam else "",
                        "marca": str(row[c_marca]).strip() if c_marca else "",
                    })
                st.caption(f"{len(itens)} itens reconhecidos.")
                if st.button("💾 Salvar catálogo", type="primary"):
                    r = cloud.salvar_catalogo(itens)
                    if r.get("ok"):
                        st.success(f"{r.get('salvos', len(itens))} itens salvos.")
                        st.rerun()
                    else:
                        st.error(r.get("erro", "Erro ao salvar."))
        except Exception as erro:
            st.error(f"Erro ao ler planilha: {erro}")

    with st.expander("➕ Adicionar item manualmente", expanded=False):
        with st.form("form_catalogo"):
            c1, c2 = st.columns(2)
            with c1:
                conf = st.text_input("Confecção")
                cod = st.text_input("Código")
            with c2:
                item = st.text_input("Item")
                tipo = st.text_input("Tipo")
            marca = st.text_input("Marca")
            if st.form_submit_button("Adicionar"):
                if not cod.strip():
                    st.error("Informe o código.")
                else:
                    r = cloud.salvar_catalogo([{
                        "confeccao": conf.strip(), "codigo": cod.strip(),
                        "item": item.strip(), "tipo": tipo.strip(),
                        "tamanho": "", "marca": marca.strip(),
                    }])
                    if r.get("ok"):
                        st.success("Item salvo.")
                        st.rerun()
                    else:
                        st.error(r.get("erro", "Erro ao salvar."))
