import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
import random
from datetime import datetime
from neo_api_client import NeoAPI

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

# -----------------------------------------------------------------------------
# HIGH-CONTRAST GLOBAL STYLES
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

st.title("⚡ SNY")
st.subheader("QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("---")
st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Live Derivatives Order Book Feed | Explicit Token-Level Contract Routing")

if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

if "token_cache" not in st.session_state:
    st.session_state["token_cache"] = {}

# -----------------------------------------------------------------------------
# ⚙️ USER CONTROL SIDEBAR: DYNAMIC EXPIRY & STRIKE CONFIGURATION
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Active Market Parameters")
    st.caption("Match these EXACTLY to your Kotak Neo app chains to pull true Option LTP.")
    
    st.subheader("National Indices")
    nifty_exp = st.text_input("Nifty Expiry", "23JUN26")
    nifty_strike = st.number_input("Nifty Strike", value=23350, step=50)
    
    bn_exp = st.text_input("BankNifty Expiry", "24JUN26")
    bn_strike = st.number_input("BankNifty Strike", value=50400, step=100)
    
    st.subheader("Equity Options")
    stk_exp = st.text_input("Stock Expiry", "25JUN26")
    rel_strike = st.number_input("Reliance Strike", value=2960, step=20)
    hdfc_strike = st.number_input("HDFCBANK Strike", value=1600, step=10)
    tcs_strike = st.number_input("TCS Strike", value=3850, step=50)
    
    st.subheader("MCX Commodities")
    crude_exp = st.text_input("CrudeOil Expiry", "16JUN26")
    crude_strike = st.number_input("CrudeOil Strike", value=6500, step=100)
    gold_exp = st.text_input("Gold Expiry", "26JUN26")
    gold_strike = st.number_input("Gold Strike", value=72600, step=100)
    
    st.markdown("---")
    test_mode = st.toggle("Enable Weekend Simulation Mode", value=False)

# Compile dynamic asset array based on exact user inputs
ASSETS = {
    "NIFTY":     {"segment": "nse_fo", "strike": int(nifty_strike), "exp": nifty_exp.strip().upper()},
    "BANKNIFTY": {"segment": "nse_fo", "strike": int(bn_strike), "exp": bn_exp.strip().upper()},
    "RELIANCE":  {"segment": "nse_fo", "strike": int(rel_strike), "exp": stk_exp.strip().upper()},
    "HDFCBANK":  {"segment": "nse_fo", "strike": int(hdfc_strike), "exp": stk_exp.strip().upper()},
    "TCS":       {"segment": "nse_fo", "strike": int(tcs_strike), "exp": stk_exp.strip().upper()},
    "CRUDEOIL":  {"segment": "mcx_fo", "strike": int(crude_strike), "exp": crude_exp.strip().upper()},
    "GOLD":      {"segment": "mcx_fo", "strike": int(gold_strike), "exp": gold_exp.strip().upper()}
}

# -----------------------------------------------------------------------------
# AUTOMATED BROKER HANDSHAKE LAYER
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def initialize_broker_connection():
    c_key = os.environ.get("KOTAK_CONSUMER_KEY")
    c_secret = os.environ.get("KOTAK_CONSUMER_SECRET")
    mobile = os.environ.get("KOTAK_MOBILE")
    ucc = os.environ.get("KOTAK_UCC")        
    mpin = os.environ.get("KOTAK_MPIN")
    totp_secret = os.environ.get("KOTAK_TOTP_SECRET")

    if not all([c_key, c_secret, mobile, ucc, mpin, totp_secret]):
        return None

    try:
        api = NeoAPI(environment='prod')
        totp_token = pyotp.TOTP(totp_secret.replace(" ", "")).now()
        api.totp_login(mobile_number=mobile, ucc=ucc, totp=totp_token)
        api.totp_validate(mpin=mpin)
        return api
    except Exception:
        return None

api_client = initialize_broker_connection()

# -----------------------------------------------------------------------------
# TRUE TOKEN-LEVEL DERIVATIVES PROCESSING ENGINE
# -----------------------------------------------------------------------------
def capture_live_ticks():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    
    for symbol, meta in ASSETS.items():
        # Scrape both Calls and Puts for absolute symmetry
        for opt_type in ["CE", "PE"]:
            cache_key = f"{symbol}_{meta['strike']}_{opt_type}_{meta['exp']}"
            inst_token = st.session_state["token_cache"].get(cache_key)
            
            display_symbol = f"{symbol}{meta['exp']}{meta['strike']}{opt_type}"
            ltp = 0.0
            vol = 0
            status = "🔴 OFFLINE / ERR"
            
            if api_client and not test_mode:
                # 1. Search for the exact underlying token using Kotak's native engine
                if not inst_token:
                    try:
                        res = api_client.search_scrip(exchange_segment=meta["segment"], symbol=f"{symbol} {meta['strike']} {opt_type}")
                        if res and isinstance(res, list):
                            for contract in res:
                                trd_sym = str(contract.get("pTrdSymbol", "")).upper()
                                # Pinpoint the exact exact expiry string mapped in the sidebar
                                if meta["exp"] in trd_sym:
                                    inst_token = contract.get("pSymbol")
                                    display_symbol = trd_sym
                                    st.session_state["token_cache"][cache_key] = inst_token
                                    break
                    except:
                        pass
                
                # 2. Extract true Option Premium LTP via verified token string
                if inst_token:
                    try:
                        quote = api_client.get_live_quotes([{"instrument_token": str(inst_token), "exchange_segment": meta["segment"]}])
                        if quote and isinstance(quote, list) and len(quote) > 0:
                            data = quote[0]
                            ltp = float(data.get('last_traded_price', data.get('ltp', 0.0)))
                            vol = int(data.get('volume', data.get('v', 0)))
                            if ltp > 0:
                                status = "🟢 LIVE"
                    except:
                        pass
            
            # 3. Handle specific simulated boundaries safely
            if test_mode and ltp == 0.0:
                ltp = round(random.uniform(45.0, 250.0), 1)
                vol = random.randint(15000, 75000)
                status = "🟡 SIMULATED"
                
            # Render directly into matrix buffer block
            st.session_state["terminal_stream_buffer"].insert(0, {
                "timestamp": ts_string, "asset": symbol,
                "formatted_symbol": display_symbol, 
                "direction": "BULLISH" if opt_type == "CE" else "BEARISH",
                "volume": vol, "ltp": ltp, "status": status
            })

    # Limit buffer limits strictly
    st.session_state["terminal_stream_buffer"] = st.session_state["terminal_stream_buffer"][:80]

capture_live_ticks()
all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])

