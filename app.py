import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
import random
import requests
import json
from datetime import datetime

st.set_page_config(
    page_title="SNY Institutional Flow Terminal",
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

BASE_URL = "https://gw-napi.kotaksecurities.com"

# ─────────────────────────────────────────────
# AUTH — direct HTTP, no SDK, cached 25 min
# ─────────────────────────────────────────────
@st.cache_resource(ttl=1500, show_spinner=False)
def get_session():
    """
    Returns (headers, sid, server_id, error_msg)
    Uses raw HTTP so the neo_api_client SDK (heavy) is never imported.
    """
    ck  = os.environ.get("KOTAK_CONSUMER_KEY", "")
    mob = os.environ.get("KOTAK_MOBILE", "").strip().lstrip("+")
    if mob.startswith("91") and len(mob) == 12:
        mob = mob[2:]
    elif mob.startswith("0") and len(mob) == 11:
        mob = mob[1:]
    ucc    = os.environ.get("KOTAK_UCC", "")
    mpin   = os.environ.get("KOTAK_MPIN", "")
    secret = os.environ.get("KOTAK_TOTP_SECRET", "").replace(" ", "")

    if not all([ck, mob, ucc, mpin, secret]):
        return None, None, None, "Missing env vars"

    totp = pyotp.TOTP(secret).now()

    # Step 1 — TOTP login
    try:
        r1 = requests.post(
            f"{BASE_URL}/login/1.0/login/v2/validate",
            headers={
                "accept":       "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ck}",
            },
            json={
                "mobileNumber": mob,
                "ucc":          ucc,
                "totp":         totp,
            },
            timeout=15,
        )
        d1 = r1.json()
    except Exception as e:
        return None, None, None, f"Login HTTP error: {e}"

    if r1.status_code != 200 or d1.get("error"):
        return None, None, None, f"Login failed: {json.dumps(d1)[:300]}"

    data1   = d1.get("data", d1)
    auth    = data1.get("Auth") or data1.get("auth") or data1.get("token", "")
    sid     = data1.get("SID")  or data1.get("sid",  "")
    srv_id  = data1.get("ServerID") or data1.get("serverId", "")

    # Step 2 — MPIN validate
    try:
        r2 = requests.post(
            f"{BASE_URL}/login/1.0/login/v2/totp/validate",
            headers={
                "accept":        "application/json",
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {ck}",
                "Auth":          auth,
                "sid":           sid,
            },
            json={"mpin": mpin},
            timeout=15,
        )
        d2 = r2.json()
    except Exception as e:
        return None, None, None, f"Validate HTTP error: {e}"

    if r2.status_code != 200 or d2.get("error"):
        return None, None, None, f"Validate failed: {json.dumps(d2)[:300]}"

    data2     = d2.get("data", d2)
    final_tok = data2.get("token") or data2.get("Token") or data2.get("accessToken") or auth
    final_sid = data2.get("SID") or data2.get("sid") or sid

    headers = {
        "accept":        "application/json",
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {ck}",
        "Auth":          final_tok,
        "sid":           final_sid,
        "neo-fin-key":   f"neotradeapi{final_sid}",
        "Sid":           final_sid,
    }
    return headers, final_sid, srv_id, None


# ─────────────────────────────────────────────
# API CALLS — raw HTTP
# ─────────────────────────────────────────────
def api_search_scrip(headers, exchange_segment, symbol):
    """Cache scrip records per symbol — only fetched once per hour."""
    try:
        r = requests.get(
            f"{BASE_URL}/market-data/oms/1.0/scripmaster/search",
            params={"exchSeg": exchange_segment, "symbol": symbol, "series": ""},
            headers=headers,
            timeout=10,
        )
        d = r.json()
        if isinstance(d, dict):
            return d.get("data", []) or d.get("result", []) or []
        return d if isinstance(d, list) else []
    except Exception:
        return []


def api_live_quote(headers, token_id, exchange_segment):
    try:
        r = requests.post(
            f"{BASE_URL}/market-data/oms/1.0/quotes",
            headers=headers,
            json={
                "quote_type": "ltp",
                "Seg":        exchange_segment,
                "Exch":       exchange_segment.split("_")[0].upper(),
                "ExchType":   exchange_segment.split("_")[1].upper() if "_" in exchange_segment else "FO",
                "symbol":     str(token_id),
                "Depth":      "10",
                "mode":       "LTP",
            },
            timeout=8,
        )
        d = r.json()
        items = d.get("data", d) if isinstance(d, dict) else d
        if isinstance(items, list) and items:
            return items[0]
        if isinstance(items, dict):
            return items
    except Exception:
        pass
    return {}


def safe_ltp(q):
    for k in ('ltp', 'last_traded_price', 'lastPrice', 'LTP', 'c', 'close'):
        v = q.get(k)
        if v is not None and v != '':
            try:
                f = float(v)
                if f > 0:
                    return f
            except (ValueError, TypeError):
                continue
    return 0.0


def safe_vol(q):
    for k in ('volume', 'vol', 'tradedQuantity', 'totalTradedVolume', 'ltq'):
        v = q.get(k)
        if v is not None:
            try:
                return int(float(v))
            except (ValueError, TypeError):
                continue
    return 0


def norm_opt(raw):
    s = str(raw).strip().upper()
    if s in ('CE', 'CALL', 'C'):
        return 'CE'
    if s in ('PE', 'PUT', 'P'):
        return 'PE'
    return None


def expiry_in(sym, tag):
    return tag.upper() in sym.upper()


def get_tok(item):
    for k in ('pSymbol', 'token', 'instrument_token', 'Token', 'scripToken'):
        v = item.get(k)
        if v is not None:
            return v
    return None


def get_sym(item):
    for k in ('pTrdSymbol', 'trdSym', 'tradingSymbol', 'Trading_Symbol'):
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
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────
# SCRIP CACHE  (TTL 1 hour — large data, changes rarely)
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def cached_scrip(exchange_segment, symbol, _headers_key):
    """_headers_key is a dummy arg to bust cache on new session."""
    headers, _, _, err = get_session()
    if err or headers is None:
        return []
    return api_search_scrip(headers, exchange_segment, symbol)


# ─────────────────────────────────────────────
# MARKET DATA CAPTURE
# ─────────────────────────────────────────────
def capture_market_state(headers, session_id):
    ist = pytz.timezone('Asia/Kolkata')
    ts  = datetime.now(ist).strftime("%H:%M:%S")
    snap, live = [], False

    for symbol, meta in ASSET_ROUTING.items():
        exp_tag    = meta["exp"]
        underlying = 0.0

        fo_records = cached_scrip(meta["fo_seg"], symbol, session_id)

        # ── Underlying price ─────────────────────────────────────────
        if meta["is_fut"]:
            for item in fo_records:
                s = get_sym(item)
                if "FUT" in s and expiry_in(s, exp_tag):
                    tok = get_tok(item)
                    if tok:
                        q = api_live_quote(headers, tok, meta["fo_seg"])
                        ltp = safe_ltp(q)
                        if ltp > 0:
                            underlying = ltp
                            break
            if underlying <= 0:
                for item in fo_records:
                    if "FUT" in get_sym(item):
                        tok = get_tok(item)
                        if tok:
                            q = api_live_quote(headers, tok, meta["fo_seg"])
                            ltp = safe_ltp(q)
                            if ltp > 0:
                                underlying = ltp
                                break
        else:
            cm_records = cached_scrip(meta["cm_seg"], symbol, session_id)
            for item in cm_records:
                s = get_sym(item)
                if s in (f"{symbol}-EQ", symbol, f"{symbol}EQ"):
                    tok = get_tok(item)
                    if tok:
                        q = api_live_quote(headers, tok, meta["cm_seg"])
                        ltp = safe_ltp(q)
                        if ltp > 0:
                            underlying = ltp
                            break

        if underlying <= 0:
            continue

        # ── ATM ladder ───────────────────────────────────────────────
        atm     = int(round(underlying / meta["step"]) * meta["step"])
        strikes = {atm - meta["step"], atm, atm + meta["step"]}

        # ── Option chain scan ────────────────────────────────────────
        for item in fo_records:
            try:
                s = get_sym(item)
                if not expiry_in(s, exp_tag):
                    continue
                opt = norm_opt(item.get("pOptionType", item.get("optTp", "")))
                if opt is None:
                    continue
                strike = get_strike(item)
                if strike not in strikes:
                    continue
                tok = get_tok(item)
                if not tok:
                    continue
                q   = api_live_quote(headers, tok, meta["fo_seg"])
                ltp = safe_ltp(q)
                if ltp <= 0:
                    continue
                snap.append({
                    "timestamp": ts, "asset": symbol,
                    "formatted_symbol": s,
                    "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                    "volume": safe_vol(q), "ltp": ltp,
                    "underlying": underlying, "status": "🟢 LIVE",
                })
                live = True
            except Exception:
                continue

    return snap, live


def fallback_snapshot():
    ist = pytz.timezone('Asia/Kolkata')
    ts  = datetime.now(ist).strftime("%H:%M:%S")
    rows = []
    for sym, meta in ASSET_ROUTING.items():
        base = meta["base"] + round(random.uniform(-15, 15), 1)
        atm  = int(round(base / meta["step"]) * meta["step"])
        for strike in [atm - meta["step"], atm, atm + meta["step"]]:
            for opt in ["CE", "PE"]:
                ltp = (round(random.uniform(40, 260), 1)
                       if sym in ("NIFTY", "BANKNIFTY")
                       else round(random.uniform(6, 65), 1))
                rows.append({
                    "timestamp": ts, "asset": sym,
                    "formatted_symbol": f"{sym}{meta['exp']}{strike}{opt}",
                    "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                    "volume": random.randint(15000, 125000),
                    "ltp": ltp, "underlying": base,
                    "status": "🌙 OFF-HOURS FALLBACK",
                })
    return rows


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────
headers, sid, srv_id, auth_err = get_session()

if auth_err:
    st.error(f"🔴 Auth failed: {auth_err}")
else:
    st.success("🟢 Broker Connected — Live data active")

with st.expander("🔧 Diagnostic", expanded=bool(auth_err)):
    env_keys = ["KOTAK_CONSUMER_KEY", "KOTAK_MOBILE", "KOTAK_UCC", "KOTAK_MPIN", "KOTAK_TOTP_SECRET"]
    for k in env_keys:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    if auth_err:
        st.error(f"Auth error: {auth_err}")
    else:
        st.success(f"Session OK | SID: ...{str(sid)[-6:]}")

# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────
if "buffer" not in st.session_state:
    st.session_state["buffer"] = []

if headers:
    snap, got_live = capture_market_state(headers, str(sid))
    if got_live:
        st.session_state["buffer"] = snap
    elif not st.session_state["buffer"]:
        st.session_state["buffer"] = fallback_snapshot()
elif not st.session_state["buffer"]:
    st.session_state["buffer"] = fallback_snapshot()

all_df = pd.DataFrame(st.session_state["buffer"])
ist_now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
live_n  = len(all_df[all_df['status'].str.contains('LIVE', na=False)]) if not all_df.empty else 0
st.caption(
    f"📦 Rows: {len(all_df)} | 🟢 Live: {live_n} | "
    f"🌙 Fallback: {len(all_df) - live_n} | IST: {ist_now}"
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

# Refresh every 15s — gives enough time for quotes to complete
st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();}, 15000);</script>",
    height=0, width=0
)
