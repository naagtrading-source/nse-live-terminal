import streamlit as st
import pandas as pd
import os, pytz, pyotp, random, requests, json
from datetime import datetime

st.set_page_config(page_title="SNY Flow Terminal", layout="wide", page_icon="🚨")
st.markdown("""
<style>
div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] {
    background-color: #1f2231 !important; color: #fff !important;
    border-radius: 4px 4px 0 0; padding: 6px 16px; }
.stTabs [aria-selected="true"] {
    background-color: #ff9f43 !important; color: #0b0c10 !important; font-weight: bold !important; }
</style>""", unsafe_allow_html=True)

st.title("⚡ SNY — QUANTITATIVE ALGORITHMIC ROUTING ENGINE")
st.markdown("### 🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Hybrid Core Engine | Real-Time Live Streaming & Automated Off-Hours Fallback")
st.markdown("---")

ASSET_ROUTING = {
    "NIFTY":     {"fo_seg":"nse_fo","is_fut":True, "step":50,  "base":23450,"exp":"23JUN26"},
    "BANKNIFTY": {"fo_seg":"nse_fo","is_fut":True, "step":100, "base":50600,"exp":"30JUN26"},
    "RELIANCE":  {"fo_seg":"nse_fo","is_fut":False,"step":20,  "base":2980, "exp":"30JUN26","cm_seg":"nse_cm"},
    "HDFCBANK":  {"fo_seg":"nse_fo","is_fut":False,"step":10,  "base":1610, "exp":"30JUN26","cm_seg":"nse_cm"},
    "TCS":       {"fo_seg":"nse_fo","is_fut":False,"step":50,  "base":3850, "exp":"30JUN26","cm_seg":"nse_cm"},
    "CRUDEOIL":  {"fo_seg":"mcx_fo","is_fut":True, "step":100, "base":6550, "exp":"17JUL26"},
    "GOLD":      {"fo_seg":"mcx_fo","is_fut":True, "step":100, "base":72800,"exp":"30JUN26"},
}

