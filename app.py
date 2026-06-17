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
# BROKER CONNECTION  (NOT cached — TOTP is time-based, 30s window)
# ─────────────────────────────────────────────
def initialize_broker_connection():
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    missing_keys = [k for k in required_keys if not os.environ.get(k)]
    if missing_keys:
        return None, f"MISSING ENV VARS: {', '.join(missing_keys)}", []

    logs = []
    try:
        from neo_api_client import NeoAPI
        logs.append("✅ neo_api_client imported")

        consumer_key = os.environ.get("KOTAK_CONSUMER_KEY")
        api = NeoAPI(environment='prod', consumer_key=consumer_key)
        logs.append(f"✅ NeoAPI object created (key: ...{consumer_key[-6:]})")

        totp_secret = os.environ.get("KOTAK_TOTP_SECRET").replace(" ", "")
        totp_token = pyotp.TOTP(totp_secret).now()
        logs.append(f"✅ TOTP generated: {totp_token}")

        mobile = os.environ.get("KOTAK_MOBILE")
        ucc    = os.environ.get("KOTAK_UCC")
        login_resp = api.totp_login(mobile_number=mobile, ucc=ucc, totp=totp_token)
        logs.append(f"✅ totp_login response: {str(login_resp)[:200]}")

        mpin = os.environ.get("KOTAK_MPIN")
        validate_resp = api.totp_validate(mpin=mpin)
        logs.append(f"✅ totp_validate response: {str(validate_resp)[:200]}")

        return api, "OK", logs

    except ImportError as e:
        logs.append(f"❌ ImportError: {e}")
        return None, f"IMPORT_ERROR: {e}", logs
    except Exception as e:
        logs.append(f"❌ Exception: {type(e).__name__}: {e}")
        return None, f"AUTH_ERROR: {type(e).__name__}: {e}", logs

api_client, api_status, auth_logs = initialize_broker_connection()

# ── Status banner ────────────────────────────
if api_status == "OK":
    st.success("🟢 Broker Connected — Live data active")
elif "MISSING" in api_status:
    st.warning(f"⚠️ {api_status} — Running in OFF-HOURS FALLBACK mode")
else:
    st.error(f"🔴 Broker Error — Running in OFF-HOURS FALLBACK mode")

# ── Diagnostic expander ──────────────────────
with st.expander("🔧 Auth & Live Data Diagnostic Log", expanded=(api_status != "OK")):
    st.markdown("**Environment Variables:**")
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    for k in required_keys:
        val = os.environ.get(k)
        if val:
            st.success(f"✅ {k} — set ({len(val)} chars)")
        else:
            st.error(f"❌ {k} — MISSING")

    st.markdown("**Auth Steps:**")
    for log in auth_logs:
        st.code(log)

    if api_client is not None:
        st.markdown("**Live Search Scrip Test (NIFTY on nse_fo):**")
        try:
            test_res = api_client.search_scrip(exchange_segment="nse_fo", symbol="NIFTY")
            records = test_res.get('data', []) if isinstance(test_res, dict) else test_res
            st.success(f"✅ search_scrip returned {len(records)} records")
            if records:
                st.json(records[0])  # Show first record so we can see real field names
        except Exception as e:
            st.error(f"❌ search_scrip failed: {type(e).__name__}: {e}")

        st.markdown("**Live Quote Test (first NIFTY FUT token found):**")
        try:
            test_res2 = api_client.search_scrip(exchange_segment="nse_fo", symbol="NIFTY")
            records2 = test_res2.get('data', []) if isinstance(test_res2, dict) else test_res2
            token_found = None
            trd_sym_found = ""
            for item in records2:
                trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                if "FUT" in trd_sym:
                    token_found = item.get("pSymbol", item.get("token"))
                    trd_sym_found = trd_sym
                    break
            if token_found:
                st.info(f"Using token: {token_found} | symbol: {trd_sym_found}")
                q = api_client.get_live_quotes([{
                    "instrument_token": str(token_found),
                    "exchange_segment": "nse_fo"
                }])
                st.success(f"✅ get_live_quotes raw response:")
                st.json(q)
            else:
                st.warning("No FUT token found in NIFTY scrip records")
        except Exception as e:
            st.error(f"❌ get_live_quotes failed: {type(e).__name__}: {e}")

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
# HELPERS
# ─────────────────────────────────────────────
def safe_scrip_list(res):
    if isinstance(res, dict):
        return res.get('data', []) or res.get('result', []) or []
    elif isinstance(res, list):
        return res
    return []

