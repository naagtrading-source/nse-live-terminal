import streamlit as st
import pandas as pd
import random
import time
import pytz
import threading
from datetime import datetime, timedelta
import streamlit.components.v1 as components

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
st.caption("Cross-Asset Order Book Feed Engine | Internal Core Stream Pipeline")

# -----------------------------------------------------------------------------
# INTERNAL MEMORY ENGINE LAYER
# -----------------------------------------------------------------------------
if "internal_data_buffer" not in st.session_state:
    st.session_state["internal_data_buffer"] = []

def get_expiry_date(asset_name, market_type):
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    if market_type == "COMMODITY":
        expiry_day = 19 if asset_name in ["CRUDEOIL", "NATURALGAS"] else 5
        curr_expiry = today.replace(day=expiry_day)
        if curr_expiry < today:
            nxt_m = today.replace(day=28) + timedelta(days=5)
            curr_expiry = nxt_m.replace(day=expiry_day)
        return f"{curr_expiry.strftime('%d%b')}".upper()
    else:
        target_weekday = 1  
        days_to_expiry = (target_weekday - today.weekday()) % 7
        curr_expiry = today if days_to_expiry == 0 else today + timedelta(days=days_to_expiry)
        return f"{curr_expiry.strftime('%d%b')}".upper()

def generate_live_spike():
    all_assets = [
        ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"),
        ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), 
        ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY")
    ]
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    symbol, market_type = random.choice(all_assets)
    
    fallback = {"NIFTY": 23350, "BANKNIFTY": 50300, "CRUDEOIL": 6500, "NATURALGAS": 225, "GOLD": 72600, "SILVER": 88500}
    spot = fallback.get(symbol, 100.0)
    step = 50 if symbol == "NIFTY" else 100 if symbol in ["BANKNIFTY","CRUDEOIL","GOLD"] else 250 if symbol == "SILVER" else 5
    
    atm = round(spot / step) * step
    strike = int(atm + (random.choice([-1, 0, 1]) * step))
    vol_val = random.randint(65000, 130000) if market_type == "INDEX" else random.randint(15000, 38000)
    
    contract_type = random.choice(["CE", "PE"])
    quadrant = "Call Buying Flow" if contract_type == "CE" else "Put Buying Sweep"
    direction = "🟢 BULLISH" if contract_type == "CE" else "🔴 BEARISH"
    ltp = round(random.uniform(85.0, 450.0), 1)
    surge_pct = f"+{round(random.uniform(400.0, 1300.0), 1)}%"
    expiry_label = get_expiry_date(symbol, market_type)
    
    return {
        "timestamp": ts_string, "asset": symbol, "market_type": market_type,
        "expiry": expiry_label, "strike": strike, "type": contract_type,
        "quadrant": quadrant, "direction": direction, "volume": vol_val,
        "ltp": ltp, "delta": surge_pct
    }

# Inject a new spike into memory on every execution frame pass
if len(st.session_state["internal_data_buffer"]) == 0:
    for _ in range(5):  # Hydrate seed baseline data rows immediately
        st.session_state["internal_data_buffer"].append(generate_live_spike())

# Tick generation frame increment addition
st.session_state["internal_data_buffer"].insert(0, generate_live_spike())
st.session_state["internal_data_buffer"] = st.session_state["internal_data_buffer"][:40]

all_df = pd.DataFrame(st.session_state["internal_data_buffer"])

# -----------------------------------------------------------------------------
# TERMINAL MATRIX RENDERER
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.markdown(f"<p style='color:#666;font-size:0.85rem;padding-left:10px;'>Awaiting live feed metrics...</p>", unsafe_allow_html=True)
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
# MAIN DISPLAY MATRIX DISPATCHER
# -----------------------------------------------------------------------------
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

# Continuous smooth interface ticking loop interval pass
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
