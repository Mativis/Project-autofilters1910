import streamlit as st
import pandas as pd
import io
import numpy as np
from datetime import datetime
import calendar
from collections import defaultdict

# Configuração da página
st.set_page_config(
    page_title="Ferramenta de Gestão de Confecção",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CSS PERSONALIZADO - DESIGN MODERNO ====================
st.markdown("""
    <style>
        /* Variáveis de cores */
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #4caf50;
            --warning: #ff9800;
            --danger: #f44336;
            --light: #f8f9fa;
            --dark: #333;
        }
        
        /* Reset e Base */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        /* Main container */
        .main {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
        }
        
        /* Header Principal - Moderno */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem 2.5rem;
            border-radius: 15px;
            margin-bottom: 2.5rem;
            color: white;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .main-header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 300px;
            height: 300px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
        }
        
        .main-header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 800;
            position: relative;
            z-index: 1;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .main-header p {
            margin: 0.8rem 0 0 0;
            opacity: 0.95;
            font-size: 1.1rem;
            position: relative;
            z-index: 1;
            font-weight: 300;
        }
        
        /* Navegação - Menu Moderno */
        .nav-container {
            background: white;
            border-radius: 12px;
            padding: 0.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .nav-button {
            flex: 1;
            min-width: 150px;
            padding: 0.8rem 1.5rem;
            border: 2px solid #e0e0e0;
            background: white;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 1rem;
        }
        
        .nav-button:hover {
            border-color: #667eea;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
            transform: translateY(-2px);
        }
        
        .nav-button.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: #667eea;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        /* Cards de Pedido - Redesenhado */
        .order-card-container {
            background: white;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
            transition: all 0.3s ease;
            border-left: 5px solid #667eea;
        }
        
        .order-card-container:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        }
        
        .order-card-container.prioridade {
            border-left-color: #f44336;
            background: linear-gradient(90deg, rgba(244, 67, 54, 0.02) 0%, white 100%);
        }
        
        .order-card-container.atencao {
            border-left-color: #ff9800;
            background: linear-gradient(90deg, rgba(255, 152, 0, 0.02) 0%, white 100%);
        }
        
        .order-card-container.ok {
            border-left-color: #4caf50;
            background: linear-gradient(90deg, rgba(76, 175, 80, 0.02) 0%, white 100%);
        }
        
        /* Header do Card de Pedido */
        .order-card-header {
            padding: 1.2rem;
            background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .order-card-title {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            flex: 1;
            min-width: 250px;
        }
        
        .order-number {
            font-size: 1.3rem;
            font-weight: 800;
            color: #667eea;
        }
        
        .order-info-text {
            font-size: 0.85rem;
            color: #666;
        }
        
        .order-card-stats {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .stat-badge {
            background: white;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid #e0e0e0;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }
        
        .stat-badge.prioridade {
            background: #ffebee;
            border-color: #f44336;
            color: #f44336;
        }
        
        .stat-badge.atencao {
            background: #fff3e0;
            border-color: #ff9800;
            color: #ff9800;
        }
        
        .stat-badge.ok {
            background: #e8f5e9;
            border-color: #4caf50;
            color: #4caf50;
        }
        
        /* Detalhes do Pedido - Por Código */
        .order-card-content {
            padding: 1.2rem;
        }
        
        .code-detail-item {
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 0.8rem;
            transition: all 0.2s ease;
        }
        
        .code-detail-item:hover {
            border-color: #667eea;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.02) 0%, white 100%);
        }
        
        .code-detail-item.prioridade {
            border-left: 4px solid #f44336;
        }
        
        .code-detail-item.atencao {
            border-left: 4px solid #ff9800;
        }
        
        .code-detail-item.ok {
            border-left: 4px solid #4caf50;
        }
        
        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.8rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .code-number {
            font-weight: 700;
            font-size: 1.1rem;
            color: #333;
        }
        
        .code-product {
            font-size: 0.9rem;
            color: #666;
            margin: 0.5rem 0;
        }
        
        .code-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 0.8rem;
            margin: 0.8rem 0;
        }
        
        .metric-item {
            background: #f8f9fa;
            padding: 0.6rem;
            border-radius: 8px;
            text-align: center;
            font-size: 0.85rem;
        }
        
        .metric-item-label {
            display: block;
            font-size: 0.75rem;
            color: #999;
            margin-bottom: 0.3rem;
        }
        
        .metric-item-value {
            display: block;
            font-weight: 700;
            color: #333;
            font-size: 1rem;
        }
        
        /* Progress Bar Moderno */
        .progress-container {
            margin: 0.8rem 0;
        }
        
        .progress-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            margin-bottom: 0.4rem;
            color: #666;
        }
        
        .progress-bar {
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            height: 8px;
            position: relative;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }
        
        /* Status Badge */
        .status-badge {
            display: inline-block;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.8rem;
            margin-top: 0.5rem;
        }
        
        .status-badge.prioridade {
            background-color: #f44336;
            color: white;
        }
        
        .status-badge.atencao {
            background-color: #ff9800;
            color: white;
        }
        
        .status-badge.ok {
            background-color: #4caf50;
            color: white;
        }

        /* Calendário */
        .calendar-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 10px 10px 0 0;
            text-align: center;
            font-weight: 600;
        }
        
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 0.5rem;
            padding: 1rem;
            background: white;
            border-radius: 0 0 10px 10px;
        }
        
        .calendar-day-header {
            text-align: center;
            font-weight: 600;
            color: #667eea;
            padding: 0.5rem;
            font-size: 0.9rem;
        }
        
        .calendar-day {
            aspect-ratio: 1;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 0.5rem;
            text-align: center;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            background: #fafafa;
        }
        
        .calendar-day:hover {
            background: #f0f0f0;
            border-color: #667eea;
        }
        
        .calendar-day.has-events {
            background: white;
            border: 2px solid #667eea;
            font-weight: 600;
        }
        
        .calendar-day.has-events.prioridade {
            border-color: #f44336;
            background: #ffebee;
        }
        
        .calendar-day.has-events.atencao {
            border-color: #ff9800;
            background: #fff3e0;
        }
        
        .calendar-day.has-events.ok {
            border-color: #4caf50;
            background: #e8f5e9;
        }
        
        .calendar-day.empty {
            background: transparent;
            border: none;
            cursor: default;
        }
        
        /* Métricas Gerais */
        .metrics-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            border-top: 4px solid #667eea;
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        }
        
        .metric-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: #667eea;
            margin: 0.5rem 0;
        }
        
        .metric-label {
            font-size: 0.95rem;
            color: #999;
            font-weight: 600;
        }
        
        /* Sidebar Moderno */
        .sidebar-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            text-align: center;
        }
        
        .sidebar-header h2 {
            margin: 0;
            font-size: 1.3rem;
        }
        
        /* Filtros */
        .filter-section {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        
        .filter-section h3 {
            color: #333;
            font-size: 0.95rem;
            margin-bottom: 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* Abas Personalizadas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: transparent;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 0.8rem 1.5rem;
            font-weight: 600;
            border-bottom: 3px solid transparent;
            color: #666;
        }
        
        .stTabs [aria-selected="true"] {
            background: transparent;
            color: #667eea;
            border-bottom: 3px solid #667eea;
        }
        
        /* Botões */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.2rem !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
        }
        
        /* Tabelas */
        .dataframe {
            border-radius: 10px !important;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
        }
        
        /* Info Box */
        .info-box {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #2196f3;
            margin: 1rem 0;
        }
        
        /* Warning Box - Desconsideração */
        .warning-box {
            background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #ff9800;
            margin: 1rem 0;
        }
        
        /* Responsivo */
        @media (max-width: 768px) {
            .main-header h1 {
                font-size: 1.8rem;
            }
            
            .main-header {
                padding: 1.5rem;
            }
            
            .order-card-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .code-metrics {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .metrics-container {
                grid-template-columns: 1fr;
            }
            
            .calendar-grid {
                grid-template-columns: repeat(7, 1fr);
                gap: 0.25rem;
                padding: 0.5rem;
            }
            
            .calendar-day {
                font-size: 0.75rem;
                padding: 0.25rem;
            }
        }
    </style>
""", unsafe_allow_html=True)

# ==================== FUNÇÕES AUXILIARES ====================
def safe_str(value):
    """Converte qualquer valor para string de forma segura"""
    if pd.isna(value):
        return ""
    if isinstance(value, (np.int64, np.int32, np.float64, np.float32)):
        return str(int(value)) if value == int(value) else str(value)
    return str(value)

def safe_hash(*args):
    """Gera hash seguro"""
    str_args = [safe_str(arg) for arg in args]
    combined = "_".join(str_args)
    return combined.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_").replace(":", "_")

def get_status(qtd, saldo_atual, saldo_calculado):
    """Determina o status do pedido"""
    try:
        qtd = float(qtd) if pd.notna(qtd) else 0
        saldo_atual = float(saldo_atual) if pd.notna(saldo_atual) else 0
        saldo_calculado = float(saldo_calculado) if pd.notna(saldo_calculado) else 0
        
        if saldo_calculado == 0:
            return "PRIORIDADE", "prioridade", 3
        elif qtd > saldo_calculado > 0:
            return "ATENÇÃO", "atencao", 2
        else:
            return "OK", "ok", 1
    except:
        return "OK", "ok", 1

def get_order_status(pedido_df):
    """Retorna o status mais alto do pedido"""
    if 'Status' not in pedido_df.columns or len(pedido_df) == 0:
        return "OK", "ok", 1
    
    status_priority = {"PRIORIDADE": 3, "ATENÇÃO": 2, "OK": 1}
    pedido_df['Status_priority'] = pedido_df['Status'].map(status_priority).fillna(1)
    max_priority = pedido_df['Status_priority'].max()
    
    for status, priority in status_priority.items():
        if priority == max_priority:
            if status == "PRIORIDADE":
                return "PRIORIDADE", "prioridade", 3
            elif status == "ATENÇÃO":
                return "ATENÇÃO", "atencao", 2
            else:
                return "OK", "ok", 1
    return "OK", "ok", 1

def filter_by_qtd_ret_percent(df, qtd_col='Qtd', qtd_ret_col='Qtd Ret', threshold=95):
    """Filtra linhas onde Qtd Ret é menor que threshold% da Qtd"""
    if qtd_col not in df.columns or qtd_ret_col not in df.columns:
        return df, 0
    
    df_filtered = df.copy()
    
    df_filtered[qtd_col] = pd.to_numeric(df_filtered[qtd_col], errors='coerce').fillna(0)
    df_filtered[qtd_ret_col] = pd.to_numeric(df_filtered[qtd_ret_col], errors='coerce').fillna(0)
    
    mask = df_filtered[qtd_col] > 0
    df_filtered['percentual_ret'] = 0.0
    df_filtered.loc[mask, 'percentual_ret'] = (df_filtered.loc[mask, qtd_ret_col] / df_filtered.loc[mask, qtd_col]) * 100
    
    linhas_antes = len(df_filtered)
    df_filtered = df_filtered[df_filtered['percentual_ret'] < threshold]
    linhas_removidas = linhas_antes - len(df_filtered)
    
    df_filtered = df_filtered.drop(columns=['percentual_ret'])
    
    return df_filtered, linhas_removidas

def validate_default_options(options, defaults):
    """Valida se os valores padrão existem nas opções"""
    if not defaults:
        return []
    if not options:
        return []
    return [d for d in defaults if d in options]

def calcular_necessidade(row):
    """
    Calcula a necessidade baseado no Saldo 1 e Saldo
    Necessidade = (Saldo 1 * -1.10) com limite máximo do Saldo
    """
    try:
        saldo_1 = float(row.get('Saldo 1', 0)) if pd.notna(row.get('Saldo 1', 0)) else 0
        saldo = float(row.get('Saldo', 0)) if pd.notna(row.get('Saldo', 0)) else 0
        
        # Calcular necessidade base
        necessidade_base = saldo_1 * -1.10
        
        # Aplicar limite: necessidade deve ser igual ou menor que o valor de Saldo
        # Como necessidade é negativa, "menor" significa mais negativa
        if necessidade_base < -saldo:
            necessidade = -saldo
        else:
            necessidade = necessidade_base
            
        return necessidade
    except:
        return 0

# ==================== FUNÇÃO DE TABELA DE DETALHES ====================
def show_detail_table(df_detalhes, title="📋 Detalhamento dos Pedidos", filter_info=None):
    """Exibe tabela detalhada com formatação profissional"""
    
    if df_detalhes.empty:
        st.info("Nenhum pedido encontrado para exibir.")
        return
    
    st.markdown(f"""
        <div style="background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
            <h3 style="color: #333; margin-bottom: 1rem; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">{title}</h3>
    """, unsafe_allow_html=True)
    
    if filter_info:
        st.markdown(f'<div class="info-box">🔍 {filter_info}</div>', unsafe_allow_html=True)
    
    display_cols = []
    column_config = {}
    
    if 'Pedido' in df_detalhes.columns:
        display_cols.append('Pedido')
        column_config['Pedido'] = st.column_config.TextColumn("Pedido", width="small")
    
    if 'Cliente' in df_detalhes.columns:
        display_cols.append('Cliente')
        column_config['Cliente'] = st.column_config.TextColumn("Cliente", width="medium")
    
    if 'Produto' in df_detalhes.columns:
        display_cols.append('Produto')
        column_config['Produto'] = st.column_config.TextColumn("Produto", width="large")
    
    if 'Cód Prod' in df_detalhes.columns:
        display_cols.append('Cód Prod')
        column_config['Cód Prod'] = st.column_config.TextColumn("Código", width="small")
    
    if 'Qtd' in df_detalhes.columns:
        display_cols.append('Qtd')
        column_config['Qtd'] = st.column_config.NumberColumn("Quantidade", format="%d")
    
    if 'Qtd Ret' in df_detalhes.columns:
        display_cols.append('Qtd Ret')
        column_config['Qtd Ret'] = st.column_config.NumberColumn("Qtd Retorno", format="%d")
    
    if 'Saldo Atual' in df_detalhes.columns:
        display_cols.append('Saldo Atual')
        column_config['Saldo Atual'] = st.column_config.NumberColumn("Saldo Atual", format="%d")
    
    if 'Saldo Calc.' in df_detalhes.columns:
        display_cols.append('Saldo Calc.')
        column_config['Saldo Calc.'] = st.column_config.NumberColumn("Saldo Projetado", format="%d")
    
    if 'R$ Total Calc.' in df_detalhes.columns:
        display_cols.append('R$ Total Calc.')
        column_config['R$ Total Calc.'] = st.column_config.NumberColumn("Valor Total", format="R$ %.2f")
    
    if 'Dt Emissão' in df_detalhes.columns:
        display_cols.append('Dt Emissão')
        column_config['Dt Emissão'] = st.column_config.DateColumn("Data Emissão", format="DD/MM/YYYY")
    
    if 'Dt Entrega' in df_detalhes.columns:
        display_cols.append('Dt Entrega')
        column_config['Dt Entrega'] = st.column_config.DateColumn("Data Entrega", format="DD/MM/YYYY")
    
    if 'Operação Produtiva' in df_detalhes.columns:
        display_cols.append('Operação Produtiva')
        column_config['Operação Produtiva'] = st.column_config.TextColumn("Operação", width="small")
    
    if 'Segmento' in df_detalhes.columns:
        display_cols.append('Segmento')
        column_config['Segmento'] = st.column_config.TextColumn("Segmento", width="small")
    
    if 'Coleção' in df_detalhes.columns:
        display_cols.append('Coleção')
        column_config['Coleção'] = st.column_config.TextColumn("Coleção", width="small")
    
    if 'Dt. Agendamento' in df_detalhes.columns:
        display_cols.append('Dt. Agendamento')
        column_config['Dt. Agendamento'] = st.column_config.DateColumn("Data Agendamento", format="DD/MM/YYYY")
    
    if 'Status' in df_detalhes.columns:
        display_cols.append('Status')
        column_config['Status'] = st.column_config.TextColumn("Status", width="small")
    
    df_display = df_detalhes[display_cols].copy()
    
    if 'Dt. Agendamento' in df_display.columns:
        df_display['Dt. Agendamento'] = pd.to_datetime(df_display['Dt. Agendamento'], errors='coerce')
    
    if 'Dt Emissão' in df_display.columns:
        df_display['Dt Emissão'] = pd.to_datetime(df_display['Dt Emissão'], errors='coerce')
    
    if 'Dt Entrega' in df_display.columns:
        df_display['Dt Entrega'] = pd.to_datetime(df_display['Dt Entrega'], errors='coerce')
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )
    
    st.markdown(f"""
        <div style="margin-top: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; display: flex; gap: 2rem; flex-wrap: wrap; font-size: 0.95rem;">
            <span>📊 Total de registros: <b>{len(df_detalhes)}</b></span>
    """, unsafe_allow_html=True)
    
    if 'Status' in df_detalhes.columns:
        prioridades = len(df_detalhes[df_detalhes['Status'] == 'PRIORIDADE'])
        atencoes = len(df_detalhes[df_detalhes['Status'] == 'ATENÇÃO'])
        oks = len(df_detalhes[df_detalhes['Status'] == 'OK'])
        st.markdown(f"""
            <span>🔴 Prioridades: <b>{prioridades}</b></span>
            <span>🟠 Atenções: <b>{atencoes}</b></span>
            <span>🟢 OK: <b>{oks}</b></span>
        """, unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)

