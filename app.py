import streamlit as st
import pandas as pd
import os
import pytz
import pyotp
import random
from datetime import datetime

st.set_page_config(page_title="SNY Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
<style>
div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] {
    background-color: #1f2231 !important; color: #ffffff !important;
    border-radius: 4px 4px 0 0; padding: 6px 16px;
}
.stTabs [aria-selected="true"] {
    background-color: #ff9f43 !important; color: #0b0c10 !important; font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.title("⚡ SNY — QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Hybrid Core Engine | Real-Time Live Streaming & Automated Off-Hours Fallback")
st.markdown("---")

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
# BROKER SESSION — cached 25 min so TOTP not re-run every reload
# neo_api_client imported INSIDE the cached function so it only
# loads once and stays alive in the cache object (not re-imported).
# ─────────────────────────────────────────────
@st.cache_resource(ttl=1500, show_spinner=False)
def get_api():
    logs = []
    try:
        from neo_api_client import NeoAPI   # heavy import — happens once only
        logs.append("✅ SDK imported")

        ck = os.environ.get("KOTAK_CONSUMER_KEY", "")
        if not ck:
            return None, "MISSING KOTAK_CONSUMER_KEY", logs

        api = NeoAPI(environment="prod", consumer_key=ck)
        logs.append(f"✅ NeoAPI created (...{ck[-6:]})")

        secret = os.environ.get("KOTAK_TOTP_SECRET", "").replace(" ", "")
        totp   = pyotp.TOTP(secret).now()
        logs.append(f"✅ TOTP: {totp}")

        mob = os.environ.get("KOTAK_MOBILE", "").strip().lstrip("+")
        if mob.startswith("91") and len(mob) == 12:
            mob = mob[2:]
        elif mob.startswith("0") and len(mob) == 11:
            mob = mob[1:]
        ucc  = os.environ.get("KOTAK_UCC", "")
        mpin = os.environ.get("KOTAK_MPIN", "")
        logs.append(f"✅ Mobile: ...{mob[-4:]} ({len(mob)} digits)")

        r1 = api.totp_login(mobile_number=mob, ucc=ucc, totp=totp)
        logs.append(f"✅ totp_login → {str(r1)[:250]}")

        # Pull Auth + SID from login response
        auth, sid = None, None
        if isinstance(r1, dict):
            d = r1.get("data", r1)
            auth = d.get("Auth") or d.get("auth") or d.get("token")
            sid  = d.get("SID")  or d.get("sid")

        try:
            if auth and sid:
                r2 = api.totp_validate(mpin=mpin, Auth=auth, sid=sid)
            elif auth:
                r2 = api.totp_validate(mpin=mpin, Auth=auth)
            else:
                r2 = api.totp_validate(mpin=mpin)
        except TypeError:
            r2 = api.totp_validate(mpin=mpin)

        logs.append(f"✅ totp_validate → {str(r2)[:250]}")
        return api, "OK", logs

    except Exception as e:
        logs.append(f"❌ {type(e).__name__}: {e}")
        return None, f"{type(e).__name__}: {str(e)[:200]}", logs


# ─────────────────────────────────────────────
# SCRIP MASTER — cached 1 hour (large, rarely changes)
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_scrip(fo_seg, symbol):
    api, status, _ = get_api()
    if api is None or status != "OK":
        return []
    try:
        r = api.search_scrip(exchange_segment=fo_seg, symbol=symbol)
        if isinstance(r, dict):
            return r.get("data", []) or r.get("result", []) or []
        return r if isinstance(r, list) else []
    except Exception:
        return []


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def safe_ltp(q):
    for k in ("last_traded_price", "ltp", "lastPrice", "LTP", "c", "close"):
        v = q.get(k)
        if v is not None and v != "":
            try:
                f = float(v)
                if f > 0:
                    return f
            except Exception:
                continue
    return 0.0

def safe_vol(q):
    for k in ("volume", "vol", "tradedQuantity", "totalTradedVolume", "ltq"):
        v = q.get(k)
        if v is not None:
            try:
                return int(float(v))
            except Exception:
                continue
    return 0

def fetch_quote(api, token, seg):
    try:
        q = api.get_live_quotes([{"instrument_token": str(token), "exchange_segment": seg}])
        if isinstance(q, list) and q:
            return q[0]
        if isinstance(q, dict):
            d = q.get("data", [])
            if d:
                return d[0]
    except Exception:
        pass
    return {}

def norm_opt(raw):
    s = str(raw).strip().upper()
    return "CE" if s in ("CE","CALL","C") else "PE" if s in ("PE","PUT","P") else None

def exp_in(sym, tag):
    return tag.upper() in str(sym).upper()

def tok(item):
    for k in ("pSymbol","token","instrument_token","Token"):
        v = item.get(k)
        if v is not None:
            return v
    return None

def tsym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol"):
        v = item.get(k)
        if v:
            return str(v).upper()
    return ""

def strike(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price"):
        v = item.get(k)
        if v is not None:
            try:
                return int(float(v))
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────
# MARKET DATA  (only quote calls on each reload)
# ─────────────────────────────────────────────
def capture(api):
    ist = pytz.timezone("Asia/Kolkata")
    ts  = datetime.now(ist).strftime("%H:%M:%S")
    snap, live = [], False

    for sym, meta in ASSET_ROUTING.items():
        exp  = meta["exp"]
        fo   = get_scrip(meta["fo_seg"], sym)
        und  = 0.0

        if meta["is_fut"]:
            for item in fo:
                s = tsym(item)
                if "FUT" in s and exp_in(s, exp):
                    t = tok(item)
                    if t:
                        q = fetch_quote(api, t, meta["fo_seg"])
                        ltp = safe_ltp(q)
                        if ltp > 0:
                            und = ltp; break
            if und <= 0:               # fallback: nearest fut
                for item in fo:
                    if "FUT" in tsym(item):
                        t = tok(item)
                        if t:
                            q = fetch_quote(api, t, meta["fo_seg"])
                            ltp = safe_ltp(q)
                            if ltp > 0:
                                und = ltp; break
        else:
            cm = get_scrip(meta["cm_seg"], sym)
            for item in cm:
                s = tsym(item)
                if s in (f"{sym}-EQ", sym, f"{sym}EQ"):
                    t = tok(item)
                    if t:
                        q = fetch_quote(api, t, meta["cm_seg"])
                        ltp = safe_ltp(q)
                        if ltp > 0:
                            und = ltp; break

        if und <= 0:
            continue

        atm     = int(round(und / meta["step"]) * meta["step"])
        strikes = {atm - meta["step"], atm, atm + meta["step"]}

        for item in fo:
            try:
                s = tsym(item)
                if not exp_in(s, exp):
                    continue
                opt = norm_opt(item.get("pOptionType", item.get("optTp", "")))
                if not opt:
                    continue
                sk = strike(item)
                if sk not in strikes:
                    continue
                t = tok(item)
                if not t:
                    continue
                q   = fetch_quote(api, t, meta["fo_seg"])
                ltp = safe_ltp(q)
                if ltp <= 0:
                    continue
                snap.append({
                    "timestamp": ts, "asset": sym, "formatted_symbol": s,
                    "direction": "CALL ACCUMULATION" if opt=="CE" else "PUT DISTRIBUTION",
                    "volume": safe_vol(q), "ltp": ltp,
                    "underlying": und, "status": "🟢 LIVE",
                })
                live = True
            except Exception:
                continue

    return snap, live


def fallback():
    ist = pytz.timezone("Asia/Kolkata")
    ts  = datetime.now(ist).strftime("%H:%M:%S")
    rows = []
    for sym, meta in ASSET_ROUTING.items():
        base = meta["base"] + round(random.uniform(-15, 15), 1)
        atm  = int(round(base / meta["step"]) * meta["step"])
        for sk in [atm - meta["step"], atm, atm + meta["step"]]:
            for opt in ["CE", "PE"]:
                ltp = (round(random.uniform(40,260),1)
                       if sym in ("NIFTY","BANKNIFTY")
                       else round(random.uniform(6,65),1))
                rows.append({
                    "timestamp": ts, "asset": sym,
                    "formatted_symbol": f"{sym}{meta['exp']}{sk}{opt}",
                    "direction": "CALL ACCUMULATION" if opt=="CE" else "PUT DISTRIBUTION",
                    "volume": random.randint(15000,125000),
                    "ltp": ltp, "underlying": base,
                    "status": "🌙 OFF-HOURS FALLBACK",
                })
    return rows


# ─────────────────────────────────────────────
# BOOT
# ─────────────────────────────────────────────
api, status, logs = get_api()

if status == "OK":
    st.success("🟢 Broker Connected — Live data active")
else:
    st.error(f"🔴 Auth failed: {status}")

with st.expander("🔧 Diagnostic", expanded=(status != "OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    st.markdown("**Auth log:**")
    for l in logs:
        st.code(l)

if "buf" not in st.session_state:
    st.session_state["buf"] = []

if api and status == "OK":
    snap, got_live = capture(api)
    if got_live:
        st.session_state["buf"] = snap
    elif not st.session_state["buf"]:
        st.session_state["buf"] = fallback()
elif not st.session_state["buf"]:
    st.session_state["buf"] = fallback()

df = pd.DataFrame(st.session_state["buf"])
ist_now  = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")
live_n   = len(df[df["status"].str.contains("LIVE", na=False)]) if not df.empty else 0
st.caption(f"📦 Rows: {len(df)} | 🟢 Live: {live_n} | 🌙 Fallback: {len(df)-live_n} | IST: {ist_now}")


# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────
def block(asset, src):
    if src.empty:
        st.warning("⏳ No data..."); return
    f = src[src["asset"].str.upper() == asset.upper()]
    if f.empty:
        st.warning(f"⏳ No rows for {asset}"); return
    st.metric("Underlying", f"₹{f.iloc[0]['underlying']:,.1f}")
    for _, r in f.head(6).iterrows():
        dot = "🔵" if "CALL" in r["direction"] else "🔴"
        st.info(f"{dot} **{r['formatted_symbol']}** | **{r['direction']}** | "
                f"Vol: {int(r['volume']):,} | **LTP: ₹{r['ltp']}** | [{r['status']}]")

t1, t2, t3 = st.tabs(["📈 Equity Indices", "📊 Nifty 50 Stock Options", "🛢️ MCX Commodities"])

with t1:
    st.markdown("#### ⚡ Exchange Registered Derivative Indices")
    c1, c2 = st.columns(2)
    with c1: st.error("🦅 NIFTY");     block("NIFTY", df)
    with c2: st.error("🦅 BANKNIFTY"); block("BANKNIFTY", df)

with t2:
    st.markdown("#### 📊 High-Liquidity Equities")
    c1, c2, c3 = st.columns(3)
    with c1: st.warning("💎 RELIANCE"); block("RELIANCE", df)
    with c2: st.warning("💎 HDFCBANK"); block("HDFCBANK", df)
    with c3: st.warning("💎 TCS");      block("TCS", df)

with t3:
    st.markdown("#### 🛢️ MCX Commodities")
    c1, c2 = st.columns(2)
    with c1: st.success("🔥 CRUDEOIL"); block("CRUDEOIL", df)
    with c2: st.success("✨ GOLD");     block("GOLD", df)

st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();},15000);</script>",
    height=0, width=0
)
