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
st.caption("Hybrid Core Engine | Real-Time Live Streaming & Automated Off-Hours Fallback")
st.markdown("---")

# ─────────────────────────────────────────────
# DIAGNOSTIC PANEL  (always visible, helps debug)
# ─────────────────────────────────────────────
with st.expander("🔧 System Diagnostic Panel", expanded=False):
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    all_present = True
    for k in required_keys:
        val = os.environ.get(k)
        if val:
            st.success(f"✅ {k} — set ({len(val)} chars)")
        else:
            st.error(f"❌ {k} — MISSING")
            all_present = False
    if all_present:
        st.info("All env vars present. If still blank, check broker auth below.")

# ─────────────────────────────────────────────
# BROKER CONNECTION
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def initialize_broker_connection():
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
    except ImportError:
        return None, "IMPORT_ERROR: neo_api_client not installed"
    except Exception as e:
        return None, f"AUTH_ERROR: {str(e)}"

api_client, api_status = initialize_broker_connection()

with st.expander("🔧 System Diagnostic Panel", expanded=False):
    pass  # Already rendered above; status shown below

# Show broker status banner
if api_status == "OK" and api_client is not None:
    st.success("🟢 Broker Connected — Live data active")
elif "MISSING" in api_status:
    st.warning(f"⚠️ {api_status} — Running in OFF-HOURS FALLBACK mode")
else:
    st.error(f"🔴 Broker Error: {api_status} — Running in OFF-HOURS FALLBACK mode")