def safe_ltp(q):
    # Try every known Kotak Neo field name for LTP
    for key in ('last_traded_price', 'ltp', 'lastPrice', 'c', 'close', 'ltp_rate',
                'Last_Traded_Price', 'LTP', 'ltP', 'last_price'):
        val = q.get(key)
        if val is not None and val != '' and val != 0:
            try:
                f = float(val)
                if f > 0:
                    return f
            except (ValueError, TypeError):
                continue
    return 0.0

def safe_volume(q):
    for key in ('volume', 'tradedQuantity', 'vol', 'totalTradedVolume',
                'ltq', 'Volume', 'total_traded_volume', 'total_buy_quantity'):
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
        # Some versions return a dict with a 'data' key
        if q and isinstance(q, dict):
            data = q.get('data', [])
            if data and len(data) > 0:
                return safe_ltp(data[0]), safe_volume(data[0])
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
    # exp_tag like "23JUN26" — match case-insensitively inside symbol string
    return exp_tag.upper() in str(trd_sym).upper()

def get_strike_from_item(item):
    for key in ('pStrikePrice', 'strkPrc', 'strikePrice', 'strike_price', 'Strike_Price'):
        val = item.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                continue
    return None

def get_token_from_item(item):
    for key in ('pSymbol', 'token', 'instrument_token', 'Token'):
        val = item.get(key)
        if val is not None:
            return val
    return None

