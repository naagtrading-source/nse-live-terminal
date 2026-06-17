import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
import random
from datetime import datetime

st.set_page_config(
    page_title="Symmetrical Institutional Flow Terminal",
    layout="wide",
    page_icon="🚨"
)

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

st.title("⚡ SNY — QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Self-Healing Engine | Continuous Heartbeat Session Validation & Live Field Inspector")
st.markdown("---")

# -----------------------------------------------------------------------------
# PERSISTENT SESSION MONITORING ARRAYS
# -----------------------------------------------------------------------------
if "api_client" not in st.session_state:
    st.session_state["api_client"] = None
if "api_status" not in st.session_state:
    st.session_state["api_status"] = "INITIALIZING"
if "last_api_error" not in st.session_state:
    st.session_state["last_api_error"] = None
if "inspected_fields" not in st.session_state:
    st.session_state["inspected_fields"] = {}

# -----------------------------------------------------------------------------
# AUTOMATED BROKER AUTHENTICATION ROUTE
# -----------------------------------------------------------------------------
def login_broker():
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    missing_keys = [k for k in required_keys if not os.environ.get(k)]
    if missing_keys:
        return None, f"MISSING ENV VARS: {', '.join(missing_keys)}"

    try:
        from neo_api_client import NeoAPI
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
        return api, "OK"
    except Exception as e:
        return None, f"AUTH_ERROR: {str(e)}"

# 🔄 THE HEARTBEAT VALVE: Validates session status dynamically on every frame cycle
if st.session_state["api_client"] is None:
    client, status_msg = login_broker()
    st.session_state["api_client"] = client
    st.session_state["api_status"] = status_msg
else:
    try:
        # Check authorization state using a fast, low-overhead endpoint
        st.session_state["api_client"].limits(segment="ALL", exchange="ALL", product="ALL")
        st.session_state["api_status"] = "🟢 Live Active Broker Session"
    except Exception as stale_err:
        # Intercept dropped connection and automatically refresh session
        client, status_msg = login_broker()
        st.session_state["api_client"] = client
        if client:
            st.session_state["api_status"] = "🔄 Session Revived Automatically"
        else:
            st.session_state["api_status"] = f"🔴 Connection Lost: {status_msg}"

# -----------------------------------------------------------------------------
# 🔧 SYSTEM DIAGNOSTIC & FIELD INSPECTOR PANEL
# -----------------------------------------------------------------------------
with st.expander("🔧 System Diagnostic & Live Inspector Panel", expanded=False):
    col_env1, col_env2 = st.columns(2)
    with col_env1:
        st.markdown("### 🔑 Credential Vector Mapping")
        for k in ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]:
            if os.environ.get(k):
                st.success(f"✅ {k} — Active")
            else:
                st.error(f"❌ {k} — MISSING")
    with col_env2:
        st.markdown("### 🛡️ Runtime Environment Telemetry")
        st.info(f"**Handshake State:** {st.session_state['api_status']}")
        if st.session_state["last_api_error"]:
            st.warning(f"**Last Core Warning:** {st.session_state['last_api_error']}")

    if st.session_state["inspected_fields"]:
        st.markdown("### 🔍 Dictionary Parameter Structure (Raw Exchange Scrip Sample)")
        st.json(st.session_state["inspected_fields"])

