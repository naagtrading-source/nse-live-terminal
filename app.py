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
st.caption("Isolated Segment Allocation Engine | Live-Streaming Active Exchange Pipeline")

if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

if "scrip_master_cache" not in st.session_state:
    st.session_state["scrip_master_cache"] = {}

# -----------------------------------------------------------------------------
# AUTOMATED DIAGNOSTIC BROKER HANDSHAKE
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def initialize_broker_connection():
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    missing_keys = [key for key in required_keys if not os.environ.get(key)]
    
    if missing_keys:
        return f"MISSING: {', '.join(missing_keys)}"

    try:
        api = NeoAPI(
            environment='prod',
            consumer_key=os.environ.get("KOTAK_CONSUMER_KEY")
        )
        totp_secret = os.environ.get("KOTAK_TOTP_SECRET").replace(" ", "")
        totp_token = pyotp.TOTP(totp_secret).now()
        
        api.totp_login(
            mobile_number=os.environ.get("KOTAK_MOBILE"), 
            ucc=os.environ.get("KOTAK_UCC"), 
            totp=totp_token
        )
        api.totp_validate(mpin=os.environ.get("KOTAK_MPIN"))
        return api
    except Exception as e:
        return f"AUTH_ERROR: {str(e)}"

api_client = initialize_broker_connection()

if isinstance(api_client, str) and api_client.startswith("MISSING:"):
    st.error(f"⚠️ Configuration Error: The following variables are missing from Render: {api_client.replace('MISSING:', '')}")
    st.stop()

# -----------------------------------------------------------------------------
# DYNAMIC REAL-TIME SEGMENT ROUTING MAPS
# -----------------------------------------------------------------------------
ASSET_ROUTING = {
    "NIFTY":     {"fo_seg": "nse_fo", "is_fut": True,  "step": 50,  "base": 23450, "exp": "23JUN26"},
    "BANKNIFTY": {"fo_seg": "nse_fo", "is_fut": True,  "step": 100, "base": 50600, "exp": "30JUN26"},
    "RELIANCE":  {"fo_seg": "nse_fo", "is_fut": False, "step": 20,  "base": 2980,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "HDFCBANK":  {"fo_seg": "nse_fo", "is_fut": False, "step": 10,  "base": 1610,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "TCS":       {"fo_seg": "nse_fo", "is_fut": False, "step": 50,  "base": 3850,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "CRUDEOIL":  {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 6550,  "exp": "17JUL26"},
    "GOLD":      {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 72800, "exp": "30JUN26"}
}

def capture_true_isolated_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    current_snapshot = []

    for symbol, meta in ASSET_ROUTING.items():
        asset_live_fetched = False
        scrip_records = []
        
        # Pull or read token map structures out of persistent RAM caching layer
        if symbol in st.session_state["scrip_master_cache"]:
            scrip_records = st.session_state["scrip_master_cache"][symbol]
        elif hasattr(api_client, 'search_scrip'):
            try:
                res = api_client.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
                scrip_records = res.get('data', []) if isinstance(res, dict) else res
                if scrip_records:
                    st.session_state["scrip_master_cache"][symbol] = scrip_records
            except:
                scrip_records = []

        underlying_price = 0.0
        
        # 1. Fetch live transaction index markers from the broker connection
        if scrip_records and not isinstance(api_client, str):
            try:
                if meta["is_fut"]:
                    for item in scrip_records:
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                        if "FUT" in trd_sym:
                            token = item.get("pSymbol", item.get("token"))
                            q = api_client.get_live_quotes([{"instrument_token": str(token), "exchange_segment": meta["fo_seg"]}])
                            if q and isinstance(q, list):
                                underlying_price = float(q[0].get('last_traded_price', q[0].get('ltp', 0.0)))
                            break
                else:
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

        # 2. Process real-time option chain if underlying pricing registers above zero bounds
        if underlying_price > 0.0:
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]
            
            options_added = 0
            for item in scrip_records:
                try:
                    trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                    strike_val = int(float(item.get("pStrikePrice", item.get("strkPrc", 0))))
                    opt_type = str(item.get("pOptionType", item.get("optTp", ""))).upper()
                    token_id = item.get("pSymbol", item.get("token"))

                    if strike_val in target_strikes and opt_type in ["CE", "PE", "CALL", "PUT"]:
                        q_opt = api_client.get_live_quotes([{"instrument_token": str(token_id), "exchange_segment": meta["fo_seg"]}])
                        if q_opt and isinstance(q_opt, list) and len(q_opt) > 0:
                            ltp = float(q_opt[0].get('last_traded_price', q_opt[0].get('ltp', 0.0)))
                            vol = int(q_opt[0].get('volume', q_opt[0].get('v', 0)))
                            
                            if ltp > 0:
                                current_snapshot.append({
                                    "timestamp": ts_string, "asset": symbol, "formatted_symbol": trd_sym,
                                    "direction": "CALL ACCUMULATION" if "C" in opt_type else "PUT DISTRIBUTION",
                                    "volume": vol, "ltp": ltp, "underlying": underlying_price, "status": "🟢 LIVE SPEED"
                                })
                                options_added += 1
                except:
                    pass
            if options_added > 0:
                asset_live_fetched = True

        # 3. FIXED: Run off-hours sandbox rendering ONLY for individual dead segments (e.g., closed equities)
        if not asset_live_fetched:
            underlying_price = meta["base"] + round(random.uniform(-10, 10), 1)
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]
            
            for strike in target_strikes:
                for opt in ["CE", "PE"]:
                    display_symbol = f"{symbol}{meta['exp']}{strike}{opt}"
                    ltp = round(random.uniform(40.0, 260.0), 1) if symbol in ["NIFTY", "BANKNIFTY"] else round(random.uniform(6.0, 65.0), 1)
                    vol = random.randint(15000, 125000)
                    
                    current_snapshot.append({
                        "timestamp": ts_string, "asset": symbol, "formatted_symbol": display_symbol,
                        "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                        "volume": vol, "ltp": ltp, "underlying": underlying_price, "status": "🌙 OFF-HOURS FALLBACK"
                    })

    if current_snapshot:
        st.session_state["terminal_stream_buffer"] = current_snapshot

capture_true_isolated_market_state()
all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])

# -----------------------------------------------------------------------------
# SCREEN RENDER INTERFACE
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.caption("Initializing active transmission channels...")
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.caption("Searching live contract matrices...")
        return

    top_record = f_df.iloc[0]
    st.metric(label="Underlying Anchor Price", value=f"₹{top_record['underlying']:,}")
    
    for _, r in f_df.head(3).iterrows():
        st.info(f"""
        **{r['formatted_symbol']}** | Matrix: **{r['direction']}** | Vol: {int(r['volume']):,} | **Premium LTP: ₹{r['ltp']}** | [{r['status']}]
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
    st.markdown("#### 📊 HIGH-LIQUIDITY EQUITIES WHALES")
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

# Auto refresh template loop every 3 seconds
st.components.v1.html(
    "<html><body><script>setTimeout(function(){window.location.reload();}, 3000);</script></body></html>",
    height=0, width=0
)
