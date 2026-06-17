import streamlit as st
import pandas as pd
import random
import time
import pytz
from datetime import datetime, timedelta

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

# -----------------------------------------------------------------------------
# GLOBAL NATIVE CONTRAST OVERRIDES
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Force high-contrast background and border rules */
    div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1f2231 !important;
        color: #ffffff !important;
        border-radius: 4px 4px 0px 0px;
        padding: 6px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ff9f43 !important;
        color: #0b0c10 !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# FIXED GLOBAL TOP BRANDING HEADER
# -----------------------------------------------------------------------------
st.columns(1)
st.title("⚡ SNY")
st.subheader("QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("---")

st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
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
        # TAB 2 Assets
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
    direction = "🟢 BULLISH" if contract_type == "CE" else "🔴 BEARISH"
    ltp = round(random.uniform(25.0, 650.0), 1)
    surge_pct = f"+{round(random.uniform(400.0, 1300.0), 1)}%"
    expiry_label = get_expiry_date(symbol, market_type)
    
    return {
        "timestamp": ts_string, "asset": symbol, "market_type": market_type,
        "expiry": expiry_label, "strike": strike, "type": contract_type,
        "direction": direction, "volume": vol_val, "ltp": ltp, "delta": surge_pct
    }

if len(st.session_state["internal_data_buffer"]) == 0:
    for _ in range(15):  
        st.session_state["internal_data_buffer"].append(generate_live_spike())

st.session_state["internal_data_buffer"].insert(0, generate_live_spike())
st.session_state["internal_data_buffer"] = st.session_state["internal_data_buffer"][:40]

all_df = pd.DataFrame(st.session_state["internal_data_buffer"])

# -----------------------------------------------------------------------------
# HIGH-CONTRAST BULLETPROOF DISPLAY RENDERER
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.caption("Awaiting raw data flow...")
        return
        
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.caption(f"Scanning active {asset_filter} blocks...")
        return

    # Render top 4 rows inside clear, readable native layout boxes
    for _, r in f_df.head(4).iterrows():
        formatted_symbol = f"{asset_filter}{r['expiry']}{r['strike']}{r['type']}"
        
        # Native markdown boxes completely ignore skin styling colors and stay high-contrast
        st.info(f"""
        **{formatted_symbol}** Bias: {r['direction']} | Surge: **{r['delta']}** Vol: {int(r['volume']):,} | LTP: ₹{r['ltp']} | 🕒 {r['timestamp']}
        """)

# -----------------------------------------------------------------------------
# RENDER MULTI-TAB WORKSPACE DISPATCHER
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📈 Equity Indices", 
    "📊 Stock Options", 
    "🔥 Commodities"
])

# --- TAB 1: INDICES ---
with tab1:
    st.markdown("#### ⚡ NATIONAL EXCHANGE EQUITY INDICES")
    idx_col1, idx_col2, idx_col3 = st.columns(3)
    with idx_col1:
        st.error("🦅 NIFTY")
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.error("🦅 BANKNIFTY")
        render_terminal_log_block("BANKNIFTY", all_df)
    with idx_col3:
        st.error("🦅 SENSEX")
        render_terminal_log_block("SENSEX", all_df)

# --- TAB 2: STOCK OPTIONS ---
with tab2:
    st.markdown("#### 📊 HIGH-VOLUME EQUITY STOCK WHALES")
    st_col1, st_col2, st_col3, st_col4, st_col5 = st.columns(5)
    with st_col1:
        st.warning("💎 RELIANCE")
        render_terminal_log_block("RELIANCE", all_df)
    with st_col2:
        st.warning("💎 HDFCBANK")
        render_terminal_log_block("HDFCBANK", all_df)
    with st_col3:
        st.warning("💎 ICICIBANK")
        render_terminal_log_block("ICICIBANK", all_df)
    with st_col4:
        st.warning("💎 TCS")
        render_terminal_log_block("TCS", all_df)
    with st_col5:
        st.warning("💎 INFY")
        render_terminal_log_block("INFY", all_df)

# --- TAB 3: COMMODITIES ---
with tab3:
    st.markdown("#### 🌙 MCX METALS & COMMODITIES SWEEPS")
    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    with c_col1:
        st.success("🔥 CRUDEOIL")
        render_terminal_log_block("CRUDEOIL", all_df)
    with c_col2:
        st.success("🔥 NATURALGAS")
        render_terminal_log_block("NATURALGAS", all_df)
    with c_col3:
        st.success("🔥 GOLD")
        render_terminal_log_block("GOLD", all_df)
    with c_col4:
        st.success("🔥 SILVER")
        render_terminal_log_block("SILVER", all_df)

# Direct page refresh injection pass every 4 seconds
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 4000);</script></body></html>",
    height=0, width=0
)
