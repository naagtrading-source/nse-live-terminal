import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
import random
import time
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
# BROKER CONNECTION
# Cached with TTL=1800s (30 min) — TOTP is only needed at login,
# the session stays valid. Prevents reconnecting on every 5s reload.
# ─────────────────────────────────────────────
@st.cache_resource(ttl=1800, show_spinner=False)
def initialize_broker_connection():
    required_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC",
                     "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        return None, f"MISSING ENV VARS: {', '.join(missing)}", []

    logs = []
    try:
        from neo_api_client import NeoAPI
        logs.append("neo_api_client imported OK")

        consumer_key = os.environ.get("KOTAK_CONSUMER_KEY")
        api = NeoAPI(environment='prod', consumer_key=consumer_key)
        logs.append(f"NeoAPI created (key: ...{consumer_key[-6:]})")

        totp_secret = os.environ.get("KOTAK_TOTP_SECRET").replace(" ", "")
        totp_token = pyotp.TOTP(totp_secret).now()
        logs.append(f"TOTP: {totp_token}")

        # Normalise mobile → exactly 10 digits
        mobile_raw = os.environ.get("KOTAK_MOBILE", "").strip().lstrip("+")
        if mobile_raw.startswith("91") and len(mobile_raw) == 12:
            mobile_raw = mobile_raw[2:]
        elif mobile_raw.startswith("0") and len(mobile_raw) == 11:
            mobile_raw = mobile_raw[1:]
        logs.append(f"Mobile: ...{mobile_raw[-4:]} ({len(mobile_raw)} digits)")

        ucc = os.environ.get("KOTAK_UCC")
        login_resp = api.totp_login(mobile_number=mobile_raw, ucc=ucc, totp=totp_token)
        # Log only the error/success summary — not the full response (saves memory)
        if isinstance(login_resp, dict) and login_resp.get('error'):
            logs.append(f"LOGIN ERROR: {str(login_resp['error'])[:200]}")
            return None, f"LOGIN_FAILED", logs
        logs.append(f"totp_login: OK")

        # Extract Auth + SID to pass into validate
        mpin = os.environ.get("KOTAK_MPIN")
        auth_token, sid = None, None
        if isinstance(login_resp, dict):
            data = login_resp.get('data', login_resp)
            auth_token = data.get('Auth') or data.get('auth') or data.get('token')
            sid = data.get('SID') or data.get('sid') or data.get('Sid')

        try:
            if auth_token and sid:
                validate_resp = api.totp_validate(mpin=mpin, Auth=auth_token, sid=sid)
            elif auth_token:
                validate_resp = api.totp_validate(mpin=mpin, Auth=auth_token)
            else:
                validate_resp = api.totp_validate(mpin=mpin)
        except TypeError:
            validate_resp = api.totp_validate(mpin=mpin)

        if isinstance(validate_resp, dict) and validate_resp.get('error'):
            logs.append(f"VALIDATE ERROR: {str(validate_resp['error'])[:200]}")
            return None, "VALIDATE_FAILED", logs

        logs.append("totp_validate: OK")
        return api, "OK", logs

    except ImportError as e:
        return None, f"IMPORT_ERROR: {e}", logs
    except Exception as e:
        logs.append(f"Exception: {type(e).__name__}: {str(e)[:200]}")
        return None, f"AUTH_ERROR: {type(e).__name__}", logs


api_client, api_status, auth_logs = initialize_broker_connection()

# ── Status banner ────────────────────────────
if api_status == "OK":
    st.success("🟢 Broker Connected — Live data active")
elif "MISSING" in api_status:
    st.warning(f"⚠️ {api_status}")
else:
    st.error(f"🔴 {api_status}")

