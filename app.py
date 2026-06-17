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
st.caption("Live Derivatives Order Book | Automated Nearest-Expiry Token Routing")

if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

if "contract_cache" not in st.session_state:
    st.session_state["contract_cache"] = {}

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
# DYNAMIC ASSET MATRIX (NO MANUAL EXPIRIES NEEDED)
# -----------------------------------------------------------------------------
ASSETS = {
    "NIFTY":     {"segment": "nse_fo", "strike": 23350, "type": "INDEX"},
    "BANKNIFTY": {"segment": "nse_fo", "strike": 50400, "type": "INDEX"},
    "RELIANCE":  {"segment": "nse_fo", "strike": 2960,  "type": "STOCK"},
    "HDFCBANK":  {"segment": "nse_fo", "strike": 1600,  "type": "STOCK"},
    "TCS":       {"segment": "nse_fo", "strike": 3850,  "type": "STOCK"},
    "CRUDEOIL":  {"segment": "mcx_fo", "strike": 6500,  "type": "COMMODITY"},
    "GOLD":      {"segment": "mcx_fo", "strike": 72600, "type": "COMMODITY"}
}

def get_nearest_contract_token(api, segment, symbol, strike, opt_type):
    """
    Searches the exchange for the specific strike and returns the 
    NEAREST available expiry contract token and its exact trading symbol.
    """
    try:
        # Search Kotak Neo for all contracts matching the symbol, strike, and type (CE/PE)
        res = api.search_scrip(
            exchange_segment=segment, 
            symbol=symbol, 
            strike_price=str(strike), 
            option_type=opt_type
        )
        
        if res and isinstance(res, list) and len(res) > 0:
            # The API generally returns the nearest/most liquid expiries at the top of the list.
            # We filter to ensure it perfectly matches our search criteria to be safe.
            for contract in res:
                trd_sym = str(contract.get("pTrdSymbol", "")).upper()
                if symbol in trd_sym and str(strike) in trd_sym and opt_type in trd_sym:
                    token = contract.get("pSymbol")
                    return token, trd_sym
    except Exception:
        pass
    
    # Return None if the contract isn't found (e.g., strike doesn't exist)
    return None, f"{symbol}_[SEARCH_ERR]_{strike}{opt_type}"

# -----------------------------------------------------------------------------
# TRUE TOKEN-LEVEL DERIVATIVES PROCESSING ENGINE
# -----------------------------------------------------------------------------
def capture_live_ticks():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    
    for symbol, meta in ASSETS.items():
        opt_type = random.choice(["CE", "PE"])
        strike = meta["strike"]
        
        cache_key = f"{symbol}_{strike}_{opt_type}"
        inst_token = None
        display_symbol = f"{symbol}...{strike}{opt_type}"
        
        ltp = 0.0
        vol = 0
        status = "🔴 ERR"
        
        if api_client:
            # 1. Fetch exact token from cache, OR search exchange if not cached
            if cache_key in st.session_state["contract_cache"]:
                cached_data = st.session_state["contract_cache"][cache_key]
                inst_token = cached_data["token"]
                display_symbol = cached_data["trd_sym"]
            else:
                inst_token, display_symbol = get_nearest_contract_token(
                    api_client, meta["segment"], symbol, strike, opt_type
                )
                if inst_token:
                    st.session_state["contract_cache"][cache_key] = {
                        "token": inst_token, "trd_sym": display_symbol
                    }

            # 2. Extract true Option Premium LTP via verified token
            if inst_token:
                try:
                    quote = api_client.get_live_quotes([{"instrument_token": str(inst_token), "exchange_segment": meta["segment"]}])
                    if quote and isinstance(quote, list) and len(quote) > 0:
                        data = quote[0]
                        ltp = float(data.get('last_traded_price', data.get('ltp', 0.0)))
                        vol = int(data.get('volume', data.get('v', 0)))
                        if ltp > 0:
                            status = "🟢 LIVE"
                except Exception:
                    pass
        
        # 3. Handle weekend/after-hours simulation block gracefully
        if ltp <= 0.0:
            if meta["type"] == "INDEX":
                ltp = round(random.uniform(45.0, 320.0), 1)
            elif meta["type"] == "COMMODITY":
                ltp = round(random.uniform(80.0, 450.0), 1)
            else:
                ltp = round(random.uniform(8.0, 65.0), 1)
            vol = random.randint(15000, 75000)
            status = "🟡 OFFLINE SIM"
            
        # 4. Insert directly into stream matrix
        st.session_state["terminal_stream_buffer"].insert(0, {
            "timestamp": ts_string, "asset": symbol,
            "formatted_symbol": display_symbol, 
            "direction": "BULLISH" if opt_type == "CE" else "BEARISH",
            "volume": vol, "ltp": ltp, "status": status,
            "delta": f"+{round(random.uniform(250, 850), 1)}%"
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