# -----------------------------------------------------------------------------
# ASSET STRATEGIC BOUNDS
# -----------------------------------------------------------------------------
ASSET_ROUTING = {
    "NIFTY":     {"fo_seg": "nse_fo", "is_fut": True,  "step": 50,  "base": 23450, "exp": "23JUN26"},
    "BANKNIFTY": {"fo_seg": "nse_fo", "is_fut": True,  "step": 100, "base": 50600, "exp": "30JUN26"},
    "RELIANCE":  {"fo_seg": "nse_fo", "is_fut": False, "step": 20,  "base": 2980,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "HDFCBANK":  {"fo_seg": "nse_fo", "is_fut": False, "step": 10,  "base": 1610,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "TCS":       {"fo_seg": "nse_fo", "is_fut": False, "step": 50,  "base": 3850,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "CRUDEOIL":  {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 6550,  "exp": "17JUL26"},
    "GOLD":      {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 72800, "exp": "30JUN26"},
}

# -----------------------------------------------------------------------------
# HELPER UTILITIES
# -----------------------------------------------------------------------------
def safe_scrip_list(res):
    if isinstance(res, dict):
        return res.get('data', []) or res.get('result', []) or []
    elif isinstance(res, list):
        return res
    return []

def safe_ltp(q):
    for key in ('last_traded_price', 'ltp', 'lastPrice', 'c', 'close'):
        val = q.get(key)
        if val is not None:
            try: return float(val)
            except: continue
    return 0.0

def safe_volume(q):
    for key in ('volume', 'tradedQuantity', 'vol', 'totalTradedVolume', 'ltq'):
        val = q.get(key)
        if val is not None:
            try: return int(float(val))
            except: continue
    return 0

def fetch_ltp(token_id, segment):
    api = st.session_state["api_client"]
    if api is None:
        return 0.0, 0
    try:
        q = api.get_live_quotes([{"instrument_token": str(token_id), "exchange_segment": segment}])
        if q and isinstance(q, list) and len(q) > 0:
            return safe_ltp(q[0]), safe_volume(q[0])
    except Exception as e:
        st.session_state["last_api_error"] = f"Quotes API rejection on token {token_id}: {str(e)}"
    return 0.0, 0

def normalize_opt_type(raw):
    raw = str(raw).strip().upper()
    if raw in ('CE', 'CALL', 'C'): return 'CE'
    if raw in ('PE', 'PUT', 'P'): return 'PE'
    return None

def expiry_matches(trd_sym, exp_tag):
    return exp_tag.upper() in str(trd_sym).upper()

# -----------------------------------------------------------------------------
# HYBRID DATA EXTRACTION ARCHITECTURE
# -----------------------------------------------------------------------------
def capture_hybrid_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    current_snapshot = []
    live_data_fetched = False

    api = st.session_state["api_client"]

    if api is not None and hasattr(api, 'search_scrip'):
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = 0.0
            exp_tag = meta["exp"]

            # Resolve live underlying metrics
            try:
                if meta["is_fut"]:
                    res = api.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
                    records = safe_scrip_list(res)
                    
                    # Store data fields to map parameter structure variants instantly
                    if records and symbol not in st.session_state["inspected_fields"]:
                        st.session_state["inspected_fields"][symbol] = records[0]
                        
                    for item in records:
                        # Defensive parsing checking all known SDK variable options
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", item.get("trading_symbol", "")))).upper()
                        if "FUT" in trd_sym and expiry_matches(trd_sym, exp_tag):
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["fo_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
                else:
                    res_cm = api.search_scrip(exchange_segment=meta["cm_seg"], symbol=symbol)
                    for item in safe_scrip_list(res_cm):
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", item.get("trading_symbol", "")))).upper()
                        if trd_sym in (f"{symbol}-EQ", symbol):
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["cm_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
            except Exception as e:
                st.session_state["last_api_error"] = f"Underlying resolution exception on {symbol}: {str(e)}"
                continue

            if underlying_price <= 0.0:
                continue

            # Build options strike cluster array mapping boundaries
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = {atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]}

            try:
                res_fo = api.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
                fo_records = safe_scrip_list(res_fo)
            except Exception as e:
                st.session_state["last_api_error"] = f"Chain lookup failed on {symbol}: {str(e)}"
                continue

            for item in fo_records:
                try:
                    trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", item.get("trading_symbol", "")))).upper()
                    if not expiry_matches(trd_sym, exp_tag):
                        continue

                    opt_type = normalize_opt_type(item.get("pOptionType", item.get("optTp", item.get("optionType", ""))))
                    if opt_type is None:
                        continue

                    raw_strike = item.get("pStrikePrice", item.get("strkPrc", item.get("strikePrice", 0)))
                    try: strike_val = int(float(raw_strike))
                    except: continue

                    if strike_val not in target_strikes:
                        continue

                    token_id = item.get("pSymbol", item.get("token"))
                    ltp_val, vol = fetch_ltp(token_id, meta["fo_seg"])

                    if ltp_val <= 0.0:
                        continue

                    current_snapshot.append({
                        "timestamp": ts_string, "asset": symbol, "formatted_symbol": trd_sym,
                        "direction": "CALL ACCUMULATION" if opt_type == "CE" else "PUT DISTRIBUTION",
                        "volume": vol, "ltp": ltp_val, "underlying": underlying_price, "status": "🟢 LIVE SPEED"
                    })
                    live_data_fetched = True
                except:
                    continue

    # Integrated fallback layer for when segments are natively closed
    if not live_data_fetched:
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = meta["base"] + round(random.uniform(-15, 15), 1)
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]

            for strike in target_strikes:
                for opt in ["CE", "PE"]:
                    ltp = round(random.uniform(40.0, 260.0), 1) if symbol in ["NIFTY", "BANKNIFTY"] else round(random.uniform(6.0, 65.0), 1)
                    current_snapshot.append({
                        "timestamp": ts_string, "asset": symbol, "formatted_symbol": f"{symbol}{meta['exp']}{strike}{opt}",
                        "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                        "volume": random.randint(15000, 125000), "ltp": ltp, "underlying": underlying_price, "status": "🌙 OFF-HOURS FALLBACK"
                    })

    return current_snapshot

snapshot = capture_hybrid_market_state()
if snapshot:
    st.session_state["terminal_stream_buffer"] = snapshot

all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])
st.caption(f"📦 Data matrix elements processed: {len(all_df)} | Refresh sync update counter: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')} IST")

# -----------------------------------------------------------------------------
# SCREEN RENDER INTERFACE
# -----------------------------------------------------------------------------
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.warning("⏳ Accessing network nodes...")
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.warning(f"⏳ Syncing metrics for {asset_filter}")
        return

    top_record = f_df.iloc[0]
    st.metric(label="Underlying Anchor Price", value=f"₹{top_record['underlying']:,.1f}")

    for _, r in f_df.head(4).iterrows():
        color = "🔵" if "CALL" in str(r['direction']) else "🔴"
        st.info(f"{color} **{r['formatted_symbol']}** | Matrix: **{r['direction']}** | Vol: {int(r['volume']):,} | **LTP: ₹{r['ltp']}** | [{r['status']}]")

tab1, tab2, tab3 = st.tabs([" Northampton Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with tab1:
    st.markdown("#### ⚡ Exchange Registered Derivative Indices")
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.error("🦅 NIFTY RADAR")
        render_terminal_log_block("NIFTY", all_df)
    with idx_col2:
        st.error("🦅 BANKNIFTY RADAR")
        render_terminal_log_block("BANKNIFTY", all_df)

with tab2:
    st.markdown("#### 📊 High-Liquidity Equities Whales")
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
    st.markdown("#### 🛢️ Multi-Commodity Exchange Block Surges")
    cmd_col1, cmd_col2 = st.columns(2)
    with cmd_col1:
        st.success("🔥 CRUDEOIL")
        render_terminal_log_block("CRUDEOIL", all_df)
    with cmd_col2:
        st.success("✨ GOLD")
        render_terminal_log_block("GOLD", all_df)

st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();}, 5000);</script>",
    height=0, width=0
)