# ── Lightweight diagnostic (text only — no st.json) ──
with st.expander("🔧 Diagnostic Log", expanded=(api_status != "OK")):
    env_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC",
                "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    for k in env_keys:
        v = os.environ.get(k)
        if v:
            st.success(f"✅ {k} ({len(v)} chars)")
        else:
            st.error(f"❌ {k} MISSING")
    for log in auth_logs:
        st.code(log)

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
# SCRIP CACHE — fetched once per session, not every 5s reload
# Searching scrip is expensive (large response). Cache by symbol.
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_scrip_records(fo_seg, symbol):
    """Fetch and cache scrip list for a symbol. TTL=1hr."""
    if api_client is None:
        return []
    try:
        res = api_client.search_scrip(exchange_segment=fo_seg, symbol=symbol)
        if isinstance(res, dict):
            return res.get('data', []) or res.get('result', []) or []
        return res if isinstance(res, list) else []
    except Exception:
        return []

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def safe_ltp(q):
    for key in ('last_traded_price', 'ltp', 'lastPrice', 'c', 'close',
                'Last_Traded_Price', 'LTP', 'last_price'):
        val = q.get(key)
        if val is not None and val != '':
            try:
                f = float(val)
                if f > 0:
                    return f
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
        if isinstance(q, list) and q:
            return safe_ltp(q[0]), safe_volume(q[0])
        if isinstance(q, dict):
            data = q.get('data', [])
            if data:
                return safe_ltp(data[0]), safe_volume(data[0])
    except Exception:
        pass
    return 0.0, 0

def normalize_opt(raw):
    raw = str(raw).strip().upper()
    if raw in ('CE', 'CALL', 'C'):
        return 'CE'
    if raw in ('PE', 'PUT', 'P'):
        return 'PE'
    return None

def expiry_in(trd_sym, exp_tag):
    return exp_tag.upper() in str(trd_sym).upper()

def get_token(item):
    for k in ('pSymbol', 'token', 'instrument_token', 'Token'):
        v = item.get(k)
        if v is not None:
            return v
    return None

def get_trd_sym(item):
    for k in ('pTrdSymbol', 'trdSym', 'tradingSymbol'):
        v = item.get(k)
        if v:
            return str(v).upper()
    return ""

def get_strike(item):
    for k in ('pStrikePrice', 'strkPrc', 'strikePrice', 'strike_price'):
        v = item.get(k)
        if v is not None:
            try:
                return int(float(v))
            except (ValueError, TypeError):
                continue
    return None

# ─────────────────────────────────────────────
# LIVE DATA FETCH  (only quotes are fetched on each 10s refresh)
# ─────────────────────────────────────────────
def capture_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts = datetime.now(ist_tz).strftime("%H:%M:%S")
    snapshot = []
    live = False

    if api_client is None:
        return snapshot, False

    for symbol, meta in ASSET_ROUTING.items():
        exp_tag = meta["exp"]
        underlying = 0.0

        # Use cached scrip records — not re-fetched every reload
        fo_records = get_scrip_records(meta["fo_seg"], symbol)

        # ── Resolve underlying price ─────────────────────────────────
        if meta["is_fut"]:
            for item in fo_records:
                trd = get_trd_sym(item)
                if "FUT" in trd and expiry_in(trd, exp_tag):
                    tok = get_token(item)
                    if tok:
                        ltp, _ = fetch_ltp(tok, meta["fo_seg"])
                        if ltp > 0:
                            underlying = ltp
                            break
            # Fallback: any FUT
            if underlying <= 0:
                for item in fo_records:
                    if "FUT" in get_trd_sym(item):
                        tok = get_token(item)
                        if tok:
                            ltp, _ = fetch_ltp(tok, meta["fo_seg"])
                            if ltp > 0:
                                underlying = ltp
                                break
        else:
            cm_records = get_scrip_records(meta["cm_seg"], symbol)
            for item in cm_records:
                trd = get_trd_sym(item)
                if trd in (f"{symbol}-EQ", symbol, f"{symbol}EQ"):
                    tok = get_token(item)
                    if tok:
                        ltp, _ = fetch_ltp(tok, meta["cm_seg"])
                        if ltp > 0:
                            underlying = ltp
                            break

        if underlying <= 0:
            continue

        # ── ATM strikes ──────────────────────────────────────────────
        atm = int(round(underlying / meta["step"]) * meta["step"])
        strikes = {atm - meta["step"], atm, atm + meta["step"]}

        # ── Walk option chain ────────────────────────────────────────
        for item in fo_records:
            try:
                trd = get_trd_sym(item)
                if not expiry_in(trd, exp_tag):
                    continue
                opt = normalize_opt(item.get("pOptionType", item.get("optTp", "")))
                if opt is None:
                    continue
                strike = get_strike(item)
                if strike not in strikes:
                    continue
                tok = get_token(item)
                if not tok:
                    continue
                ltp, vol = fetch_ltp(tok, meta["fo_seg"])
                if ltp <= 0:
                    continue
                snapshot.append({
                    "timestamp": ts, "asset": symbol,
                    "formatted_symbol": trd,
                    "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                    "volume": vol, "ltp": ltp,
                    "underlying": underlying, "status": "🟢 LIVE"
                })
                live = True
            except Exception:
                continue

    return snapshot, live


