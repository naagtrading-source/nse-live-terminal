import streamlit as st
import pandas as pd
import random
import time
import pytz
from datetime import datetime, timedelta
import streamlit.components.v1 as components

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    
    /* Global SNY Top Header Styling */
    .global-top-header {
        background: linear-gradient(90deg, #1f2231 0%, #141722 100%);
        padding: 12px 24px;
        border-radius: 6px;
        margin-bottom: 20px;
        border-bottom: 3px solid #ff9f43;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .brand-title {
        color: #ffffff;
        font-family: 'Montserrat', sans-serif;
        font-size: 1.8rem;
        font-weight: 900;
        letter-spacing: 3px;
        margin: 0;
        text-shadow: 0 0 10px rgba(255,159,67,0.3);
    }
    .brand-sub {
        color: #ff9f43;
        font-family: monospace;
        font-size: 0.75rem;
        font-weight: bold;
    }
    
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 10px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .section-header.stocks { color: #512da8; border-left: 4px solid #7c4dff; }
    .section-header.commodity { color: #00ffcc; border-left: 4px solid #00ffcc; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    
    /* Responsive Fluid Layout Rows */
    .ticker-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        margin-bottom: 4px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.75rem;
        gap: 10px;
    }
    .col-left { display: flex; flex-direction: column; align-items: flex-start; min-width: 0; }
    .col-right { display: flex; flex-direction: column; align-items: flex-end; text-align: right; min-width: max-content; }
    
    .symbol-txt { color: #ff9f43; font-weight: 900; font-size: 0.82rem; word-break: break-all; }
    .meta-txt { color: #a0a5b5; font-size: 0.65rem; }
    .vol-txt { color: #ffffff; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# GLOBAL TOP BRANDING BANNER
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="global-top-header">
        <h1 class="brand-title">SNY</h1>
        <div class="brand-sub">QUANTITATIVE ALGORITHMIC ROUTING ENGINE</div>
    </div>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Cross-Asset Order Book Feed Engine | Tabbed Grid Framework")

# -----------------------------------------------------------------------------
# INTERNAL CORE MEMORY GENERATOR ENGINE
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
        # TAB 1 Assets
        ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"), ("SENSEX", "INDEX"),
        # TAB 2 Assets (Nifty 50 Heavies)
        ("RELIANCE", "STOCK"), ("TCS", "STOCK"), ("INFY", "STOCK"), ("HDFCBANK", "STOCK"), ("ICICIBANK", "STOCK"),
        # TAB 3 Assets
        ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY")
    ]
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    symbol, market_type = random.choice(all_assets)
    
    fallback = {
        "NIFTY": 23350, "BANKNIFTY": 50300, "SENSEX": 76800,
        "RELIANCE": 2950, "TCS": 3850, "INFY": 1500, "HDFCBANK": 1600, "ICICIBANK": 1150,
        "CRUDEOIL": 6500, "NATURALGAS": 225, "GOLD": 72600, "SILVER": 88500
    }
    spot = fallback.get(symbol, 100.0)
    step = 50 if symbol == "NIFTY" else 100 if symbol in ["BANKNIFTY","CRUDEOIL","GOLD"] else 250 if symbol in ["SILVER","SENSEX"] else 20
    
    atm = round(spot / step) * step
    strike = int(atm + (random.choice([-1, 0, 1]) * step))
    vol_val = random.randint(65000, 130000) if market_type == "INDEX" else random.randint(10000, 45000)
    
    contract_type = random.choice(["CE", "PE"])
    quadrant = "Call Buying Flow" if contract_type == "CE" else "Put Buying Sweep"
    direction = "🟢 BULLISH" if contract_type == "CE" else "🔴 BEARISH"
    ltp = round(random.uniform(25.0, 650.0), 1)
    surge_pct = f"+{round(random.uniform(400.0, 1300.0), 1)}%"
    expiry_label = get_expiry_date(symbol, market_type)
    
    return {
        "timestamp": ts_string, "asset": symbol, "market_type": market_type,
        "expiry": expiry_label, "strike": strike, "type": contract_type,
        "quadrant": quadrant, "direction": direction, "volume": vol_val,
        "ltp": ltp, "delta": surge_pct
    }

if len(st.session_state["internal_data_buffer"]) == 0:
    for _ in range(12):  
        st.session_state["internal_data_buffer"].append(generate_live_spike())

st.session_state["internal_data_buffer"].insert(0, generate_live_spike())
st.session_state["internal_data_buffer"] = st.session_state["internal_data_buffer"][:60]

all_df = pd.DataFrame(st.session_state["internal_data_buffer"])

# -----------------------------------------------------------------------------
# CORE FLEXBOX CELL DRAWER ENGINE
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;padding-left:10px;'>Awaiting raw data flow...</p>", unsafe_allow_html=True)
        return
        
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.markdown(f"<p style='color:#666;font-size:0.85rem;padding-left:10px;'>Scanning active {asset_filter} blocks...</p>", unsafe_allow_html=True)
        return

    rows_html = ""
    for _, r in f_df.iterrows():
        is_bull = "BULLISH" in str(r.get('direction', '')).upper() or "BUY" in str(r.get('quadrant', '')).upper()
        badge_color = "#2ebd85" if is_bull else "#f6465d"
        bg_row_effect = "rgba(46, 189, 133, 0.06)" if is_bull else "rgba(246, 70, 93, 0.06)"
        
        formatted_symbol = f"{asset_filter}{r['expiry']}{r['strike']}{r['type']}"
        vol_amt = int(r.get('volume', 0))

        rows_html += f"""
        <div class="ticker-row" style="background-color: {bg_row_effect}; border-left: 3px solid {badge_color};">
            <div class="col-left">
                <span class="symbol-txt">{formatted_symbol}</span>
                <span class="meta-txt">🕒 {r['timestamp']} | 🚨 INSTANT SPIKE</span>
            </div>
            <div class="col-right">
                <span style="color: {badge_color}; font-weight: bold;">{r['delta']}</span>
                <span class="vol-txt">V: {vol_amt:,}</span>
                <span class="meta-txt">LTP: {round(float(r.get('ltp', 0.0)), 1)}</span>
            </div>
        </div>"""
        
    final_html = f"""
    <html><head><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'></head>
    <body style='background-color: #0b0c10; padding:0; margin:0; overflow-x:hidden;'>
        <div style="display: flex; flex-direction: column; gap: 4px; padding: 2px;">{rows_html}</div>
    </body></html>
    """
    components.html(final_html, height=240, scrolling=True)

# -----------------------------------------------------------------------------
# RENDER MULTI-TAB WORKSPACE DISPATCHER
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📈 Equity Indices (NIFTY / BANKNIFTY / SENSEX)", 
    "📊 Nifty 50 Stock Options Heavyweights", 
    "🔥 Commodities Options & Futures (MCX)"
])

# --- TAB 1: INDICES ---
with tab1:
    st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE EQUITY INDICES</div>", unsafe_allow_html=True)
    idx_col1, idx_col2, idx_col3 = st.columns(3)
    with idx_col1:
        st.markdown("<div class='asset-title-banner'>🦅 NIFTY</div>", unsafe_allow_html=True)
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.markdown("<div class='asset-title-banner'>🦅 BANKNIFTY</div>", unsafe_allow_html=True)
        render_terminal_log_block("BANKNIFTY", all_df)
    with idx_col3:
        st.markdown("<div class='asset-title-banner'>🦅 SENSEX</div>", unsafe_allow_html=True)
        render_terminal_log_block("SENSEX", all_df)

# --- TAB 2: STOCK OPTIONS ---
with tab2:
    st.markdown("<div class='section-header stocks'>📊 HIGH-VOLUME EQUITY STOCK WHALES</div>", unsafe_allow_html=True)
    st_col1, st_col2, st_col3, st_col4, st_col5 = st.columns(5)
    with st_col1:
        st.markdown("<div class='asset-title-banner' style='color:#7c4dff;'>💎 RELIANCE</div>", unsafe_allow_html=True)
        render_terminal_log_block("RELIANCE", all_df)
    with st_col2:
        st.markdown("<div class='asset-title-banner' style='color:#7c4dff;'>💎 HDFCBANK</div>", unsafe_allow_html=True)
        render_terminal_log_block("HDFCBANK", all_df)
    with st_col3:
        st.markdown("<div class='asset-title-banner' style='color:#7c4dff;'>💎 ICICIBANK</div>", unsafe_allow_html=True)
        render_terminal_log_block("ICICIBANK", all_df)
    with st_col4:
        st.markdown("<div class='asset-title-banner' style='color:#7c4dff;'>💎 TCS</div>", unsafe_allow_html=True)
        render_terminal_log_block("TCS", all_df)
    with st_col5:
        st.markdown("<div class='asset-title-banner' style='color:#7c4dff;'>💎 INFY</div>", unsafe_allow_html=True)
        render_terminal_log_block("INFY", all_df)

# --- TAB 3: COMMODITIES ---
with tab3:
    st.markdown("<div class='section-header commodity'>🌙 MCX METALS & COMMODITIES SWEEPS</div>", unsafe_allow_html=True)
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

# Soft automatic page sync trigger (3 seconds cadence check)
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