# ── AUTH using the SDK (only correct way — HTTP endpoints are undocumented) ───
@st.cache_resource(ttl=1500, show_spinner=False)
def get_session():
    logs = []
    try:
        from neo_api_client import NeoAPI
        import unittest.mock as mock

        ck     = os.environ.get("KOTAK_CONSUMER_KEY","").strip()
        secret = os.environ.get("KOTAK_TOTP_SECRET","").replace(" ","")
        ucc    = os.environ.get("KOTAK_UCC","").strip()
        mpin   = os.environ.get("KOTAK_MPIN","").strip()
        mob    = os.environ.get("KOTAK_MOBILE","").strip().lstrip("+")
        if mob.startswith("91") and len(mob)==12: mob = mob[2:]
        elif mob.startswith("0") and len(mob)==11: mob = mob[1:]

        padded = secret + "=" * (-len(secret) % 8)
        try:    totp = pyotp.TOTP(padded).now()
        except: totp = pyotp.TOTP(secret).now()
        logs.append(f"TOTP={totp} mob=...{mob[-4:]}({len(mob)}d)")

        api = NeoAPI(environment="prod", consumer_key=ck)
        logs.append(f"NeoAPI created")

        # The SDK imports streamlit internally as its own reference.
        # We must patch it inside the SDK's own module namespace.
        import neo_api_client
        dummy = mock.MagicMock()

        # Find all submodules that may call st
        import sys
        neo_modules = {k: v for k, v in sys.modules.items()
                       if k.startswith("neo_api_client") and hasattr(v, "__dict__")}
        logs.append(f"neo modules: {list(neo_modules.keys())}")

        patches = []
        for mod_name, mod in neo_modules.items():
            if hasattr(mod, "st"):
                patches.append(mock.patch.object(mod, "st", dummy))
                logs.append(f"patching st in {mod_name}")
            # Also patch individual st functions if imported directly
            for fn in ("success","error","warning","info","write","markdown","spinner"):
                if hasattr(mod, fn):
                    patches.append(mock.patch.object(mod, fn, dummy))
                    logs.append(f"patching {fn} in {mod_name}")

        # Apply all patches
        for p in patches:
            try: p.start()
            except: pass

        try:
            r1 = api.totp_login(mobile_number=mob, ucc=ucc, totp=totp)
        finally:
            for p in patches:
                try: p.stop()
                except: pass

        logs.append(f"totp_login type={type(r1).__name__}")
        logs.append(f"totp_login repr={str(r1)[:300]}")

        # The v2 SDK stores auth internally — check every possible attribute
        for attr in dir(api):
            if any(x in attr.lower() for x in ("auth","token","sid","session","access")):
                try:
                    val = getattr(api, attr)
                    if val and not callable(val) and len(str(val)) > 5:
                        logs.append(f"api.{attr} = {str(val)[:80]}")
                        captured[attr] = val
                except: pass

        # Also check api.configuration
        try:
            cfg = api.configuration
            for attr in dir(cfg):
                if any(x in attr.lower() for x in ("auth","token","sid","session","access","key")):
                    try:
                        val = getattr(cfg, attr)
                        if val and not callable(val) and len(str(val)) > 3:
                            logs.append(f"cfg.{attr} = {str(val)[:80]}")
                    except: pass
        except: pass

        # Now call totp_validate — SDK handles Auth/Sid internally after login
        # Re-apply patches for validate call
        patches2 = []
        neo_modules2 = {k: v for k, v in sys.modules.items()
                        if k.startswith("neo_api_client") and hasattr(v, "__dict__")}
        for mod_name, mod in neo_modules2.items():
            if hasattr(mod, "st"):
                patches2.append(mock.patch.object(mod, "st", dummy))
            for fn in ("success","error","warning","info","write","markdown","spinner"):
                if hasattr(mod, fn):
                    patches2.append(mock.patch.object(mod, fn, dummy))

        for p in patches2:
            try: p.start()
            except: pass
        try:
            r2 = api.totp_validate(mpin=mpin)
        finally:
            for p in patches2:
                try: p.stop()
                except: pass

        logs.append(f"totp_validate type={type(r2).__name__}")
        logs.append(f"totp_validate repr={str(r2)[:300]}")

        # Check for error in response
        if isinstance(r2, dict):
            errs = r2.get("error", [])
            if errs:
                # Try passing mpin positionally
                with mock.patch("streamlit.success", dummy), \
                     mock.patch("streamlit.error",   dummy), \
                     mock.patch("streamlit.warning", dummy), \
                     mock.patch("streamlit.info",    dummy), \
                     mock.patch("streamlit.write",   dummy):
                    r2b = api.totp_validate(mpin)
                logs.append(f"totp_validate(positional) repr={str(r2b)[:300]}")
                if isinstance(r2b, dict) and not r2b.get("error"):
                    r2 = r2b

        return api, "OK", logs

    except Exception as e:
        import traceback
        logs.append(f"Exception: {type(e).__name__}: {e}")
        logs.append(traceback.format_exc()[:500])
        return None, f"{type(e).__name__}: {str(e)[:150]}", logs


api, s_status, s_logs = get_session()

if s_status == "OK":
    st.success("🟢 Broker Connected — Live data active")
else:
    st.error(f"🔴 Auth failed: {s_status}")