# -----------------------------------------------------------------------------
# SCREEN RENDER BLOCKS
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        return

    # Render top 4 most recent quote scans
    for _, r in f_df.head(4).iterrows():
        st.info(f"""
        **{r['formatted_symbol']}** [{r['status']}] | Bias: {r['direction']} | Vol: {int(r['volume']):,} | **LTP: ₹{r['ltp']}** | 🕒 {r['timestamp']}
        """)

tab1, tab2, tab3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with tab1:
    st.markdown("#### ⚡ NATIONAL EXCHANGE EQUITY INDICES")
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.error("🦅 NIFTY")
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.error("🦅 BANKNIFTY")
        render_terminal_log_block("BANKNIFTY", all_df)

with tab2:
    st.markdown("#### 📊 HIGH-VOLUME EQUITY STOCK WHALES")
    st_col1, st_col2, st_col3 = st.columns(3)
    with st_col1:
        st.warning("💎 RELIANCE")
        render_terminal_log_block("RELIANCE", all_df)
    with st_col2:
        st.warning("💎 HDFCBANK")
        render_terminal_log_block("HDFCBANK", all_df)
    with st_col3:
        st.warning("💎 TCS")
        render_terminal_log_block("TCS", all_df)

with tab3:
    st.markdown("#### 🛢️ MULTI-COMMODITY EXCHANGE ACTIVE WHALES")
    cmd_col1, cmd_col2 = st.columns(2)
    with cmd_col1:
        st.success("🔥 CRUDEOIL")
        render_terminal_log_block("CRUDEOIL", all_df)
    with cmd_col2:
        st.success("✨ GOLD")
        render_terminal_log_block("GOLD", all_df)

# Auto refresh layout interval map
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
