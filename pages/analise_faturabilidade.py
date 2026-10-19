import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import plotly.graph_objects as go

# Configurar página
st.set_page_config(
    page_title="Análise de Faturabilidade",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== FUNÇÕES DE CARREGAMENTO ====================

@st.cache_data
def load_pedidos(file_path):
    """Carrega dados do arquivo Excel com pedidos"""
    try:
        df = pd.read_excel(file_path)
        df['Dt. Agendamento'] = pd.to_datetime(df['Dt. Agendamento'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo de pedidos: {e}")
        return None

@st.cache_data
def load_estoque(file_path):
    """Carrega dados do arquivo Excel com estoque"""
    try:
        df = pd.read_excel(file_path)
        # Garantir que as colunas existem
        required_columns = ['Cód Confec', 'Carteira já Fat', 'Empenhado', 'Estoque']
        if not all(col in df.columns for col in required_columns):
            st.error(f"Arquivo de estoque deve conter as colunas: {', '.join(required_columns)}")
            return None
        return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo de estoque: {e}")
        return None

# ==================== FUNÇÕES DE ANÁLISE ====================

def calcular_faturabilidade(qtd, estoque, carteira_fat, empenhado):
    """
    Determina se é possível faturar baseado na lógica:
    - Se estoque == 0 ou NaN = Não disponível (Sem Estoque)
    - Se qtd > (Estoque - (Carteira já Fat + (-1 * Empenhado))) = Não Faturável
    - Se qtd <= (Estoque - (Carteira já Fat + (-1 * Empenhado))) = Faturável
    - Necessidade = Qtd - Disponível (se Disponível < Qtd; caso contrário, 0)
    
    Args:
        qtd: Quantidade solicitada
        estoque: Quantidade em estoque
        carteira_fat: Carteira já faturada
        empenhado: Quantidade empenhada
    
    Returns:
        tuple: (é_faturável, disponível, consumo_calculado, necessidade)
        Retorna (None, None, None, None) quando estoque é 0 ou inválido
    """
    try:
        # Verificar se estoque é válido e maior que 0
        if pd.isna(estoque) or estoque == 0:
            return None, None, None, None
        
        # Converter para números, tratando NaN como 0
        qtd = float(qtd) if pd.notna(qtd) else 0
        estoque = float(estoque)
        carteira_fat = float(carteira_fat) if pd.notna(carteira_fat) else 0
        empenhado = float(empenhado) if pd.notna(empenhado) else 0
        
        # Calcular disponibilidade real
        consumo_carteira = estoque + empenhado
        disponivel = (consumo_carteira - carteira_fat)
        
        # Garantir que disponível não seja negativo
        disponivel = max(0.0, disponivel)

        # Determinar faturabilidade
        eh_faturavel = qtd <= disponivel
        
        # Calcular necessidade
        necessidade = max(0.0, qtd - disponivel)
        
        return eh_faturavel, disponivel, consumo_carteira, necessidade
    except Exception as e:
        st.warning(f"Erro ao calcular faturabilidade: {e}")
        return None, None, None, None

def mesclar_pedidos_estoque(df_pedidos, df_estoque):
    """
    Mescla dados de pedidos com dados de estoque
    e calcula faturabilidade
    """
    # Criar coluna de lookup no dataframe de pedidos
    df_analise = df_pedidos.copy()
    
    # Inicializar colunas de resultado com tipo object para aceitar None
    df_analise['Cód Confec'] = df_analise['Cód Prod']  # Mapeamento entre colunas
    df_analise['Estoque'] = np.nan
    df_analise['Carteira já Fat'] = np.nan
    df_analise['Empenhado'] = np.nan
    df_analise['Disponível'] = np.nan
    df_analise['Necessidade'] = np.nan
    df_analise['É Faturável'] = None  # Inicializar como None (object type)
    df_analise['Consumo Carteira'] = np.nan
    
    # Mesclar com dados de estoque
    df_estoque_renamed = df_estoque.rename(columns={'Cód Confec': 'Cód Prod'})
    df_analise = df_analise.merge(
        df_estoque_renamed[['Cód Prod', 'Estoque', 'Carteira já Fat', 'Empenhado']],
        on='Cód Prod',
        how='left',
        suffixes=('', '_estoque')
    )
    
    # Usar sufixos para resolver conflitos
    for col in ['Estoque', 'Carteira já Fat', 'Empenhado']:
        if f'{col}_estoque' in df_analise.columns:
            df_analise[col] = df_analise[f'{col}_estoque']
            df_analise.drop(columns=[f'{col}_estoque'], inplace=True)
    
    # Converter colunas para numérico
    for col in ['Estoque', 'Carteira já Fat', 'Empenhado']:
        df_analise[col] = pd.to_numeric(df_analise[col], errors='coerce')
    
    # Calcular faturabilidade para cada linha
    for idx, row in df_analise.iterrows():
        # Verificar se estoque existe e é maior que 0
        if pd.notna(row['Estoque']) and row['Estoque'] > 0:
            eh_faturavel, disponivel, consumo, necessidade = calcular_faturabilidade(
                row['Qtd'],
                row['Estoque'],
                row['Carteira já Fat'],
                row['Empenhado']
            )
            df_analise.at[idx, 'É Faturável'] = eh_faturavel
            df_analise.at[idx, 'Disponível'] = disponivel
            df_analise.at[idx, 'Consumo Carteira'] = consumo
            df_analise.at[idx, 'Necessidade'] = necessidade
        else:
            # Estoque é 0, NaN ou None - manter como None
            df_analise.at[idx, 'É Faturável'] = None
            df_analise.at[idx, 'Disponível'] = None
            df_analise.at[idx, 'Consumo Carteira'] = None
            # Se não tem estoque, a necessidade é a quantidade solicitada
            df_analise.at[idx, 'Necessidade'] = float(row['Qtd']) if pd.notna(row['Qtd']) else 0.0
    
    return df_analise

def get_status_faturabilidade(eh_faturavel):
    """Retorna status e emoji para faturabilidade"""
    if pd.isna(eh_faturavel) or eh_faturavel is None:
        return "⚠️ SEM ESTOQUE"
    elif eh_faturavel:
        return "✅ FATURÁVEL"
    else:
        return "❌ NÃO FATURÁVEL"

def criar_resumo_faturabilidade(df_analise):
    """Cria resumo das análises de faturabilidade"""
    total_pedidos = len(df_analise)
    
    # Contar por status
    faturavel = (df_analise['É Faturável'] == True).sum()
    nao_faturavel = (df_analise['É Faturável'] == False).sum()
    sem_estoque = df_analise['É Faturável'].isna().sum()
    
    return {
        'total': total_pedidos,
        'faturavel': faturavel,
        'nao_faturavel': nao_faturavel,
        'sem_estoque': sem_estoque,
        'percentual_faturavel': (faturavel / max(total_pedidos - sem_estoque, 1)) * 100 if (total_pedidos - sem_estoque) > 0 else 0
    }

def criar_cards_faturabilidade(df_analise):
    """Cria cards com detalhes de faturabilidade agrupados por cliente"""
    clientes = df_analise['Cliente'].unique()
    # Remover NaN e ordenar
    clientes = sorted([c for c in clientes if pd.notna(c)])
    
    for cliente in clientes:
        df_cliente = df_analise[df_analise['Cliente'] == cliente]
        
        st.subheader(f"👤 {cliente}")
        
        cols = st.columns(3)
        for idx, (_, row) in enumerate(df_cliente.iterrows()):
            col_idx = idx % 3
            
            with cols[col_idx]:
                status_text = get_status_faturabilidade(row['É Faturável'])
                
                # Cabeçalho do card
                st.write(f"### Pedido #{int(row['Pedido'])} - {status_text}")
                
                # Informações básicas do pedido
                st.write(f"**📦 Produto:** {row['Produto']}")
                st.write(f"**🔢 Cód:** {row['Cód Prod']}")
                st.write(f"**📅 Data:** {row['Dt. Agendamento'].strftime('%d/%m/%Y') if pd.notna(row['Dt. Agendamento']) else 'N/A'}")
                st.write(f"**👕 Coleção:** {row['Coleção']}")
                st.write(f"**⚙️ Operação:** {row['Operação Produtiva']}")
                st.write(f"**🎯 Segmento:** {row['Segmento']}")
                
                st.divider()
                
                # Análise de estoque
                if pd.notna(row['Estoque']) and row['Estoque'] > 0:
                    estoque_val = int(row['Estoque'])
                    carteira_fat = int(row['Carteira já Fat']) if pd.notna(row['Carteira já Fat']) else 0
                    empenhado = int(row['Empenhado']) if pd.notna(row['Empenhado']) else 0
                    consumo = int(row['Consumo Carteira']) if pd.notna(row['Consumo Carteira']) else 0
                    disponivel = int(row['Disponível']) if pd.notna(row['Disponível']) else 0
                    qtd_solicitada = int(row['Qtd'])
                    necessidade = int(row['Necessidade']) if pd.notna(row['Necessidade']) else 0
                    diferenca = disponivel - qtd_solicitada
                    
                    st.write("#### 📦 ANÁLISE DE ESTOQUE")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Estoque Total", f"{estoque_val:,}")
                        st.metric("Empenhado", f"{empenhado:,}")
                    with col2:
                        st.metric("Carteira Fat", f"{carteira_fat:,}")
                        st.metric("Consumo", f"{consumo:,}")
                    
                    st.divider()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Disponível", f"{disponivel:,}", delta=None)
                    with col2:
                        st.metric("Qtd Solicitada", f"{qtd_solicitada:,}", delta=None)
                    with col3:
                        st.metric("Necessidade", f"{necessidade:,}", delta=None)
                    
                    st.divider()
                    
                    # Diferença com cor
                    if diferenca >= 0:
                        st.success(f"✅ **Diferença:** +{diferenca:,} (Disponível excede a solicitação)")
                    else:
                        st.error(f"❌ **Diferença:** {diferenca:,} (Falta {abs(diferenca):,})")
                else:
                    st.error("⚠️ **Produto com estoque zerado ou não encontrado**")
                    qtd_solicitada = int(row['Qtd'])
                    st.metric("Necessidade", f"{qtd_solicitada:,}", delta=None)
                
                st.divider()
                st.write(f"**💰 Valor Total:** R$ {row['R$ Total']:.2f}")

def criar_tabela_analise(df_analise):
    """Cria tabela detalhada de análise de faturabilidade"""
    df_display = df_analise[[
        'Pedido', 'Cliente', 'Cód Prod', 'Produto', 'Qtd',
        'Estoque', 'Carteira já Fat', 'Empenhado', 'Disponível',
        'Necessidade', 'É Faturável', 'R$ Total', 'Operação Produtiva', 'Segmento', 
        'Coleção', 'Dt. Agendamento'
    ]].copy()
    
    df_display['Dt. Agendamento'] = df_display['Dt. Agendamento'].dt.strftime('%d/%m/%Y')
    df_display['É Faturável'] = df_display['É Faturável'].apply(
        lambda x: '✅ SIM' if x == True else ('❌ NÃO' if x == False else '⚠️ SEM ESTOQUE')
    )
    
    # Formatar valores numéricos
    for col in ['Qtd', 'Estoque', 'Carteira já Fat', 'Empenhado', 'Disponível', 'Necessidade']:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f'{int(x):,}' if pd.notna(x) and x > 0 else '0' if pd.notna(x) else 'N/A')
    
    return df_display.sort_values('Pedido')

def criar_grafico_faturabilidade(df_analise, resumo):
    """Cria gráfico com resumo de faturabilidade"""
    fig = go.Figure(data=[
        go.Bar(
            name='Status',
            x=['Faturável', 'Não Faturável', 'Sem Estoque'],
            y=[resumo['faturavel'], resumo['nao_faturavel'], resumo['sem_estoque']],
            marker=dict(color=['#4caf50', '#f44336', '#ffc107']),
            text=[resumo['faturavel'], resumo['nao_faturavel'], resumo['sem_estoque']],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Resumo de Faturabilidade",
        xaxis_title="Status",
        yaxis_title="Quantidade de Pedidos",
        height=400,
        showlegend=False
    )
    
    return fig

# ==================== INTERFACE PRINCIPAL ====================

st.title("💰 Análise de Faturabilidade")

# Sidebar para carregar arquivos
with st.sidebar:
    st.header("Configurações")
    
    uploaded_pedidos = st.file_uploader(
        "Carregue o arquivo Excel com os pedidos",
        type=['xlsx', 'xls'],
        key='file_pedidos',
        help="Arquivo deve conter: Pedido, Cliente, Cód Prod, Produto, Qtd, R$ Total, etc."
    )
    
    uploaded_estoque = st.file_uploader(
        "Carregue o arquivo Excel com o estoque",
        type=['xlsx', 'xls'],
        key='file_estoque',
        help="Arquivo deve conter: Cód Confec, Carteira já Fat, Empenhado, Estoque"
    )

if uploaded_pedidos and uploaded_estoque:
    df_pedidos = load_pedidos(uploaded_pedidos)
    df_estoque = load_estoque(uploaded_estoque)
    
    if df_pedidos is not None and df_estoque is not None:
        # Mesclar dados
        df_analise = mesclar_pedidos_estoque(df_pedidos, df_estoque)
        
        # Criar resumo
        resumo = criar_resumo_faturabilidade(df_analise)
        
        # Filtros na sidebar
        with st.sidebar:
            st.markdown("---")
            st.subheader("🔍 Filtros")
            
            # Filtro por Faturabilidade
            faturabilidade_filtro = st.multiselect(
                "Faturabilidade",
                options=["Faturável", "Não Faturável", "Sem Estoque"],
                default=["Faturável", "Não Faturável", "Sem Estoque"],
                help="Selecione os status que deseja visualizar"
            )
            
            # Filtro por Cliente
            clientes_unicos = sorted([c for c in df_analise['Cliente'].unique() if pd.notna(c)])
            clientes = st.multiselect(
                "Cliente",
                options=clientes_unicos,
                help="Selecione um ou mais clientes"
            )
            
            # Filtro por Operação
            operacoes_unicas = sorted([o for o in df_analise['Operação Produtiva'].unique() if pd.notna(o)])
            operacoes = st.multiselect(
                "Operação Produtiva",
                options=operacoes_unicas,
                help="Selecione uma ou mais operações"
            )
        
        # Aplicar filtros
        df_filtered = df_analise.copy()
        
        # Filtro de faturabilidade
        mask_faturabilidade = pd.Series([False] * len(df_filtered))
        for status in faturabilidade_filtro:
            if status == "Faturável":
                mask_faturabilidade |= (df_filtered['É Faturável'] == True)
            elif status == "Não Faturável":
                mask_faturabilidade |= (df_filtered['É Faturável'] == False)
            elif status == "Sem Estoque":
                mask_faturabilidade |= (df_filtered['É Faturável'].isna())
        
        df_filtered = df_filtered[mask_faturabilidade]
        
        if clientes:
            df_filtered = df_filtered[df_filtered['Cliente'].isin(clientes)]
        
        if operacoes:
            df_filtered = df_filtered[df_filtered['Operação Produtiva'].isin(operacoes)]
        
        # Exibir métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Pedidos", resumo['total'])
        
        with col2:
            st.metric("✅ Faturável", int(resumo['faturavel']))
        
        with col3:
            st.metric("❌ Não Faturável", int(resumo['nao_faturavel']))
        
        with col4:
            st.metric("⚠️ Sem Estoque", int(resumo['sem_estoque']))
        
        st.divider()
        
        # Gráfico de faturabilidade
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = criar_grafico_faturabilidade(df_analise, resumo)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.metric(
                "% Faturável",
                f"{resumo['percentual_faturavel']:.1f}%"
            )
        
        st.divider()
        
        # Abas de visualização
        tab1, tab2, tab3 = st.tabs(["🎯 Cards por Cliente", "📋 Tabela Detalhada", "📊 Análise por Produto"])
        
        with tab1:
            if not df_filtered.empty:
                criar_cards_faturabilidade(df_filtered)
            else:
                st.warning("Nenhum pedido encontrado com os filtros selecionados.")
        
        with tab2:
            if not df_filtered.empty:
                df_display = criar_tabela_analise(df_filtered)
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download dos dados filtrados
                csv = df_display.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Baixar análise (CSV)",
                    data=csv,
                    file_name=f"analise_faturabilidade_{datetime.now().strftime('%d_%m_%Y')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Nenhum pedido encontrado com os filtros selecionados.")
        
        with tab3:
            if not df_filtered.empty:
                # Análise por produto
                df_produto = df_filtered.groupby('Cód Prod').agg({
                    'Qtd': 'sum',
                    'Estoque': 'first',
                    'Disponível': 'first',
                    'Necessidade': 'sum',
                    'É Faturável': lambda x: (x == True).sum(),
                    'Pedido': 'count'
                }).rename(columns={'Pedido': 'Total de Pedidos', 'É Faturável': 'Pedidos Faturáveis'})
                
                df_produto['% Faturabilidade'] = (
                    df_produto['Pedidos Faturáveis'] / df_produto['Total de Pedidos'] * 100
                ).round(1)
                
                st.dataframe(
                    df_produto.sort_values('Qtd', ascending=False),
                    use_container_width=True
                )
            else:
                st.warning("Nenhum pedido encontrado com os filtros selecionados.")

else:
    st.info("👆 Por favor, carregue ambos os arquivos para começar.")
    st.markdown("""
        ### 📝 Formato esperado dos arquivos Excel:
        
        #### Arquivo de Pedidos:
        - **Pedido** - Identificador único do pedido
        - **Cliente** - Nome do cliente
        - **Cód Prod** - Código do produto
        - **Produto** - Nome do produto
        - **Qtd** - Quantidade solicitada
        - **R$ Total** - Valor total do pedido
        - **Operação Produtiva** - Tipo de operação
        - **Segmento** - Segmento de mercado
        - **Coleção** - Coleção do produto
        - **Dt. Agendamento** - Data do agendamento (formato: DD/MM/YYYY)
        
        #### Arquivo de Estoque:
        - **Cód Confec** - Código do produto (mesmo formato de Cód Prod)
        - **Carteira já Fat** - Quantidade já faturada
        - **Empenhado** - Quantidade empenhada
        - **Estoque** - Quantidade total em estoque
        
        ### 📊 Como a faturabilidade é determinada:
        
        **Lógica:**
        - Se Estoque = 0 → ⚠️ **SEM ESTOQUE** (Necessidade = Qtd)
        - Disponível = Estoque - (Carteira já Fat - Empenhado)
        - Se Qtd ≤ Disponível → ✅ **FATURÁVEL** (Necessidade = 0)
        - Se Qtd > Disponível → ❌ **NÃO FATURÁVEL** (Necessidade = Qtd - Disponível)
        - Se Produto não está no estoque → ⚠️ **SEM ESTOQUE** (Necessidade = Qtd)
    """)
