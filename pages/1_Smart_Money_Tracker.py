import streamlit as st
import pandas as pd
import sqlite3
import streamlit.components.v1 as components

st.set_page_config(page_title="Smart Money Institutional Tracker", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .pump-text { color: #2ebd85 !important; font-weight: bold; font-size: 1.2rem; }
    .dump-text { color: #f6465d !important; font-weight: bold; font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Smart Money Institutional Flow Scanner")
st.caption("Intraday Aggressive Position Scanners | Isolating Multi-Crore Pump & Dump Signatures")

# --- DATABASE READER ---
DB_FILE = "terminal_history.db"

def load_ledger_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# --- ANALYTICS ENGINE MODULE ---
def calculate_institutional_flows():
    df = load_ledger_from_db()
    if df.empty:
        return pd.DataFrame()
    
    analysis_rows = []
    # Group transactions across individual assets to calculate network concentration scores
    grouped = df.groupby('asset')
    
    for asset, group in grouped:
        # Sort by row ID to isolate the absolute newest snapshot records
        latest_records = group.sort_values(by='id', ascending=False).head(20)
        
        ce_sub = latest_records[latest_records['type'] == 'CE']
        pe_sub = latest_records[latest_records['type'] == 'PE']
        
        # Pull transactional buy vs sell weights matching Quantsapp's core scanning logic
        ce_buy_vol = ce_sub[ce_sub['quadrant'] == "Call Buying"]['volume'].sum()
        ce_sell_vol = ce_sub[ce_sub['quadrant'] == "Call Writing"]['volume'].sum()
        pe_buy_vol = pe_sub[pe_sub['quadrant'] == "Put Buying"]['volume'].sum()
        pe_sell_vol = pe_sub[pe_sub['quadrant'] == "Put Writing"]['volume'].sum()
        
        total_tracked_volume = int(latest_records['volume'].sum())
        
        # FORMULA: Institutional Pumping Bias = Aggressive Call Buying + Aggressive Put Writing Floor Building
        pumping_power = ce_buy_vol + pe_sell_vol
        # FORMULA: Institutional Dumping Bias = Aggressive Call Writing + Aggressive Put Buying Momentum
        dumping_power = ce_sell_vol + pe_buy_vol
        
        if pumping_power > dumping_power * 1.05:
            bias_signal = "🟢 ACCUMULATION (PUMP)"
            flow_score = round((pumping_power / max(1, dumping_power)) * 10, 1)
            style_class = "pump-text"
        elif dumping_power > pumping_power * 1.05:
            bias_signal = "🔴 DISTRIBUTION (DUMP)"
            flow_score = round((dumping_power / max(1, pumping_power)) * 10, 1)
            style_class = "dump-text"
        else:
            bias_signal = "🟡 NEUTRAL CHOP"
            flow_score = 5.0
            style_class = "text-muted"
            
        m_type = latest_records['market_type'].iloc[0] if 'market_type' in latest_records.columns else "INDEX"
        latest_ts = latest_records['timestamp'].iloc[0]
        
        analysis_rows.append({
            'Asset': asset,
            'Market': m_type,
            'Flow Score': flow_score,
            'Institutional Bias': bias_signal,
            'Cumulative Volume': total_tracked_volume,
            'Last Scan': latest_ts,
            'Style': style_class
        })
        
    return pd.DataFrame(analysis_rows).sort_values(by='Flow Score', ascending=False)

# --- REFRESH WRAPPER FRAGMENT ---
@st.fragment(run_every=30)
def render_tracker_dashboard():
    flow_df = calculate_institutional_flows()
    
    if not flow_df.empty:
        c1, c2 = st.columns([1, 3])
        with c1:
            st.metric(label="Total Scanned Instruments", value=len(flow_df['Asset'].unique()))
        with c2:
            top_pump = flow_df[flow_df['Institutional Bias'].str.contains("PUMP")].head(1)
            if not top_pump.empty:
                st.write(f"🔥 Highest Institutional Inflow Node: **{top_pump['Asset'].values[0]}** (Score: {top_pump['Flow Score'].values[0]}/50)")
        
        st.markdown("---")
        
        # Build individual UI summary panels matching professional terminal configurations
        for _, row in flow_df.iterrows():
            border_color = "#2ebd85" if "PUMP" in row['Institutional Bias'] else "#f6465d" if "DUMP" in row['Institutional Bias'] else "#2d334a"
            bg_gradient = "rgba(46, 189, 133, 0.05)" if "PUMP" in row['Institutional Bias'] else "rgba(246, 70, 93, 0.05)" if "DUMP" in row['Institutional Bias'] else "rgba(30, 34, 48, 0.3)"
            
            card_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body {{ background-color: #0b0c10; color: #e4e6eb; font-family: system-ui, sans-serif; padding: 0; margin: 0; }}
                    .tracker-card {{ 
                        background: {bg_gradient}; 
                        border: 1px solid {border_color}; 
                        border-radius: 6px; 
                        padding: 14px 20px; 
                        margin-bottom: 15px; 
                        display: flex; 
                        justify-content: space-between; 
                        align-items: center;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                    }}
                    .asset-title {{ font-size: 1.25rem; font-weight: bold; color: #fff; margin: 0; font-family: monospace; }}
                    .market-badge {{ font-size: 0.68rem; background-color: #1b1f2e; padding: 2px 6px; border-radius: 4px; color: #a0a5b5; margin-left: 8px; border: 1px solid #2d334a; }}
                    .score-badge {{ font-size: 1.4rem; font-weight: bold; font-family: monospace; color: #ff9f43; }}
                    .bias-text {{ font-weight: bold; font-size: 0.95rem; }}
                </style>
            </head>
            <body>
                <div class="tracker-card">
                    <div>
                        <div class="d-flex align-items-center mb-1">
                            <p class="asset-title">{row['Asset']}</p>
                            <span class="market-badge">{row['Market']}</span>
                        </div>
                        <small style="color: #a0a5b5;">Accumulated Order Book Volume: <span style="color:#fff; font-weight:600;">{row['Cumulative Volume']:,} lots</span></small>
                    </div>
                    <div class="text-center">
                        <div class="bias-text" style="color: {'#2ebd85' if 'PUMP' in row['Institutional Bias'] else '#f6465d' if 'DUMP' in row['Institutional Bias'] else '#a0a5b5'};">{row['Institutional Bias']}</div>
                        <small style="color: #666; font-size:0.75rem;">Last Activity Captured: {row['Last Scan']}</small>
                    </div>
                    <div>
                        <span class="stat-label" style="color:#a0a5b5; font-size:0.7rem; display:block; text-align:right;">FLOW POWER</span>
                        <span class="score-badge">{row['Flow Score']}</span>
                    </div>
                </div>
            </body>
            </html>
            """
            components.html(card_html, height=85, scrolling=False)
    else:
        st.info("⏳ Awaiting transaction logs from the core terminal framework. Keep the main app.py tab open to stream spikes...")

render_tracker_dashboard()