def fallback_snapshot():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts = datetime.now(ist_tz).strftime("%H:%M:%S")
    rows = []
    for symbol, meta in ASSET_ROUTING.items():
        base = meta["base"] + round(random.uniform(-15, 15), 1)
        atm = int(round(base / meta["step"]) * meta["step"])
        for strike in [atm - meta["step"], atm, atm + meta["step"]]:
            for opt in ["CE", "PE"]:
                ltp = (round(random.uniform(40, 260), 1)
                       if symbol in ("NIFTY", "BANKNIFTY")
                       else round(random.uniform(6, 65), 1))
                rows.append({
                    "timestamp": ts, "asset": symbol,
                    "formatted_symbol": f"{symbol}{meta['exp']}{strike}{opt}",
                    "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                    "volume": random.randint(15000, 125000),
                    "ltp": ltp, "underlying": base,
                    "status": "🌙 OFF-HOURS FALLBACK"
                })
    return rows

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if "buffer" not in st.session_state:
    st.session_state["buffer"] = []

snapshot, got_live = capture_market_state()
if got_live:
    st.session_state["buffer"] = snapshot
elif not st.session_state["buffer"]:
    # Only generate fallback if we have nothing stored yet
    st.session_state["buffer"] = fallback_snapshot()

all_df = pd.DataFrame(st.session_state["buffer"])

ist_now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
live_count = len(all_df[all_df['status'].str.contains('LIVE', na=False)]) if not all_df.empty else 0
st.caption(
    f"📦 Rows: {len(all_df)} | 🟢 Live: {live_count} | "
    f"🌙 Fallback: {len(all_df) - live_count} | IST: {ist_now}"
)

# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────
def render_block(asset, df):
    if df.empty:
        st.warning("⏳ No data...")
        return
    f = df[df['asset'].str.upper() == asset.upper()]
    if f.empty:
        st.warning(f"⏳ No rows for {asset}")
        return
    st.metric("Underlying", f"₹{f.iloc[0]['underlying']:,.1f}")
    for _, r in f.head(6).iterrows():
        dot = "🔵" if "CALL" in r['direction'] else "🔴"
        st.info(
            f"{dot} **{r['formatted_symbol']}** | **{r['direction']}** | "
            f"Vol: {int(r['volume']):,} | **LTP: ₹{r['ltp']}** | [{r['status']}]"
        )

tab1, tab2, tab3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with tab1:
    st.markdown("#### ⚡ Exchange Registered Derivative Indices")
    c1, c2 = st.columns(2)
    with c1:
        st.error("🦅 NIFTY")
        render_block("NIFTY", all_df)
    with c2:
        st.error("🦅 BANKNIFTY")
        render_block("BANKNIFTY", all_df)

with tab2:
    st.markdown("#### 📊 High-Liquidity Equities")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.warning("💎 RELIANCE")
        render_block("RELIANCE", all_df)
    with c2:
        st.warning("💎 HDFCBANK")
        render_block("HDFCBANK", all_df)
    with c3:
        st.warning("💎 TCS")
        render_block("TCS", all_df)

with tab3:
    st.markdown("#### 🛢️ MCX Commodities")
    c1, c2 = st.columns(2)
    with c1:
        st.success("🔥 CRUDEOIL")
        render_block("CRUDEOIL", all_df)
    with c2:
        st.success("✨ GOLD")
        render_block("GOLD", all_df)

# Auto-refresh every 10s (was 5s — halved to reduce memory pressure)
st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();}, 10000);</script>",
    height=0, width=0
)
