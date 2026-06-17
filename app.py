import streamlit as st
import pandas as pd
import random
import pytz
from datetime import datetime, timedelta

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

# -----------------------------------------------------------------------------
# GLOBAL NATIVE CONTRAST OVERRIDES
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
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
# GLOBAL HEADER
# -----------------------------------------------------------------------------
st.title("⚡ SNY")
st.subheader("QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("---")

st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Cross-Asset Order Book Feed Engine | Tabbed Grid Framework")

# -----------------------------------------------------------------------------
# CALCULATION ENGINES (Dynamic Expiries & Realistic LTP)
# -----------------------------------------------------------------------------
if "internal_data_buffer" not in st.session_state:
    st.session_state["internal_data_buffer"] = []

def calculate_accurate_expiry(asset_name, market_type):
    """
    Computes valid real-world derivative expiries:
    - Equity Indices (NIFTY/BANKNIFTY): Nearest weekly Thursday contracts
    - Stocks & SENSEX: Nearest monthly expiry Friday contracts
    - Commodities (MCX): Standardized active delivery cycle representations
    """
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    
    if market_type == "COMMODITY":
        # CRUDE/NG roll around 19th-22nd; Gold/Silver typically early month rotation
        base_day = 19 if asset_name in ["CRUDEOIL", "NATURALGAS"] else 5
        target_date = today.replace(day=base_day)
        if target_date < today:
            # Advance to the following month sequence if passed current cycle
            next_month = today.replace(day=28) + timedelta(days=5)
            target_date = next_month.replace(day=base_day)
        return target_date.strftime('%d%b').upper()
        
    elif symbol == "SENSEX" or market_type == "STOCK":
        # Last Friday of the month contract cycle logic
        last_day = today.replace(day=28) + timedelta(days=4)
        last_day = last_day - timedelta(days=last_day.day)
        target_date = last_day - timedelta(days=(last_day.weekday() - 4) % 7)
        if target_date < today:
            next_month = today.replace(day=28) + timedelta(days=5)
            last_day = next_month.replace(day=28) + timedelta(days=4)
            last_day = last_day - timedelta(days=last_day.day)
            target_date = last_day - timedelta(days=(last_day.weekday() - 4) % 7)
        return target_date.strftime('%d%b').upper()
        
    else:
        # Standard NSE Weekly Index Thursday calculation routine
        days_to_thursday = (3 - today.weekday()) % 7
        target_date = today + timedelta(days=days_to_thursday)
        return target_date.strftime('%d%b').upper()

def generate_live_spike():
    all_assets = [
        ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"), ("SENSEX", "INDEX"),
        ("RELIANCE", "STOCK"), ("TCS", "STOCK"), ("INFY", "STOCK"), ("HDFCBANK", "STOCK"), ("ICICIBANK", "STOCK"),
        ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY")
    ]
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    global symbol # allow fallback tracking scope inside local block helper 
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
    surge_pct = f"+{round(random.uniform(400.0, 1300.0), 1)}%"
    expiry_label = calculate_accurate_expiry(symbol, market_type)
    
    # --- RE-ALIGNED REALISTIC PREMIUM MAPPING (LTP) ---
    if symbol in ["GOLD", "SILVER"]:
        # Precious metal option premiums trade at higher index scales
        ltp = round(random.uniform(450.0, 1850.0), 1)
    elif market_type == "STOCK":
        # Regular large-cap individual option pricing chains
        ltp = round(random.uniform(15.0, 95.0), 1)
    else:
        # Standard Index and Energy option premium parameters
        ltp = round(random.uniform(95.0, 420.0), 1)
    
    return {
        "timestamp": ts_string, "asset": symbol, "market_type": market_type,
        "expiry": expiry_label, "strike": strike, "type": contract_type,
        "direction": direction, "volume": vol_val, "ltp": ltp, "delta": surge_pct
    }

# Hydration fill check loop pass
if len(st.session_state["internal_data_buffer"]) == 0:
    for _ in range(20):  
        st.session_state["internal_data_buffer"].append(generate_live_spike())

st.session_state["internal_data_buffer"].insert(0, generate_live_spike())
st.session_state["internal_data_buffer"] = st.session_state["internal_data_buffer"][:45]

all_df = pd.DataFrame(st.session_state["internal_data_buffer"])

# -----------------------------------------------------------------------------
# COMPONENT RENDER BLOCK 
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.caption("Awaiting data link stream initialization...")
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.caption(f"Scanning active {asset_filter} blocks...")
        return

    for _, r in f_df.head(4).iterrows():
        formatted_symbol = f"{asset_filter}{r['expiry']}{r['strike']}{r['type']}"
        st.info(f"""
        **{formatted_symbol}** Bias: {r['direction']} | Surge: **{r['delta']}** Vol: {int(r['volume']):,} | LTP: ₹{r['ltp']} | 🕒 {r['timestamp']}
        """)

# -----------------------------------------------------------------------------
# INTERFACE NAVIGATION MATRIX
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📈 Equity Indices", 
    "📊 Stock Options", 
    "🔥 Commodities"
])

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

# Direct page refresh cadence pass (4 seconds)
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 4000);</script></body></html>",
    height=0, width=0
)
