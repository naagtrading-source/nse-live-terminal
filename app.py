import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
from datetime import datetime
from neo_api_client import NeoAPI

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

# -----------------------------------------------------------------------------
# HIGH-CONTRAST TERMINAL STYLES
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
st.caption("Pure Real-Time Exchange Pipeline | Direct Token Intercept Verification")

if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

if "scrip_cache" not in st.session_state:
    st.session_state["scrip_cache"] = {}

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
        return "MISSING_ENV_VARS"

    try:
        api = NeoAPI(environment='prod')
        totp_token = pyotp.TOTP(totp_secret.replace(" ", "")).now()
        api.totp_login(mobile_number=mobile, ucc=ucc, totp=totp_token)
        api.totp_validate(mpin=mpin)
        return api
    except Exception as e:
        return f"AUTH_ERROR: {str(e)}"

api_client = initialize_broker_connection()

# Check and output connection matrix issues directly to user
if isinstance(api_client, str):
    if api_client == "MISSING_ENV_VARS":
        st.error("⚠️ Setup Error: Environment variables are missing inside your Render panel control.")
    else:
        st.error(f"🔴 Kotak API Authentication Failed: {api_client}")
    st.info("💡 Terminal is currently locked. Verify your KOTAK_TOTP_SECRET and UCC Client Code parameters.")
    st.stop()

# -----------------------------------------------------------------------------
# DYNAMIC REAL-TIME ROUTING CONFIGURATIONS
# -----------------------------------------------------------------------------
ASSET_ROUTING = {
    "NIFTY":     {"fo_seg": "nse_fo", "underlying_is_fut": True,  "step": 50},
    "BANKNIFTY": {"fo_seg": "nse_fo", "underlying_is_fut": True,  "step": 100},
    "RELIANCE":  {"fo_seg": "nse_fo", "underlying_is_fut": False, "step": 20,  "cm_seg": "nse_cm"},
    "HDFCBANK":  {"fo_seg": "nse_fo", "underlying_is_fut": False, "step": 10,  "cm_seg": "nse_cm"},
    "TCS":       {"fo_seg": "nse_fo", "underlying_is_fut": False, "step": 50,  "cm_seg": "nse_cm"},
    "CRUDEOIL":  {"fo_seg": "mcx_fo", "underlying_is_fut": True,  "step": 100},
    "GOLD":      {"fo_seg": "mcx_fo", "underlying_is_fut": True,  "step": 100}
}

# -----------------------------------------------------------------------------
# AUTHENTIC EXCHANGE FETCH CHANNEL
# -----------------------------------------------------------------------------
def capture_true_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    
    current_snapshot = []

    for symbol, meta in ASSET_ROUTING.items():
        underlying_price = 0.0
        scrip_records = []
        
        # Pull Master Scrip data lists natively from connection instance
        try:
            res = api_client.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
            if res and isinstance(res, dict) and 'data' in res:
                scrip_records = res['data']
            elif isinstance(res, list):
                scrip_records = res
        except:
            scrip_records = []

        if not scrip_records:
            continue

        # 1. FETCH LIVE UNDERLYING ANCHOR PRICE (No hardcoded maps)
        try:
            if meta["underlying_is_fut"]:
                # Match the nearest front-month standard Future contract price for index and commodity anchors
                for item in scrip_records:
                    trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                    if "FUT" in trd_sym:
                        token = item.get("pSymbol", item.get("token"))
                        q = api_client.get_live_quotes([{"instrument_token": str(token), "exchange_segment": meta["fo_seg"]}])
                        if q and isinstance(q, list):
                            underlying_price = float(q[0].get('last_traded_price', q[0].get('ltp', 0.0)))
                        break
            else:
                # For cash stocks, resolve the exact underlying asset inside the cash market slice
                res_cm = api_client.search_scrip(exchange_segment=meta["cm_seg"], symbol=symbol)
                records_cm = res_cm.get('data', []) if isinstance(res_cm, dict) else res_cm
                for item in records_cm:
                    if str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper() == f"{symbol}-EQ":
                        token = item.get("pSymbol", item.get("token"))
                        q = api_client.get_live_quotes([{"instrument_token": str(token), "exchange_segment": meta["cm_seg"]}])
                        if q and isinstance(q, list):
                            underlying_price = float(q[0].get('last_traded_price', q[0].get('ltp', 0.0)))
                        break
        except:
            underlying_price = 0.0

        if underlying_price <= 0.0:
            # If exchange returns zero, skip displaying fake data entirely
            continue

        # 2. DYNAMICALLY MAP AT-THE-MONEY (ATM) STRIKE ZONES
        atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
        target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]

        # 3. INTERCEPT AND PARSE OPTIONS CONTRACT INFORMATION
        for item in scrip_records:
            try:
                trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                strike_val = int(float(item.get("pStrikePrice", item.get("strkPrc", 0))))
                opt_type = str(item.get("pOptionType", item.get("optTp", ""))).upper()
                token_id = item.get("pSymbol", item.get("token"))

                # Filter out far strikes to track only immediate high-density block action
                if strike_val in target_strikes and opt_type in ["CE", "PE", "CALL", "PUT"]:
                    q_opt = api_client.get_live_quotes([{"instrument_token": str(token_id), "exchange_segment": meta["fo_seg"]}])
                    
                    if q_opt and isinstance(q_opt, list) and len(q_opt) > 0:
                        ltp = float(q_opt[0].get('last_traded_price', q_opt[0].get('ltp', 0.0)))
                        vol = int(q_opt[0].get('volume', q_opt[0].get('v', 0)))
                        
                        current_snapshot.append({
                            "timestamp": ts_string, "asset": symbol, "formatted_symbol": trd_sym,
                            "direction": "INSTITUTIONAL CALL ACCUMULATION" if "C" in opt_type else "INSTITUTIONAL PUT DISTRIBUTION",
                            "volume": vol, "ltp": ltp, "underlying": underlying_price
                        })
            except:
                pass

    if current_snapshot:
        st.session_state["terminal_stream_buffer"] = current_snapshot

capture_true_market_state()
all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])

# -----------------------------------------------------------------------------
# SCREEN RENDER GRAPHICS
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.caption("🔴 Awaiting Live Transmission (Confirm your broker API is connected and market is open)...")
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.caption("Searching live contract matrices...")
        return

    top_record = f_df.iloc[0]
    st.metric(label="Live Underlying Anchor Price", value=f"₹{top_record['underlying']:,}")
    
    for _, r in f_df.head(3).iterrows():
        st.info(f"""
        **{r['formatted_symbol']}** | Matrix: **{r['direction']}** | Vol: {int(r['volume']):,} | **Premium LTP: ₹{r['ltp']}** | 🕒 {r['timestamp']}
        """)

tab1, tab2, tab3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with tab1:
    st.markdown("#### ⚡ EXCHANGE REGISTERED DERIVATIVE INDICES")
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.error("🦅 NIFTY RADAR")
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.error("🦅 BANKNIFTY RADAR")
        render_terminal_log_block("BANKNIFTY", all_df)

with tab2:
    st.markdown("#### 📊 HIGH-LIQUIDITY EQUITIES WHALE RADAR")
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
    st.markdown("#### 🛢️ MULTI-COMMODITY EXCHANGE BLOCK SURGES")
    cmd_col1, cmd_col2 = st.columns(2)
    with cmd_col1:
        st.success("🔥 CRUDEOIL")
        render_terminal_log_block("CRUDEOIL", all_df)
    with cmd_col2:
        st.success("✨ GOLD")
        render_terminal_log_block("GOLD", all_df)

# Auto refresh page content loop frame interval every 3 seconds
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