# ==================== FUNÇÃO: CARDS POR PEDIDO ====================
def create_order_cards(df_filtered, status_filter=None):
    """Cria cards de pedidos agrupados com detalhes por código"""
    
    if 'Pedido' not in df_filtered.columns:
        st.warning("Coluna 'Pedido' não encontrada no arquivo.")
        return
    
    df_filtered = df_filtered.copy()
    df_filtered['Pedido_str'] = df_filtered['Pedido'].fillna("Desconhecido").astype(str)
    
    if 'Status' not in df_filtered.columns:
        df_filtered['Status'] = df_filtered.apply(
            lambda row: get_status(row.get('Qtd', 0), row.get('Saldo Atual', 0), row.get('Saldo Calc.', 0))[0],
            axis=1
        )
    
    # Agrupar por pedido
    pedidos_data = []
    pedidos = sorted(df_filtered['Pedido_str'].unique(), key=str)
    
    for pedido in pedidos:
        df_pedido = df_filtered[df_filtered['Pedido_str'] == pedido].copy()
        
        total_codigos = len(df_pedido)
        total_prioridade = len(df_pedido[df_pedido['Status'] == 'PRIORIDADE']) if 'Status' in df_pedido.columns else 0
        total_atencao = len(df_pedido[df_pedido['Status'] == 'ATENÇÃO']) if 'Status' in df_pedido.columns else 0
        total_ok = len(df_pedido[df_pedido['Status'] == 'OK']) if 'Status' in df_pedido.columns else 0
        
        pedido_status_text, pedido_status_class, pedido_priority = get_order_status(df_pedido)
        
        if status_filter:
            if status_filter == "PRIORIDADE" and pedido_priority != 3:
                continue
            elif status_filter == "ATENÇÃO" and pedido_priority != 2:
                continue
            elif status_filter == "OK" and pedido_priority != 1:
                continue
        
        cliente = df_pedido['Cliente'].iloc[0] if 'Cliente' in df_pedido.columns else "N/A"
        data_agendamento = df_pedido['Dt. Agendamento'].iloc[0] if 'Dt. Agendamento' in df_pedido.columns else None
        
        try:
            valor_total = df_pedido['R$ Total Calc.'].sum() if 'R$ Total Calc.' in df_pedido.columns else 0
        except:
            valor_total = 0
        
        pedidos_data.append({
            'pedido': pedido,
            'df_pedido': df_pedido,
            'cliente': cliente,
            'total_codigos': total_codigos,
            'total_prioridade': total_prioridade,
            'total_atencao': total_atencao,
            'total_ok': total_ok,
            'pedido_status_text': pedido_status_text,
            'pedido_status_class': pedido_status_class,
            'data_agendamento': data_agendamento,
            'valor_total': valor_total
        })
    
    if 'expanded_orders' not in st.session_state:
        st.session_state.expanded_orders = {}
    if 'selected_order_for_table' not in st.session_state:
        st.session_state.selected_order_for_table = None
    
    # Renderizar cards
    for order_data in pedidos_data:
        pedido = order_data['pedido']
        df_pedido = order_data['df_pedido']
        cliente = order_data['cliente']
        total_codigos = order_data['total_codigos']
        total_prioridade = order_data['total_prioridade']
        total_atencao = order_data['total_atencao']
        total_ok = order_data['total_ok']
        pedido_status_text = order_data['pedido_status_text']
        pedido_status_class = order_data['pedido_status_class']
        data_agendamento = order_data['data_agendamento']
        valor_total = order_data['valor_total']
        
        order_key = safe_hash("order", pedido)
        is_expanded = st.session_state.expanded_orders.get(order_key, False)
        
        # Card do Pedido
        st.markdown(f"""
            <div class="order-card-container {pedido_status_class}">
                <div class="order-card-header">
                    <div class="order-card-title">
                        <span class="order-number">#{pedido}</span>
                        <div>
                            <div class="order-info-text">Cliente: <strong>{cliente}</strong></div>
                            <div class="order-info-text">Códigos: <strong>{total_codigos}</strong></div>
                        </div>
                    </div>
                    <div class="order-card-stats">
                        <div class="stat-badge {pedido_status_class}">{pedido_status_text}</div>
                        <div class="stat-badge">🔴 {total_prioridade}</div>
                        <div class="stat-badge">🟠 {total_atencao}</div>
                        <div class="stat-badge">🟢 {total_ok}</div>
                        <div class="stat-badge">💰 R$ {valor_total:,.2f}</div>
                    </div>
                </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            button_label = "📂 Ver Códigos" if not is_expanded else "📁 Fechar"
            if st.button(button_label, key=f"btn_{order_key}", use_container_width=True):
                st.session_state.expanded_orders[order_key] = not is_expanded
                st.rerun()
        
        with col2:
            if st.button(f"📋 Ver Tabela", key=f"table_{order_key}", use_container_width=True):
                st.session_state.selected_order_for_table = pedido
                st.rerun()
        
        if is_expanded:
            st.markdown('<div class="order-card-content">', unsafe_allow_html=True)
            
            if len(df_pedido) == 0:
                st.info("Nenhum código encontrado para este pedido.")
            else:
                for idx, (_, row) in enumerate(df_pedido.iterrows()):
                    codigo = safe_str(row.get('Cód Prod', 'N/A'))
                    produto = row.get('Produto', 'N/A')
                    
                    try:
                        qtd = float(row.get('Qtd', 0)) if pd.notna(row.get('Qtd')) else 0
                        saldo_atual = float(row.get('Saldo Atual', 0)) if pd.notna(row.get('Saldo Atual')) else 0
                        saldo_calc = float(row.get('Saldo Calc.', 0)) if pd.notna(row.get('Saldo Calc.')) else 0
                    except:
                        qtd = 0
                        saldo_atual = 0
                        saldo_calc = 0
                    
                    status_text, status_class, _ = get_status(qtd, saldo_atual, saldo_calc)
                    
                    percent_estoque = (saldo_atual / qtd * 100) if qtd > 0 else 0
                    estoque_color = "#f44336" if percent_estoque < 30 else "#ff9800" if percent_estoque < 70 else "#4caf50"
                    
                    valor_str = "N/A"
                    if 'R$ Total Calc.' in row and pd.notna(row['R$ Total Calc.']):
                        try:
                            valor = float(row['R$ Total Calc.'])
                            valor_str = f"R$ {valor:,.2f}"
                        except:
                            valor_str = str(row['R$ Total Calc.'])
                    
                    st.markdown(f"""
                        <div class="code-detail-item {status_class}">
                            <div class="code-header">
                                <span class="code-number">📦 Código: {codigo}</span>
                                <span class="status-badge {status_class}">{status_text}</span>
                            </div>
                            <div class="code-product">{safe_str(produto)[:80]}</div>
                            <div class="code-metrics">
                                <div class="metric-item">
                                    <span class="metric-item-label">Qtd</span>
                                    <span class="metric-item-value">{qtd:,.0f}</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-item-label">Saldo Atual</span>
                                    <span class="metric-item-value">{saldo_atual:,.0f}</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-item-label">Saldo Calc.</span>
                                    <span class="metric-item-value">{saldo_calc:,.0f}</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-item-label">Valor</span>
                                    <span class="metric-item-value">{valor_str}</span>
                                </div>
                            </div>
                            <div class="progress-container">
                                <div class="progress-label">
                                    <span>Estoque: {percent_estoque:.0f}%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: {percent_estoque}%; background: {estoque_color};"></div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    if st.session_state.selected_order_for_table:
        order_selected = st.session_state.selected_order_for_table
        df_order_selected = next((o['df_pedido'] for o in pedidos_data if o['pedido'] == order_selected), None)
        
        if df_order_selected is not None and not df_order_selected.empty:
            st.markdown("---")
            show_detail_table(
                df_order_selected, 
                title=f"📋 Detalhamento - Pedido: {order_selected}",
                filter_info=f"Mostrando {len(df_order_selected)} código(s) do pedido {order_selected}"
            )
            
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("🔒 Fechar Tabela", key="close_order_table"):
                    st.session_state.selected_order_for_table = None
                    st.rerun()

# ==================== FUNÇÃO: CALENDÁRIO COM TABELA ====================
def create_calendar_view(df_filtered):
    """Cria visualização de calendário com tabela detalhada"""
    
    if 'Dt. Agendamento' not in df_filtered.columns:
        st.warning("Coluna 'Dt. Agendamento' não encontrada no arquivo.")
        return
    
    df_filtered_clean = df_filtered.dropna(subset=['Dt. Agendamento']).copy()
    
    if df_filtered_clean.empty:
        st.warning("Nenhum pedido com data de agendamento disponível.")
        return
    
    df_filtered_clean['Data'] = pd.to_datetime(df_filtered_clean['Dt. Agendamento']).dt.date
    
    if 'selected_calendar_date' not in st.session_state:
        st.session_state.selected_calendar_date = None
    
    # Agrupar por data
    agendamentos = defaultdict(list)
    for _, row in df_filtered_clean.iterrows():
        data = row['Data']
        qtd = row.get('Qtd', 0)
        saldo_atual = row.get('Saldo Atual', 0)
        saldo_calc = row.get('Saldo Calc.', 0)
        status_text, status_class, _ = get_status(qtd, saldo_atual, saldo_calc)
        
        agendamentos[data].append({
            'pedido': safe_str(row.get('Pedido', 'N/A')),
            'cliente': safe_str(row.get('Cliente', 'N/A')),
            'status': status_text,
            'status_class': status_class
        })
    
    st.subheader("📅 Calendário de Agendamentos")
    
    if agendamentos:
        primeiro_agendamento = min(agendamentos.keys())
        ultimo_agendamento = max(agendamentos.keys())
        
        col1, col2 = st.columns(2)
        with col1:
            mes_selecionado = st.slider("Mês", value=primeiro_agendamento.month, min_value=1, max_value=12)
        with col2:
            ano_selecionado = st.number_input("Ano", value=primeiro_agendamento.year, 
                                              min_value=primeiro_agendamento.year, 
                                              max_value=ultimo_agendamento.year)
        
        st.markdown("---")
        
        cal = calendar.monthcalendar(ano_selecionado, mes_selecionado)
        dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        
        # Renderizar calendário com HTML/CSS
        html_calendar = '<div class="calendar-grid">'
        
        # Headers dos dias
        for dia in dias_semana:
            html_calendar += f'<div class="calendar-day-header">{dia}</div>'
        
        # Dias do mês
        for semana in cal:
            for dia in semana:
                if dia == 0:
                    html_calendar += '<div class="calendar-day empty"></div>'
                else:
                    data_dia = datetime(ano_selecionado, mes_selecionado, dia).date()
                    
                    if data_dia in agendamentos:
                        pedidos_dia = agendamentos[data_dia]
                        has_prioridade = any(p['status_class'] == 'prioridade' for p in pedidos_dia)
                        has_atencao = any(p['status_class'] == 'atencao' for p in pedidos_dia)
                        
                        if has_prioridade:
                            dia_class = "has-events prioridade"
                        elif has_atencao:
                            dia_class = "has-events atencao"
                        else:
                            dia_class = "has-events ok"
                        
                        key = f"calendar_day_{data_dia}"
                        html_calendar += f'<div class="calendar-day {dia_class}"><strong>{dia}</strong><br><small>({len(pedidos_dia)})</small></div>'
                    else:
                        html_calendar += f'<div class="calendar-day">{dia}</div>'
        
        html_calendar += '</div>'
        st.markdown(html_calendar, unsafe_allow_html=True)
        
        # Botões para ver data
        st.markdown("---")
        st.markdown("### 🔍 Selecione uma data para ver detalhes:")
        
        cols = st.columns(7)
        for col, dia in zip(cols, dias_semana):
            col.write("")
        
        for semana in cal:
            cols = st.columns(7)
            for col, dia in zip(cols, semana):
                if dia == 0:
                    col.write("")
                else:
                    data_dia = datetime(ano_selecionado, mes_selecionado, dia).date()
                    
                    if data_dia in agendamentos:
                        if col.button(f"📌 {dia}", key=f"btn_{data_dia}", use_container_width=True):
                            st.session_state.selected_calendar_date = data_dia
                            st.rerun()
    
    # Tabela de detalhes da data selecionada
    if st.session_state.selected_calendar_date:
        data_selecionada = st.session_state.selected_calendar_date
        df_data = df_filtered_clean[df_filtered_clean['Data'] == data_selecionada].copy()
        
        if not df_data.empty:
            st.markdown("---")
            show_detail_table(
                df_data,
                title=f"📋 Detalhamento - Data: {data_selecionada.strftime('%d/%m/%Y')}",
                filter_info=f"Mostrando {len(df_data)} código(s) agendado(s) para {data_selecionada.strftime('%d/%m/%Y')}"
            )
            
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("🔒 Fechar Tabela", key="close_calendar_table"):
                    st.session_state.selected_calendar_date = None
                    st.rerun()

# ==================== FUNÇÃO PRINCIPAL ====================
def main():
    st.markdown("""
        <div class="main-header">
            <h1>⚙️ Ferramenta de Gestão de Confecção</h1>
            <p>Gerencie seus pedidos, agendamentos e estoque de forma inteligente</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("""
            <div class="sidebar-header">
                <h2>🎯 Menu Principal</h2>
            </div>
        """, unsafe_allow_html=True)
        
        modulo = st.radio(
            "Selecione o módulo:",
            ["📋 Filtro de Confecção", "📅 Agendamento de Pedidos", "📊 Dashboard"],
            index=0
        )
        
        st.markdown("---")
        
        with st.expander("ℹ️ Sobre o Sistema"):
            st.markdown("""
                **Versão:** 6.3 - Com Cálculo de Necessidade
                
                ### ✨ Novidades:
                - ✅ Layout moderno e responsivo
                - ✅ Menu melhorado com melhor UX
                - ✅ Cards por Pedido (ao invés de Cliente)
                - ✅ Detalhamento por Código
                - ✅ Calendário interativo com cores
                - ✅ Filtro de Desconsideração
                - ✅ Visualização Dt Emissão e Dt Entrega
                - ✅ **NOVO: Cálculo de Necessidade no Módulo Confecção**
            """)
        
        st.markdown("---")
        st.markdown("### 📊 Status")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("🟢 **Online**")
        with col2:
            st.markdown(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
    
    if modulo == "📋 Filtro de Confecção":
        render_confeccao()
    elif modulo == "📅 Agendamento de Pedidos":
        render_agendamento()
    else:
        render_dashboard()

def render_confeccao():
    """Renderiza o módulo de filtro de confecção"""
    st.markdown("## 📋 Filtro de Dados de Confecção")
    st.markdown("Faça o upload do seu banco de dados em Excel para começar.")
    
    uploaded_file = st.file_uploader("Selecione o arquivo Excel", type=["xlsx", "xls"], key="confeccao_file")
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.strip()
            
            st.success(f"✅ Arquivo carregado! {len(df)} registros encontrados.")
            
            # Mostrar colunas encontradas
            with st.expander("📋 Colunas encontradas no arquivo"):
                st.write(list(df.columns))
            
            # ==================== CRIAÇÃO DA COLUNA NECESSIDADE ====================
            # Verificar se tem as colunas necessárias para cálculo da necessidade
            if 'Saldo 1' in df.columns and 'Saldo' in df.columns:
                # Converter para numérico
                df['Saldo 1'] = pd.to_numeric(df['Saldo 1'], errors='coerce').fillna(0)
                df['Saldo'] = pd.to_numeric(df['Saldo'], errors='coerce').fillna(0)
                
                # Calcular necessidade
                df['Necessidade'] = df.apply(calcular_necessidade, axis=1)
                
                st.success(f"✅ Coluna 'Necessidade' calculada com base em Saldo 1 e Saldo")
                
                # Mostrar estatísticas da necessidade
                necessidades_negativas = df[df['Necessidade'] < 0]
                if not necessidades_negativas.empty:
                    st.info(f"📊 {len(necessidades_negativas)} registro(s) com necessidade negativa (necessitam de produção)")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Soma da Necessidade", f"{df['Necessidade'].sum():.0f}")
                    with col2:
                        st.metric("Média da Necessidade", f"{df['Necessidade'].mean():.1f}")
                    with col3:
                        st.metric("Máximo Negativo", f"{df['Necessidade'].min():.0f}")
            elif 'Saldo 1' in df.columns:
                st.warning("⚠️ Coluna 'Saldo' não encontrada. Necessidade calculada apenas com Saldo 1")
                df['Saldo 1'] = pd.to_numeric(df['Saldo 1'], errors='coerce').fillna(0)
                df['Necessidade'] = df['Saldo 1'] * -1.10
            elif 'Saldo' in df.columns:
                st.warning("⚠️ Coluna 'Saldo 1' não encontrada. Necessidade não pode ser calculada")
            else:
                st.warning("⚠️ Colunas 'Saldo 1' e 'Saldo' não encontradas. Necessidade não foi calculada")
            # ==================== FIM CRIAÇÃO DA COLUNA NECESSIDADE ====================
            
            expected_columns = ['Compra', 'Cód Confec', 'Confeccionado', 'Qtd', 'Qtd Ret', 'Saldo', 'Saldo 1', 'Confecção']
            available_cols = [col for col in expected_columns if col in df.columns]
            missing_cols = [col for col in expected_columns if col not in df.columns]
            
            if missing_cols:
                st.warning(f"⚠️ Colunas não encontradas: {', '.join(missing_cols)}")
            
            if not available_cols:
                st.error("Nenhuma coluna esperada encontrada no arquivo.")
                return
            
            df_filtered = df.copy()
            
            linhas_removidas = 0
            if 'Qtd' in df_filtered.columns and 'Qtd Ret' in df_filtered.columns:
                df_filtered, linhas_removidas = filter_by_qtd_ret_percent(df_filtered, 'Qtd', 'Qtd Ret', 95)
                if linhas_removidas > 0:
                    st.info(f"ℹ️ {linhas_removidas} linha(s) removida(s) por terem Qtd Ret ≥ 95% da Qtd.")
            
            st.sidebar.markdown("## 🔍 Filtros da Confecção")
            
            # ==================== FILTRO DE DESCONSIDERAÇÃO ====================
            st.sidebar.markdown("### 🚫 Filtro de Desconsideração")
            desconsiderar_itens_retornados = st.sidebar.checkbox(
                "Desconsiderar itens 100% retornados",
                value=False,
                help="Remove itens onde a quantidade retornada é igual ou superior à quantidade total"
            )
            
            linhas_desconsideradas = 0
            if desconsiderar_itens_retornados:
                if 'Qtd' in df_filtered.columns and 'Qtd Ret' in df_filtered.columns:
                    df_filtered['Qtd'] = pd.to_numeric(df_filtered['Qtd'], errors='coerce').fillna(0)
                    df_filtered['Qtd Ret'] = pd.to_numeric(df_filtered['Qtd Ret'], errors='coerce').fillna(0)
                    
                    linhas_antes = len(df_filtered)
                    df_filtered = df_filtered[df_filtered['Qtd Ret'] < df_filtered['Qtd']]
                    linhas_desconsideradas = linhas_antes - len(df_filtered)
                    
                    if linhas_desconsideradas > 0:
                        st.sidebar.markdown(f'<div class="warning-box">⚠️ {linhas_desconsideradas} item(ns) removido(s) por estarem 100% retornado(s)</div>', unsafe_allow_html=True)
            
            # ==================== FIM FILTRO ====================
            
            if 'Confecção' in df_filtered.columns:
                df_filtered['Confecção'] = df_filtered['Confecção'].fillna("Vazio").astype(str)
                confeccoes = sorted(df_filtered['Confecção'].unique())
                confeccoes_selecionadas = st.sidebar.multiselect(
                    "Filtrar por Confecção:", 
                    options=confeccoes, 
                    default=confeccoes
                )
                if confeccoes_selecionadas:
                    df_filtered = df_filtered[df_filtered['Confecção'].isin(confeccoes_selecionadas)]
            
            if 'Confeccionado' in df_filtered.columns:
                termo_busca = st.sidebar.text_input("Contém no nome do produto:", value="")
                if termo_busca:
                    df_filtered['Confeccionado'] = df_filtered['Confeccionado'].fillna("").astype(str)
                    df_filtered = df_filtered[df_filtered['Confeccionado'].str.contains(termo_busca, case=False, na=False)]
            
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🎯 Filtro Avançado por Código")
            
            if 'Cód Confec' in df_filtered.columns:
                df_filtered['Cód Confec'] = df_filtered['Cód Confec'].fillna("").astype(str)
                df_filtered['Cód Confec'] = df_filtered['Cód Confec'].str.replace(r'\.0$', '', regex=True).str.strip()
                
                todos_cods = sorted([c for c in df_filtered['Cód Confec'].unique() if c and c != ''])
                
                arquivo_cods = st.sidebar.file_uploader(
                    "Upload Excel com lista de códigos", 
                    type=["xlsx", "xls"], 
                    key="upload_cods_confeccao",
                    help="Arquivo deve conter uma coluna 'Cód Confec' ou usar a primeira coluna"
                )
                
                codigos_do_arquivo = []
                if arquivo_cods is not None:
                    try:
                        df_cods = pd.read_excel(arquivo_cods)
                        df_cods.columns = df_cods.columns.str.strip()
                        
                        if 'Cód Confec' in df_cods.columns:
                            serie_cods = df_cods['Cód Confec']
                        else:
                            serie_cods = df_cods.iloc[:, 0]
                        
                        serie_cods = serie_cods.fillna("").astype(str)
                        serie_cods = serie_cods.str.replace(r'\.0$', '', regex=True).str.strip()
                        codigos_do_arquivo = [c for c in serie_cods.tolist() if c and c.lower() != 'nan']
                        
                        codigos_validos = [c for c in codigos_do_arquivo if c in todos_cods]
                        
                        if codigos_validos:
                            st.sidebar.success(f"✅ {len(codigos_validos)} código(s) válido(s) encontrado(s)")
                            codigos_do_arquivo = codigos_validos
                        else:
                            st.sidebar.warning("⚠️ Nenhum código correspondente encontrado")
                            codigos_do_arquivo = []
                            
                    except Exception as e:
                        st.sidebar.error(f"Erro ao ler arquivo: {e}")
                        codigos_do_arquivo = []
                
                default_cods = validate_default_options(todos_cods, codigos_do_arquivo)
                
                selecionados_cods = st.sidebar.multiselect(
                    "Códigos do Produto:", 
                    options=todos_cods, 
                    default=default_cods
                )
                
                if selecionados_cods:
                    df_filtered = df_filtered[df_filtered['Cód Confec'].isin(selecionados_cods)]
                    st.sidebar.info(f"📊 {len(selecionados_cods)} código(s) selecionado(s)")
            
            st.markdown("---")
            
            # Métricas principais
            col1, col2, col3, col4 = st.columns(4)
            
            cols_numericas = [col for col in ['Qtd', 'Qtd Ret', 'Saldo', 'Saldo 1'] if col in df_filtered.columns]
            for col in cols_numericas:
                df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)
            
            col1.metric("Total de Registros", len(df_filtered))
            if 'Qtd' in cols_numericas:
                col2.metric("Soma de Qtd", f"{df_filtered['Qtd'].sum():.0f}")
            if 'Qtd Ret' in cols_numericas:
                col3.metric("Soma de Qtd Ret", f"{df_filtered['Qtd Ret'].sum():.0f}")
            if 'Saldo' in cols_numericas:
                col4.metric("Soma de Saldo", f"{df_filtered['Saldo'].sum():.0f}")
            
            # Exibir métrica de Saldo 1 se existir
            if 'Saldo 1' in cols_numericas:
                col5 = st.columns(1)[0]
                with col5:
                    st.metric("Soma de Saldo 1", f"{df_filtered['Saldo 1'].sum():.0f}")
            
            # Exibir métrica da Necessidade se existir
            if 'Necessidade' in df_filtered.columns:
                col5, col6, col7 = st.columns(3)
                with col5:
                    st.metric("Soma da Necessidade", f"{df_filtered['Necessidade'].sum():.0f}")
                with col6:
                    st.metric("Média da Necessidade", f"{df_filtered['Necessidade'].mean():.1f}")
                with col7:
                    itens_necessidade = len(df_filtered[df_filtered['Necessidade'] < 0])
                    st.metric("Itens com Necessidade", itens_necessidade)
            
            st.markdown("---")
            
            # Abas de visualização
            if 'Confecção' in df_filtered.columns:
                df_filtered['Confecção'] = df_filtered['Confecção'].astype(str)
                confeccoes_unicas = [c for c in df_filtered['Confecção'].dropna().unique().tolist() if c and c != 'nan' and c != '']
                confeccoes_unicas.sort()
                
                nomes_abas = ["📋 Visão Geral", "📊 Resumo Agrupado"] + [f"🏭 {conf[:30]}" for conf in confeccoes_unicas]
                abas = st.tabs(nomes_abas)
                
                with abas[0]:
                    st.markdown("### 📋 Tabela Completa")
                    st.markdown(f"Mostrando {len(df_filtered)} registros após aplicação dos filtros")
                    
                    # Definir colunas para exibição
                    display_cols = ['Compra', 'Cód Confec', 'Confeccionado', 'Qtd', 'Qtd Ret', 'Saldo 1', 'Saldo', 'Confecção']
                    if 'Necessidade' in df_filtered.columns:
                        display_cols.insert(7, 'Necessidade')
                    
                    display_cols = [col for col in display_cols if col in df_filtered.columns]
                    
                    if display_cols:
                        df_display = df_filtered[display_cols].copy()
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                with abas[1]:
                    st.markdown("### 📊 Resumo por Confecção")
                    
                    # Colunas para agrupamento
                    cols_agrupamento = ['Qtd', 'Qtd Ret', 'Saldo', 'Saldo 1']
                    if 'Necessidade' in df_filtered.columns:
                        cols_agrupamento.append('Necessidade')
                    
                    cols_agrupamento = [col for col in cols_agrupamento if col in df_filtered.columns]
                    
                    if cols_agrupamento:
                        df_agrupado = df_filtered.groupby('Confecção')[cols_agrupamento].sum().reset_index()
                        
                        if 'Qtd' in df_agrupado.columns:
                            df_agrupado = df_agrupado.sort_values('Qtd', ascending=False)
                        
                        st.dataframe(df_agrupado, use_container_width=True, hide_index=True)
                        
                        st.markdown("#### 📊 Distribuição por Confecção")
                        if 'Qtd' in df_filtered.columns:
                            chart_data = df_filtered.groupby('Confecção')['Qtd'].sum().sort_values(ascending=False)
                            st.bar_chart(chart_data)
                    else:
                        st.info("Não há colunas numéricas para realizar o agrupamento.")
                
                for i, conf in enumerate(confeccoes_unicas):
                    with abas[i+2]:
                        df_aba = df_filtered[df_filtered['Confecção'] == conf]
                        
                        # Métricas da confecção
                        metric_cols = st.columns(4)
                        with metric_cols[0]:
                            st.metric("Total de Registros", len(df_aba))
                        if 'Qtd' in df_aba.columns:
                            with metric_cols[1]:
                                st.metric("Soma de Qtd", f"{df_aba['Qtd'].sum():.0f}")
                        if 'Saldo' in df_aba.columns:
                            with metric_cols[2]:
                                st.metric("Soma de Saldo", f"{df_aba['Saldo'].sum():.0f}")
                        if 'Necessidade' in df_aba.columns:
                            with metric_cols[3]:
                                st.metric("Soma da Necessidade", f"{df_aba['Necessidade'].sum():.0f}")
                        
                        st.markdown("---")
                        
                        # Tabela da confecção
                        display_cols_aba = ['Compra', 'Cód Confec', 'Confeccionado', 'Qtd', 'Qtd Ret', 'Saldo 1', 'Saldo']
                        if 'Necessidade' in df_aba.columns:
                            display_cols_aba.append('Necessidade')
                        
                        display_cols_aba = [col for col in display_cols_aba if col in df_aba.columns]
                        
                        if display_cols_aba:
                            st.dataframe(df_aba[display_cols_aba], use_container_width=True, hide_index=True)
            else:
                # Se não tem coluna Confecção, mostrar apenas a tabela
                display_cols = [col for col in df_filtered.columns if col not in ['index']]
                st.dataframe(df_filtered[display_cols], use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("📥 Exportar Relatórios")
            
            col1, col2 = st.columns(2)
            
            with col1:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    # Sheet principal
                    df_filtered.to_excel(writer, sheet_name='Filtrado', index=False)
                    
                    # Resumo por confecção
                    if 'Confecção' in df_filtered.columns:
                        cols_agrupamento = ['Qtd', 'Qtd Ret', 'Saldo', 'Saldo 1']
                        if 'Necessidade' in df_filtered.columns:
                            cols_agrupamento.append('Necessidade')
                        cols_agrupamento = [col for col in cols_agrupamento if col in df_filtered.columns]
                        
                        if cols_agrupamento:
                            df_agrupado = df_filtered.groupby('Confecção')[cols_agrupamento].sum().reset_index()
                            df_agrupado.to_excel(writer, sheet_name='Resumo_Confecções', index=False)
                    
                    # Itens com necessidade negativa
                    if 'Necessidade' in df_filtered.columns:
                        df_necessidade = df_filtered[df_filtered['Necessidade'] < 0].copy()
                        if not df_necessidade.empty:
                            df_necessidade.to_excel(writer, sheet_name='Itens_com_Necessidade', index=False)
                
                st.download_button(
                    label="⬇️ Baixar Excel",
                    data=buffer.getvalue(),
                    file_name=f"relatorio_confeccao_{datetime.now().strftime('%d_%m_%Y_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col2:
                csv = df_filtered.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv,
                    file_name=f"relatorio_confeccao_{datetime.now().strftime('%d_%m_%Y_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
            st.exception(e)
    else:
        st.info("👆 Faça o upload de um arquivo Excel para começar.")
        with st.expander("📝 Ver formato esperado"):
            st.markdown("""
                ### Colunas esperadas:
                - **Compra** - Número da compra
                - **Cód Confec** - Código do produto confeccionado
                - **Confeccionado** - Nome do produto
                - **Qtd** - Quantidade total
                - **Qtd Ret** - Quantidade retornada
                - **Saldo** - Saldo atual
                - **Saldo 1** - Saldo para cálculo da necessidade (importado do arquivo)
                - **Confecção** - Nome da confecção (para agrupamento)
                
                ### 🆕 Nova funcionalidade:
                **Coluna Necessidade**:
                - Calculada automaticamente usando as colunas 'Saldo 1' e 'Saldo' do arquivo importado
                - Fórmula: Necessidade = (Saldo 1 * -1,10)
                - Limitada pelo valor máximo do 'Saldo' (necessidade não pode ser menor que -Saldo)
                - Valores negativos indicam necessidade de produção
                
                ### Regras aplicadas:
                - 🚫 Linhas com **Qtd Ret ≥ 95% da Qtd** são automaticamente ocultadas
                - 🚫 Filtro para desconsiderar itens 100% retornados
                - 📁 Dados são agrupados em abas por confecção
                - 🎯 Filtro avançado permite upload de lista de códigos em Excel
                - 📊 Nova coluna de Necessidade para análise de demanda
            """)

def render_agendamento():
    """Renderiza o módulo de agendamento de pedidos"""
    st.markdown("## 📅 Agendamento de Pedidos")
    
    uploaded_file = st.file_uploader("Carregue o arquivo Excel", type=['xlsx', 'xls'], key="agendamento_file")
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.strip()
            
            st.success(f"✅ Arquivo carregado! {len(df)} registros encontrados.")
            
            if 'Dt. Agendamento' in df.columns:
                df['Dt. Agendamento'] = pd.to_datetime(df['Dt. Agendamento'], errors='coerce')
            
            if 'Dt Emissão' in df.columns:
                df['Dt Emissão'] = pd.to_datetime(df['Dt Emissão'], errors='coerce')
            
            if 'Dt Entrega' in df.columns:
                df['Dt Entrega'] = pd.to_datetime(df['Dt Entrega'], errors='coerce')
            
            st.sidebar.markdown("## 🔍 Filtros")
            
            df_filtered = df.copy()
            
            if 'Operação Produtiva' in df.columns:
                ops = st.sidebar.multiselect("Operação", options=df['Operação Produtiva'].unique())
                if ops:
                    df_filtered = df_filtered[df_filtered['Operação Produtiva'].isin(ops)]
            
            if 'Segmento' in df.columns:
                segs = st.sidebar.multiselect("Segmento", options=df['Segmento'].unique())
                if segs:
                    df_filtered = df_filtered[df_filtered['Segmento'].isin(segs)]
            
            if 'Coleção' in df.columns:
                cols_filter = st.sidebar.multiselect("Coleção", options=df['Coleção'].unique())
                if cols_filter:
                    df_filtered = df_filtered[df_filtered['Coleção'].isin(cols_filter)]
            
            if 'Cliente' in df.columns:
                clients = st.sidebar.multiselect("Cliente", options=df['Cliente'].unique())
                if clients:
                    df_filtered = df_filtered[df_filtered['Cliente'].isin(clients)]
            
            if all(col in df_filtered.columns for col in ['Qtd', 'Saldo Atual', 'Saldo Calc.']):
                df_filtered['Status'] = df_filtered.apply(
                    lambda row: get_status(row['Qtd'], row['Saldo Atual'], row['Saldo Calc.'])[0],
                    axis=1
                )
            
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🎯 Filtro por Status")
            client_status_filter = st.sidebar.selectbox(
                "Status do Pedido",
                options=["Todos", "PRIORIDADE", "ATENÇÃO", "OK"],
                index=0
            )
            
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de Códigos", len(df_filtered))
            if 'Pedido' in df_filtered.columns:
                with col2:
                    st.metric("Total de Pedidos", df_filtered['Pedido'].nunique())
            if 'Status' in df_filtered.columns:
                with col3:
                    prioridades = len(df_filtered[df_filtered['Status'] == 'PRIORIDADE'])
                    st.metric("🔴 Prioridades", prioridades)
                with col4:
                    atencoes = len(df_filtered[df_filtered['Status'] == 'ATENÇÃO'])
                    st.metric("🟠 Atenções", atencoes)
            
            st.markdown("---")
            
            if not df_filtered.empty:
                status_map = {"Todos": None, "PRIORIDADE": "PRIORIDADE", "ATENÇÃO": "ATENÇÃO", "OK": "OK"}
                
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📦 Cards por Pedido",
                    "📅 Calendário",
                    "📋 Tabela Completa",
                    "📥 Exportar Dados"
                ])
                
                with tab1:
                    st.markdown("### 📦 Visualização por Pedido com Detalhes de Código")
                    st.markdown("Pedidos agrupados com detalhamento de cada código/produto")
                    create_order_cards(df_filtered, status_map[client_status_filter])
                
                with tab2:
                    st.markdown("### 📅 Visualização em Calendário")
                    st.markdown("Pedidos organizados por data de agendamento com cores por prioridade")
                    create_calendar_view(df_filtered)
                
                with tab3:
                    st.markdown("### 📋 Tabela Geral Completa")
                    st.markdown("Visualização tabular de todos os códigos com filtros aplicados")
                    show_detail_table(df_filtered, title="📋 Todos os Códigos", filter_info=f"Total de {len(df_filtered)} códigos encontrados")
                
                with tab4:
                    st.markdown("#### 📊 Opções de Exportação")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        csv = df_filtered.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            "📥 Baixar CSV", 
                            data=csv, 
                            file_name=f"pedidos_{datetime.now().strftime('%d_%m_%Y_%H%M')}.csv", 
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    with col2:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df_filtered.to_excel(writer, sheet_name='Pedidos', index=False)
                            
                            if 'Status' in df_filtered.columns:
                                resumo = df_filtered.groupby('Status').size().reset_index(name='Quantidade')
                                resumo.to_excel(writer, sheet_name='Resumo_Status', index=False)
                            
                            if 'Pedido' in df_filtered.columns:
                                pedidos_resumo = df_filtered.groupby('Pedido').size().reset_index(name='Total_Codigos')
                                pedidos_resumo = pedidos_resumo.sort_values('Total_Codigos', ascending=False)
                                pedidos_resumo.to_excel(writer, sheet_name='Resumo_Pedidos', index=False)
                        
                        st.download_button(
                            "📥 Baixar Excel", 
                            data=buffer.getvalue(), 
                            file_name=f"pedidos_{datetime.now().strftime('%d_%m_%Y_%H%M')}.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
            else:
                st.warning("Nenhum pedido encontrado com os filtros selecionados.")
            
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
            st.exception(e)
    else:
        st.info("👆 Faça o upload de um arquivo Excel para começar.")
        with st.expander("📝 Ver formato esperado"):
            st.markdown("""
                ### Colunas necessárias:
                - **Pedido** - ID do pedido
                - **Cliente** - Nome do cliente
                - **Produto** - Nome do produto
                - **Cód Prod** - Código do produto
                - **Qtd** - Quantidade
                - **Saldo Atual** - Estoque atual
                - **Saldo Calc.** - Estoque calculado
                - **Dt. Agendamento** - Data (obrigatória para calendário)
                - **Dt Emissão** - Data de Emissão (opcional)
                - **Dt Entrega** - Data de Entrega (opcional)
                
                ### Funcionalidades:
                
                **📦 Cards por Pedido**
                - Visualização agrupada por pedido
                - Detalhamento de cada código/produto
                - Barras de progresso de estoque
                - Status visual por cor
                
                **📅 Calendário**
                - Visualização em calendário mensal
                - Cores indicativas por prioridade
                - Clique na data para ver detalhes
                
                **📋 Tabela Completa**
                - Tabela detalhada com todos os dados
                - Exibição de Dt Emissão e Dt Entrega
                
                **📥 Exportação**
                - Exportação para CSV e Excel
                - Resumos automáticos por status e pedido
            """)

def render_dashboard():
    """Renderiza dashboard"""
    st.markdown("## 📊 Dashboard de Gestão")
    st.markdown("Visão geral do sistema de gestão de confecção - Versão 6.3")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📋</div>
                <div class="metric-label" style="font-size: 1rem;">Módulo 1</div>
                <div class="metric-label">Filtro de Confecção</div>
            </div>
            <br>
            <div style="padding: 1rem; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
                <b>Funcionalidades:</b><br>
                ✅ Upload de arquivos Excel<br>
                ✅ <b>Cálculo de Necessidade</b><br>
                ✅ Filtro avançado por código<br>
                ✅ Upload de lista em Excel<br>
                ✅ Agrupamento em abas por confecção<br>
                ✅ Ocultação automática (Qtd Ret > 95%)<br>
                ✅ Filtro de Desconsideração<br>
                ✅ Exportação de relatórios
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📦</div>
                <div class="metric-label" style="font-size: 1rem;">Módulo 2</div>
                <div class="metric-label">Agendamento de Pedidos</div>
            </div>
            <br>
            <div style="padding: 1rem; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
                <b>Funcionalidades:</b><br>
                ✅ Cards por Pedido<br>
                ✅ Calendário Interativo<br>
                ✅ Detalhes por Código<br>
                ✅ Dt Emissão e Entrega<br>
                ✅ Tabela detalhada<br>
                ✅ Exportação CSV/Excel<br>
                ✅ Status visual colorido
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚡</div>
                <div class="metric-label" style="font-size: 1rem;">Diferenciais</div>
                <div class="metric-label">Design Responsivo</div>
            </div>
            <br>
            <div style="padding: 1rem; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
                <b>Destaques v6.3:</b><br>
                ✅ Layout moderno e limpo<br>
                ✅ Cards por Pedido<br>
                ✅ <b>Cálculo de Necessidade</b><br>
                ✅ Filtro de Desconsideração<br>
                ✅ Datas de Emissão e Entrega<br>
                ✅ Calendário com cores<br>
                ✅ Melhor experiência de usuário
            </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
