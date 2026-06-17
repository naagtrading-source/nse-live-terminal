import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from datetime import datetime
import streamlit.components.v1 as components

# 🚨 Force wide layout layout matrix parameters immediately
st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .stTable, table { width: 100% !important; table-layout: fixed !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.65rem !important; font-weight: bold !important; padding: 6px 4px !important; border-bottom: 2px solid #222634 !important; }
    td { text-align: center !important; font-size: 0.72rem !important; padding: 6px 4px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 25px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .section-header.commodity { color: #00ffcc; border-left: 4px solid #00ffcc; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Cross-Asset Order Book Feed Engine | High-Speed Live Network API Sync")

DB_FILE = "terminal_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, asset TEXT, market_type TEXT, expiry TEXT,
            strike INTEGER, type TEXT, quadrant TEXT, direction TEXT, volume INTEGER, ltp REAL, delta TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# DUAL ENGINE: INTEGRATED FASTAPI LINK HANDSHAKE
# -----------------------------------------------------------------------------
# Intercept incoming direct raw URL updates sent from the requests engine
query_params = st.query_params
if "webhook_data" in query_params:
    try:
        payload = json.loads(query_params["webhook_data"])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ledger (timestamp, asset, market_type, expiry, strike, type, quadrant, direction, volume, ltp, delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (payload['timestamp'], payload['asset'].upper(), payload.get('market_type', 'INDEX'), payload['expiry'], 
              int(payload['strike']), payload['type'].upper(), payload['quadrant'], payload['direction'], 
              int(payload['volume']), float(payload['ltp']), payload['delta']))
        conn.commit()
        conn.close()
        st.query_params.clear()  # Flush out parameter strings to prevent deadlocks
    except Exception as e:
        pass

def load_live_spikes_from_db():
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            # Pull the latest 40 rows from the localized database ledger
            df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC LIMIT 40", conn)
            conn.close()
            return df
        except:
            return pd.DataFrame()
    return pd.DataFrame()

# -----------------------------------------------------------------------------
# TERMINAL MATRIX RENDERER
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.markdown(f"<p style='color:#666;font-size:0.85rem;padding-left:10px;'>📡 Awaiting live {asset_filter} updates from loop...</p>", unsafe_allow_html=True)
        return
        
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.markdown(f"<p style='color:#666;font-size:0.85rem;padding-left:10px;'>Scanning active {asset_filter} order books...</p>", unsafe_allow_html=True)
        return

    rows_html = ""
    for _, r in f_df.iterrows():
        is_bull = "BULLISH" in str(r.get('direction', '')).upper() or "BUY" in str(r.get('quadrant', '')).upper()
        badge_color = "#2ebd85" if is_bull else "#f6465d"
        bg_row_effect = "rgba(46, 189, 133, 0.08)" if is_bull else "rgba(246, 70, 93, 0.08)"
        
        contract_type = str(r.get('type', 'CE')).upper()
        strike_val = int(r.get('strike', 0))
        expiry_lbl = str(r.get('expiry', '26DEC')).upper()
        
        formatted_symbol = f"{asset_filter}{expiry_lbl}{strike_val}{contract_type}"
        vol_amt = int(r.get('volume', 0))
        surge_val = str(r.get('delta', "+0.0%"))

        rows_html += f"""
        <tr style='background-color: {bg_row_effect} !important; border-bottom: 1px solid #1f2231;'>
            <td style='color:#a0a5b5; font-family: monospace;'>🕒 {r['timestamp']}</td>
            <td style='color:#ffffff; font-weight:bold; font-family: monospace;'>🚨 NEW SPIKE</td>
            <td style='color:#ff9f43; font-weight:900; font-family: monospace;'>{formatted_symbol}</td>
            <td style='color:#ffffff; font-family: monospace;'>Vol: <span style='font-weight:bold;'>{vol_amt:,}</span></td>
            <td style='color:{badge_color}; font-weight:bold; font-family: monospace;'>Surge: {surge_val}</td>
            <td style='color:#ffffff; font-weight:bold; font-family: monospace;'>LTP: {round(float(r.get('ltp', 0.0)), 1)}</td>
        </tr>"""
        
    table_html = f"""
    <html><head><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'></head>
    <body style='background-color: #0b0c10; padding:0; margin:0; overflow-x:hidden;'>
    <table class='table table-dark table-borderless m-0' style='width: 100%; table-layout: fixed; text-align:left;'>
        <tbody>{rows_html}</tbody>
    </table></body></html>
    """
    components.html(table_html, height=200, scrolling=True)

# -----------------------------------------------------------------------------
# MAIN DASHBOARD RENDER LAYER
# -----------------------------------------------------------------------------
all_df = load_live_spikes_from_db()

# SECTION 1: EQUITY INDICES
st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE EQUITY INDICES</div>", unsafe_allow_html=True)
idx_col1, idx_col2 = st.columns(2)
with idx_col1:
    st.markdown("<div class='asset-title-banner'>🦅 NIFTY INSTANT SURGE LOGGER</div>", unsafe_allow_html=True)
    render_terminal_log_block("NIFTY", all_df)
with idx_col2:
    st.markdown("<div class='asset-title-banner'>🦅 BANKNIFTY INSTANT SURGE LOGGER</div>", unsafe_allow_html=True)
    render_terminal_log_block("BANKNIFTY", all_df)
    
# SECTION 2: MCX COMMODITIES
st.markdown("<div class='section-header commodity'>🌙 MCX METALS & COMMODITIES MULTI-GRID</div>", unsafe_allow_html=True)
c_col1, c_col2, c_col3, c_col4 = st.columns(4)
with c_col1:
    st.markdown("<div class='asset-title-banner' style='color:#00ffcc;'>🔥 CRUDEOIL</div>", unsafe_allow_html=True)
    render_terminal_log_block("CRUDEOIL", all_df)
with c_col2:
    st.markdown("<div class='asset-title-banner' style='color:#00ffcc;'>🔥 NATURALGAS</div>", unsafe_allow_html=True)
    render_terminal_log_block("NATURALGAS", all_df)
with c_col3:
    st.markdown("<div class='asset-title-banner' style='color:#ffea00;'>🔥 GOLD</div>", unsafe_allow_html=True)
    render_terminal_log_block("GOLD", all_df)
with c_col4:
    st.markdown("<div class='asset-title-banner' style='color:#e0e0e0;'>🔥 SILVER</div>", unsafe_allow_html=True)
    render_terminal_log_block("SILVER", all_df)

# Soft auto-refresh hook to query the local SQLite engine
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