# ─────────────────────────────────────────────
# ASSET CONFIG
# ─────────────────────────────────────────────
ASSET_ROUTING = {
    "NIFTY":     {"fo_seg": "nse_fo", "is_fut": True,  "step": 50,  "base": 23450, "exp": "23JUN26"},
    "BANKNIFTY": {"fo_seg": "nse_fo", "is_fut": True,  "step": 100, "base": 50600, "exp": "30JUN26"},
    "RELIANCE":  {"fo_seg": "nse_fo", "is_fut": False, "step": 20,  "base": 2980,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "HDFCBANK":  {"fo_seg": "nse_fo", "is_fut": False, "step": 10,  "base": 1610,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "TCS":       {"fo_seg": "nse_fo", "is_fut": False, "step": 50,  "base": 3850,  "exp": "30JUN26", "cm_seg": "nse_cm"},
    "CRUDEOIL":  {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 6550,  "exp": "17JUL26"},
    "GOLD":      {"fo_seg": "mcx_fo", "is_fut": True,  "step": 100, "base": 72800, "exp": "30JUN26"},
}

# ─────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────
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
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return 0.0

def safe_volume(q):
    for key in ('volume', 'tradedQuantity', 'vol', 'totalTradedVolume', 'ltq'):
        val = q.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                continue
    return 0

def fetch_ltp(token_id, segment):
    try:
        q = api_client.get_live_quotes([{
            "instrument_token": str(token_id),
            "exchange_segment": segment
        }])
        if q and isinstance(q, list) and len(q) > 0:
            return safe_ltp(q[0]), safe_volume(q[0])
    except Exception:
        pass
    return 0.0, 0

def normalize_opt_type(raw):
    raw = str(raw).strip().upper()
    if raw in ('CE', 'CALL', 'C'):
        return 'CE'
    if raw in ('PE', 'PUT', 'P'):
        return 'PE'
    return None

def expiry_matches(trd_sym, exp_tag):
    return exp_tag.upper() in str(trd_sym).upper()

# ─────────────────────────────────────────────
# HYBRID MARKET DATA CAPTURE
# ─────────────────────────────────────────────
def capture_hybrid_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    current_snapshot = []
    live_data_fetched = False

    if api_client is not None and hasattr(api_client, 'search_scrip'):
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = 0.0
            exp_tag = meta["exp"]

            # ── Resolve underlying price ──────────────────────────────────
            try:
                if meta["is_fut"]:
                    res = api_client.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
                    for item in safe_scrip_list(res):
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                        if "FUT" in trd_sym and expiry_matches(trd_sym, exp_tag):
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["fo_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
                else:
                    res_cm = api_client.search_scrip(exchange_segment=meta["cm_seg"], symbol=symbol)
                    for item in safe_scrip_list(res_cm):
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                        if trd_sym in (f"{symbol}-EQ", symbol):
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["cm_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
            except Exception:
                pass

            if underlying_price <= 0.0:
                continue

            # ── Build ATM strike ladder ───────────────────────────────────
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = {
                atm_strike - meta["step"],
                atm_strike,
                atm_strike + meta["step"],
            }

            # ── Fetch option chain ────────────────────────────────────────
            try:
                res_fo = api_client.search_scrip(exchange_segment=meta["fo_seg"], symbol=symbol)
                fo_records = safe_scrip_list(res_fo)
            except Exception:
                continue

            for item in fo_records:
                try:
                    trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                    if not expiry_matches(trd_sym, exp_tag):
                        continue

                    opt_type = normalize_opt_type(
                        item.get("pOptionType", item.get("optTp", ""))
                    )
                    if opt_type is None:
                        continue

                    raw_strike = item.get("pStrikePrice", item.get("strkPrc", item.get("strikePrice", 0)))
                    try:
                        strike_val = int(float(raw_strike))
                    except (ValueError, TypeError):
                        continue

                    if strike_val not in target_strikes:
                        continue

                    token_id = item.get("pSymbol", item.get("token"))
                    ltp_val, vol = fetch_ltp(token_id, meta["fo_seg"])

                    if ltp_val <= 0.0:
                        continue

                    current_snapshot.append({
                        "timestamp": ts_string,
                        "asset": symbol,
                        "formatted_symbol": trd_sym,
                        "direction": "CALL ACCUMULATION" if opt_type == "CE" else "PUT DISTRIBUTION",
                        "volume": vol,
                        "ltp": ltp_val,
                        "underlying": underlying_price,
                        "status": "🟢 LIVE SPEED",
                    })
                    live_data_fetched = True
                except Exception:
                    continue

    # ── Off-hours synthetic fallback ──────────────────────────────────────
    if not live_data_fetched:
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = meta["base"] + round(random.uniform(-15, 15), 1)
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]

            for strike in target_strikes:
                for opt in ["CE", "PE"]:
                    ltp = (
                        round(random.uniform(40.0, 260.0), 1)
                        if symbol in ["NIFTY", "BANKNIFTY"]
                        else round(random.uniform(6.0, 65.0), 1)
                    )
                    current_snapshot.append({
                        "timestamp": ts_string,
                        "asset": symbol,
                        "formatted_symbol": f"{symbol}{meta['exp']}{strike}{opt}",
                        "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                        "volume": random.randint(15000, 125000),
                        "ltp": ltp,
                        "underlying": underlying_price,
                        "status": "🌙 OFF-HOURS FALLBACK",
                    })

    return current_snapshot

# ─────────────────────────────────────────────
# RUN DATA CAPTURE  (always, no cache on this)
# ─────────────────────────────────────────────
if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

snapshot = capture_hybrid_market_state()
if snapshot:
    st.session_state["terminal_stream_buffer"] = snapshot

all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])

# Show row count for debug
st.caption(f"📦 Data rows loaded: {len(all_df)} | Last refresh: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')} IST")

# ─────────────────────────────────────────────
# RENDER HELPERS
# ─────────────────────────────────────────────
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.warning("⏳ No data loaded yet — waiting for market data...")
        return

    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()

    if f_df.empty:
        st.warning(f"⏳ No rows found for {asset_filter}")
        return

    top_record = f_df.iloc[0]
    status_tag = top_record.get("status", "")
    st.metric(label="Underlying Anchor Price", value=f"₹{top_record['underlying']:,.1f}")

    for _, r in f_df.head(6).iterrows():
        color = "🔵" if "CALL" in str(r['direction']) else "🔴"
        st.info(
            f"{color} **{r['formatted_symbol']}** | "
            f"Matrix: **{r['direction']}** | "
            f"Vol: {int(r['volume']):,} | "
            f"**LTP: ₹{r['ltp']}** | "
            f"[{r['status']}]"
        )

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

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

# ─────────────────────────────────────────────
# AUTO-REFRESH  (every 5s — safer than 3s)
# ─────────────────────────────────────────────
st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();}, 5000);</script>",
    height=0, width=0
)
