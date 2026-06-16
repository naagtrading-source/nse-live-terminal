import streamlit as st
import pandas as pd
import sqlite3
import numpy as np

st.set_page_config(page_title="Institutional Clusters Scanners", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .cluster-card { background: #141722; border-radius: 6px; border: 1px solid #2d334a; padding: 15px; margin-bottom: 15px; }
    .cluster-header { font-size: 1.1rem; font-weight: bold; color: #fff; font-family: monospace; display: flex; justify-content: space-between; }
    .tag-accum { background-color: rgba(46, 189, 133, 0.15); color: #2ebd85; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; border: 1px solid #2ebd85; }
    .tag-dist { background-color: rgba(246, 70, 93, 0.15); color: #f6465d; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; border: 1px solid #f6465d; }
    .metric-num { font-size: 1.3rem; font-weight: bold; font-family: monospace; color: #ff9f43; margin-top: 2px; }
    .metric-lbl { font-size: 0.7rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Institutional High-Density Volume Clusters")
st.caption("Micro-Range Liquidity Concentration Scanners | Identifying Symmetrical Accumulation Channels")

DB_FILE = "terminal_history.db"

def load_ledger_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.fragment(run_every=30)
def process_clusters():
    df = load_ledger_data()
    if df.empty:
        st.info("⏳ Synchronizing deep liquidity matrix layers...")
        return

    st.write("### 🔍 Active Micro-Range Cluster Identifications")
    
    # Process each asset independently to check for narrow price bracket concentrations
    grouped = df.groupby('asset')
    cluster_found = False
    
    for asset, group in grouped:
        # Isolate the newest blocks to check for tight strike crowding
        recent_data = group.head(30)
        if len(recent_data) < 4: continue
        
        # Calculate the distribution spread of strikes to check for range compression
        unique_strikes = recent_data['strike'].unique()
        
        # If institutional volume is heavily hammering the SAME or adjacent strikes, a cluster forms
        if len(unique_strikes) <= 2:
            cluster_found = True
            total_cluster_vol = int(recent_data['volume'].sum())
            
            ce_vol = recent_data[recent_data['type'] == 'CE']['volume'].sum()
            pe_vol = recent_data[recent_data['type'] == 'PE'].volume.sum()
            
            quadrants = recent_data['quadrant'].tolist()
            
            # Determine if the concentrated volume represents an accumulation floor or distribution ceiling
            if "Call Buying" in quadrants or "Put Writing" in quadrants:
                bias_tag = "<span class='tag-accum'>⚡ HIGH-DENSITY ACCUMULATION NODE (PUMP)</span>"
                border_color = "#2ebd85"
                retail_action = "Institutional absorption via block limit orders. Price floor is firmly set."
            else:
                bias_tag = "<span class='tag-dist'>⚠️ HIGH-DENSITY DISTRIBUTION NODE (DUMP)</span>"
                border_color = "#f6465d"
                retail_action = "Institutional inventory unloading via liquidity blocks. Price ceiling is firmly set."
                
            avg_premium = round(recent_data['ltp'].mean(), 1)
            time_window = f"{recent_data['timestamp'].iloc[-1]} - {recent_data['timestamp'].iloc[0]}"
            
            st.markdown(f"""
            <div class='cluster-card' style='border-left: 5px solid {border_color};'>
                <div class='cluster-header'>
                    <div>🎯 {asset} Cluster Node</div>
                    <div>{bias_tag}</div>
                </div>
                <p style='margin: 8px 0 15px 0; font-size:0.85rem; color:#e4e6eb;'>
                    {retail_action} Orders consolidated heavily across strike bounds: <b>{', '.join(map(str, unique_strikes))}</b>.
                </p>
                <div class='row text-center'>
                    <div class='col-3'><div class='metric-lbl'>Aggregated Volume</div><div class='metric-num'>{total_cluster_vol:,} lots</div></div>
                    <div class='col-3'><div class='metric-lbl'>Concentration Range</div><div class='metric-num' style='color:#fff;'>TIGHT BLOCK</div></div>
                    <div class='col-3'><div class='metric-lbl'>Mean Premium LTP</div><div class='metric-num' style='color:#ff9f43;'>{avg_premium}</div></div>
                    <div class='col-3'><div class='metric-lbl'>Intraday Session Window</div><div class='metric-num' style='color:#a0a5b5; font-size:1rem; margin-top:6px;'>{time_window}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    if not cluster_found:
        st.info("🎯 Options liquidity is currently distributed normally. Scanning order books for micro-range volume loading...")

process_clusters()