def get_trd_sym(item):
    for key in ('pTrdSymbol', 'trdSym', 'tradingSymbol', 'Trading_Symbol'):
        val = item.get(key)
        if val is not None:
            return str(val).upper()
    return ""

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

            # ── Step 1: Get all scrip records for this symbol ─────────────
            try:
                res_fo = api_client.search_scrip(
                    exchange_segment=meta["fo_seg"], symbol=symbol
                )
                fo_records = safe_scrip_list(res_fo)
            except Exception:
                fo_records = []

            # ── Step 2: Resolve underlying price ─────────────────────────
            if meta["is_fut"]:
                # Find the futures contract matching our expiry
                for item in fo_records:
                    trd_sym = get_trd_sym(item)
                    if "FUT" in trd_sym and expiry_matches(trd_sym, exp_tag):
                        token = get_token_from_item(item)
                        if token:
                            ltp_val, _ = fetch_ltp(token, meta["fo_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
                # Fallback: try the nearest FUT if expiry-matched one gives 0
                if underlying_price <= 0:
                    for item in fo_records:
                        trd_sym = get_trd_sym(item)
                        if "FUT" in trd_sym:
                            token = get_token_from_item(item)
                            if token:
                                ltp_val, _ = fetch_ltp(token, meta["fo_seg"])
                                if ltp_val > 0:
                                    underlying_price = ltp_val
                                    break
            else:
                # Equity: use cash segment
                try:
                    res_cm = api_client.search_scrip(
                        exchange_segment=meta["cm_seg"], symbol=symbol
                    )
                    cm_records = safe_scrip_list(res_cm)
                    for item in cm_records:
                        trd_sym = get_trd_sym(item)
                        if trd_sym in (f"{symbol}-EQ", symbol, f"{symbol}EQ"):
                            token = get_token_from_item(item)
                            if token:
                                ltp_val, _ = fetch_ltp(token, meta["cm_seg"])
                                if ltp_val > 0:
                                    underlying_price = ltp_val
                                    break
                    # Fallback: first CM record
                    if underlying_price <= 0 and cm_records:
                        token = get_token_from_item(cm_records[0])
                        if token:
                            ltp_val, _ = fetch_ltp(token, meta["cm_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                except Exception:
                    pass

            if underlying_price <= 0.0:
                continue

            # ── Step 3: Build ATM strike ladder ──────────────────────────
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = {
                atm_strike - meta["step"],
                atm_strike,
                atm_strike + meta["step"],
            }

            # ── Step 4: Walk option chain, match expiry + strike ──────────
            for item in fo_records:
                try:
                    trd_sym = get_trd_sym(item)
                    if not expiry_matches(trd_sym, exp_tag):
                        continue

                    opt_type = normalize_opt_type(
                        item.get("pOptionType", item.get("optTp", ""))
                    )
                    if opt_type is None:
                        continue

                    strike_val = get_strike_from_item(item)
                    if strike_val is None or strike_val not in target_strikes:
                        continue

                    token_id = get_token_from_item(item)
                    if not token_id:
                        continue

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
            for strike in [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]:
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
# RUN + BUILD DATAFRAME
# ─────────────────────────────────────────────
if "terminal_stream_buffer" not in st.session_state:
    st.session_state["terminal_stream_buffer"] = []

snapshot = capture_hybrid_market_state()
if snapshot:
    st.session_state["terminal_stream_buffer"] = snapshot

all_df = pd.DataFrame(st.session_state["terminal_stream_buffer"])

ist_now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
live_count = len(all_df[all_df['status'].str.contains('LIVE', na=False)]) if not all_df.empty else 0
st.caption(f"📦 Rows: {len(all_df)} | 🟢 Live: {live_count} | 🌙 Fallback: {len(all_df) - live_count} | IST: {ist_now}")

# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────
def render_terminal_log_block(asset_filter, df_source):
    if df_source.empty:
        st.warning("⏳ No data loaded yet...")
        return
    f_df = df_source[df_source['asset'].str.upper() == asset_filter.upper()].copy()
    if f_df.empty:
        st.warning(f"⏳ No rows found for {asset_filter}")
        return
    top_record = f_df.iloc[0]
    st.metric(label="Underlying Anchor Price", value=f"₹{top_record['underlying']:,.1f}")
    for _, r in f_df.head(6).iterrows():
        color = "🔵" if "CALL" in str(r['direction']) else "🔴"
        st.info(
            f"{color} **{r['formatted_symbol']}** | "
            f"**{r['direction']}** | "
            f"Vol: {int(r['volume']):,} | "
            f"**LTP: ₹{r['ltp']}** | "
            f"[{r['status']}]"
        )

tab1, tab2, tab3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with tab1:
    st.markdown("#### ⚡ Exchange Registered Derivative Indices")
    c1, c2 = st.columns(2)
    with c1:
        st.error("🦅 NIFTY RADAR")
        render_terminal_log_block("NIFTY", all_df)
    with c2:
        st.error("🦅 BANKNIFTY RADAR")
        render_terminal_log_block("BANKNIFTY", all_df)

with tab2:
    st.markdown("#### 📊 High-Liquidity Equities Whales")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.warning("💎 RELIANCE")
        render_terminal_log_block("RELIANCE", all_df)
    with c2:
        st.warning("💎 HDFCBANK")
        render_terminal_log_block("HDFCBANK", all_df)
    with c3:
        st.warning("💎 TCS")
        render_terminal_log_block("TCS", all_df)

with tab3:
    st.markdown("#### 🛢️ Multi-Commodity Exchange Block Surges")
    c1, c2 = st.columns(2)
    with c1:
        st.success("🔥 CRUDEOIL")
        render_terminal_log_block("CRUDEOIL", all_df)
    with c2:
        st.success("✨ GOLD")
        render_terminal_log_block("GOLD", all_df)

# Auto-refresh every 5s
st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();}, 5000);</script>",
    height=0, width=0
)
