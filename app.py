import streamlit as st
import pandas as pd
import sqlite3
import os
import pytz
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .stTable, table { width: 100% !important; table-layout: fixed !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.65rem !important; font-weight: bold !important; padding: 6px 4px !important; border-bottom: 2px solid #222634 !important; }
    td { text-align: center !important; font-size: 0.72rem !important; padding: 6px 4px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 15px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Live Order Book Feed Engine | Real-Time Spike Matrix")

DB_FILE = "terminal_history.db"

# -----------------------------------------------------------------------------
# DATABASE HANDLER & NET REFRESH MECHANICS
# -----------------------------------------------------------------------------
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

# Intercept incoming live data pushes directly from your Google Colab loops
query_params = st.query_params
if "action" in query_params and query_params["action"] == "push_spike":
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ledger (timestamp, asset, market_type, expiry, strike, type, quadrant, direction, volume, ltp, delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query_params.get('timestamp', datetime.now().strftime("%H:%M:%S")),
            query_params.get('asset', 'NIFTY').upper(),
            query_params.get('market_type', 'INDEX'),
            query_params.get('expiry', '26DEC'),
            int(query_params.get('strike', 0)),
            query_params.get('type', 'CE').upper(),
            query_params.get('quadrant', 'Instant Spike'),
            query_params.get('direction', '🟢 BULLISH'),
            int(query_params.get('volume', 0)),
            float(query_params.get('ltp', 0.0)),
            query_params.get('delta', '0.0%')
        ))
        conn.commit()
        conn.close()
        st.query_params.clear()  # Clear the address bar query to reset state cleanly
    except Exception as e:
        print(f"Server insertion slip: {e}")

def load_live_spikes_from_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_FILE)
        # ORDER BY id DESC ensures new spikes stack on top immediately
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# GRAPHICAL TERMINAL MATRIX GENERATOR
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;padding-left:10px;'>📡 Awaiting first live order book scrip update from Colab loop...</p>", unsafe_allow_html=True)
        return
        
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.markdown(f"<p style='color:#666;font-size:0.85rem;padding-left:10px;'>Scanning live {asset_filter} order book feeds...</p>", unsafe_allow_html=True)
        return

    rows_html = ""
    for _, r in f_df.iterrows():
        is_bull = "BULLISH" in str(r.get('direction', '')).upper() or "BUY" in str(r.get('quadrant', '')).upper()
        badge_color = "#2ebd85" if is_bull else "#f6465d"
        bg_row_effect = "rgba(46, 189, 133, 0.08)" if is_bull else "rgba(246, 70, 93, 0.08)"
        
        contract_type = str(r.get('type', 'CE')).upper()
        strike_val = int(r.get('strike', 0))
        expiry_lbl = str(r.get('expiry', '26DEC')).replace("Expiry (", "").replace(")", "").upper()
        
        formatted_symbol = f"{asset_filter}{expiry_lbl}{strike_val}{contract_type}"
        vol_amt = int(r.get('volume', 0))
        surge_val = str(r.get('delta', "+0.0%"))
        
        if not surge_val.startswith("+") and not surge_val.startswith("-"):
            surge_val = f"+{surge_val}"

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
    components.html(table_html, height=280, scrolling=True)

# -----------------------------------------------------------------------------
# MAIN APP VIEW DISPATCHER
# -----------------------------------------------------------------------------
@st.fragment(run_every=2) # High speed auto-refresh every 2 seconds
def render_unified_dashboard_grid():
    all_df = load_live_spikes_from_db()
    
    st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE LIVE ACTIVITY RADAR</div>", unsafe_allow_html=True)
    
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.markdown("<div class='asset-title-banner'>🦅 NIFTY INSTANT SURGE LOGGER</div>", unsafe_allow_html=True)
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.markdown("<div class='asset-title-banner'>🦅 BANKNIFTY INSTANT SURGE LOGGER</div>", unsafe_allow_html=True)
        render_terminal_log_block("BANKNIFTY", all_df)

render_unified_dashboard_grid()