with st.expander("🔧 Diagnostic", expanded=(s_status != "OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    st.markdown("**Auth log:**")
    for l in s_logs: st.code(l)

# ── SCRIP — cached 1 h ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _neo_patches():
    import sys, unittest.mock as mock
    dummy = mock.MagicMock()
    patches = []
    for k, v in sys.modules.items():
        if k.startswith("neo_api_client") and hasattr(v, "__dict__"):
            if hasattr(v, "st"):
                patches.append(mock.patch.object(v, "st", dummy))
            for fn in ("success","error","warning","info","write","markdown","spinner"):
                if hasattr(v, fn):
                    patches.append(mock.patch.object(v, fn, dummy))
    return patches

def _run_patched(fn):
    patches = _neo_patches()
    for p in patches:
        try: p.start()
        except: pass
    try:    return fn()
    finally:
        for p in patches:
            try: p.stop()
            except: pass

def get_scrip(seg, symbol):
    if api is None or s_status != "OK": return []
    try:
        r = _run_patched(lambda: api.search_scrip(exchange_segment=seg, symbol=symbol))
        if isinstance(r, dict): return r.get("data",[]) or r.get("result",[]) or []
        return r if isinstance(r,list) else []
    except Exception: return []

# ── QUOTE ────────────────────────────────────────────────────────────────────
def get_quote(token, seg):
    if api is None: return {}
    try:
        q = _run_patched(lambda: api.get_live_quotes([{"instrument_token": str(token), "exchange_segment": seg}]))
        if isinstance(q,list) and q: return q[0]
        if isinstance(q,dict):
            d=q.get("data",[])
            if d: return d[0]
    except: pass
    return {}

# ── HELPERS ──────────────────────────────────────────────────────────────────
def ltp(q):
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close"):
        v=q.get(k)
        if v not in(None,""):
            try:
                f=float(v)
                if f>0: return f
            except: pass
    return 0.0

def vol(q):
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq"):
        v=q.get(k)
        if v is not None:
            try: return int(float(v))
            except: pass
    return 0

def opt_t(raw):
    s=str(raw).strip().upper()
    return "CE" if s in("CE","CALL","C") else "PE" if s in("PE","PUT","P") else None

def has_exp(sym,tag): return tag.upper() in str(sym).upper()

def get_tok(item):
    for k in ("pSymbol","token","instrument_token","Token","scripToken"):
        v=item.get(k)
        if v is not None: return v
    return None

def get_sym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol"):
        v=item.get(k)
        if v: return str(v).upper()
    return ""

def get_sk(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price"):
        v=item.get(k)
        if v is not None:
            try: return int(float(v))
            except: pass
    return None

# ── CAPTURE ──────────────────────────────────────────────────────────────────
def capture():
    ist=pytz.timezone("Asia/Kolkata")
    ts=datetime.now(ist).strftime("%H:%M:%S")
    snap,live=[],False

    for sym,meta in ASSET_ROUTING.items():
        exp=meta["exp"]; fo=get_scrip(meta["fo_seg"],sym); und=0.0

        if meta["is_fut"]:
            for item in fo:
                s=get_sym(item)
                if "FUT" in s and has_exp(s,exp):
                    t=get_tok(item)
                    if t:
                        v=ltp(get_quote(t,meta["fo_seg"]))
                        if v>0: und=v; break
            if und<=0:
                for item in fo:
                    if "FUT" in get_sym(item):
                        t=get_tok(item)
                        if t:
                            v=ltp(get_quote(t,meta["fo_seg"]))
                            if v>0: und=v; break
        else:
            cm=get_scrip(meta["cm_seg"],sym)
            for item in cm:
                s=get_sym(item)
                if s in(f"{sym}-EQ",sym,f"{sym}EQ"):
                    t=get_tok(item)
                    if t:
                        v=ltp(get_quote(t,meta["cm_seg"]))
                        if v>0: und=v; break

        if und<=0: continue
        atm=int(round(und/meta["step"])*meta["step"])
        strikes={atm-meta["step"],atm,atm+meta["step"]}

        for item in fo:
            try:
                s=get_sym(item)
                if not has_exp(s,exp): continue
                o=opt_t(item.get("pOptionType",item.get("optTp","")))
                if not o: continue
                sk=get_sk(item)
                if sk not in strikes: continue
                t=get_tok(item)
                if not t: continue
                q=get_quote(t,meta["fo_seg"]); p=ltp(q)
                if p<=0: continue
                snap.append({"timestamp":ts,"asset":sym,"formatted_symbol":s,
                    "direction":"CALL ACCUMULATION" if o=="CE" else "PUT DISTRIBUTION",
                    "volume":vol(q),"ltp":p,"underlying":und,"status":"🟢 LIVE"})
                live=True
            except: continue
    return snap,live

def fallback():
    ist=pytz.timezone("Asia/Kolkata"); ts=datetime.now(ist).strftime("%H:%M:%S")
    rows=[]
    for sym,meta in ASSET_ROUTING.items():
        base=meta["base"]+round(random.uniform(-15,15),1)
        atm=int(round(base/meta["step"])*meta["step"])
        for sk in[atm-meta["step"],atm,atm+meta["step"]]:
            for o in["CE","PE"]:
                lp=(round(random.uniform(40,260),1) if sym in("NIFTY","BANKNIFTY")
                    else round(random.uniform(6,65),1))
                rows.append({"timestamp":ts,"asset":sym,
                    "formatted_symbol":f"{sym}{meta['exp']}{sk}{o}",
                    "direction":"CALL ACCUMULATION" if o=="CE" else "PUT DISTRIBUTION",
                    "volume":random.randint(15000,125000),"ltp":lp,
                    "underlying":base,"status":"🌙 OFF-HOURS FALLBACK"})
    return rows

# ── RUN ──────────────────────────────────────────────────────────────────────
if "buf" not in st.session_state: st.session_state["buf"]=[]

if api and s_status=="OK":
    snap,got=capture()
    if got: st.session_state["buf"]=snap
    elif not st.session_state["buf"]: st.session_state["buf"]=fallback()
elif not st.session_state["buf"]:
    st.session_state["buf"]=fallback()

df=pd.DataFrame(st.session_state["buf"])
ist_now=datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")
ln=len(df[df["status"].str.contains("LIVE",na=False)]) if not df.empty else 0
st.caption(f"📦 Rows:{len(df)} | 🟢 Live:{ln} | 🌙 Fallback:{len(df)-ln} | IST:{ist_now}")

def blk(asset,src):
    if src.empty: st.warning("⏳ No data..."); return
    f=src[src["asset"].str.upper()==asset.upper()]
    if f.empty: st.warning(f"⏳ No rows for {asset}"); return
    st.metric("Underlying",f"₹{f.iloc[0]['underlying']:,.1f}")
    for _,r in f.head(6).iterrows():
        d="🔵" if "CALL" in r["direction"] else "🔴"
        st.info(f"{d} **{r['formatted_symbol']}** | **{r['direction']}** | "
                f"Vol:{int(r['volume']):,} | **LTP:₹{r['ltp']}** | [{r['status']}]")

t1,t2,t3=st.tabs(["📈 Equity Indices","📊 Nifty 50 Stock Options","🛢️ MCX Commodities"])
with t1:
    st.markdown("#### ⚡ Exchange Registered Derivative Indices")
    c1,c2=st.columns(2)
    with c1: st.error("🦅 NIFTY");     blk("NIFTY",df)
    with c2: st.error("🦅 BANKNIFTY"); blk("BANKNIFTY",df)
with t2:
    st.markdown("#### 📊 High-Liquidity Equities")
    c1,c2,c3=st.columns(3)
    with c1: st.warning("💎 RELIANCE"); blk("RELIANCE",df)
    with c2: st.warning("💎 HDFCBANK"); blk("HDFCBANK",df)
    with c3: st.warning("💎 TCS");      blk("TCS",df)
with t3:
    st.markdown("#### 🛢️ MCX Commodities")
    c1,c2=st.columns(2)
    with c1: st.success("🔥 CRUDEOIL"); blk("CRUDEOIL",df)
    with c2: st.success("✨ GOLD");     blk("GOLD",df)

st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();},15000);</script>",
    height=0,width=0)
