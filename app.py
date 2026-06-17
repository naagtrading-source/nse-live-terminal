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

# ── Pure HTTP auth — no SDK needed for login ──────────────────────────────────
# Kotak Neo v2 endpoints (from inspecting SDK network calls)
HOST     = "https://gw-napi.kotaksecurities.com"
EP_LOGIN = f"{HOST}/login/1.0/login/v2/validate"
EP_MPIN  = f"{HOST}/login/1.0/login/v2/totp/validate"
EP_SCRIP = f"{HOST}/market-data/oms/1.0/scripmaster/search"
EP_QUOTE = f"{HOST}/market-data/oms/1.0/quotes/"

@st.cache_resource(ttl=1500, show_spinner=False)
def get_session():
    logs = []
    ck     = os.environ.get("KOTAK_CONSUMER_KEY","").strip()
    secret = os.environ.get("KOTAK_TOTP_SECRET","").replace(" ","")
    ucc    = os.environ.get("KOTAK_UCC","").strip()
    mpin   = os.environ.get("KOTAK_MPIN","").strip()
    mob    = os.environ.get("KOTAK_MOBILE","").strip().lstrip("+")
    if mob.startswith("91") and len(mob)==12: mob = mob[2:]
    elif mob.startswith("0") and len(mob)==11: mob = mob[1:]

    if not all([ck, secret, ucc, mpin, mob]):
        missing = [k for k,v in {"CK":ck,"SECRET":secret,"UCC":ucc,"MPIN":mpin,"MOB":mob}.items() if not v]
        return None, f"Missing: {missing}", logs

    # Pad secret to valid base32
    padded = secret + "=" * (-len(secret) % 8)
    try:
        totp = pyotp.TOTP(padded).now()
    except Exception:
        totp = pyotp.TOTP(secret).now()
    logs.append(f"TOTP={totp} mob=...{mob[-4:]}({len(mob)}d)")

    base_h = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ck}",
    }

    # ── Step 1: TOTP login ───────────────────────────────────────────────────
    try:
        r1 = requests.post(EP_LOGIN, headers=base_h,
            json={"mobileNumber": mob, "ucc": ucc, "totp": totp},
            timeout=15)
        logs.append(f"Login HTTP {r1.status_code}")
        raw1 = r1.text[:500]
        logs.append(f"Login raw: {raw1}")
    except Exception as e:
        return None, f"Login request failed: {e}", logs

    try:
        d1 = r1.json()
    except Exception:
        return None, f"Login non-JSON: {r1.text[:200]}", logs

    # Check for errors
    if d1.get("error") or d1.get("Error") or r1.status_code != 200:
        return None, f"Login error: {json.dumps(d1)[:300]}", logs

    # Extract token fields — log ALL keys so we can see exact names
    data1 = d1.get("data", d1)
    logs.append(f"Login data keys: {list(data1.keys()) if isinstance(data1,dict) else type(data1)}")
    logs.append(f"Login data: {str(data1)[:400]}")

    auth = (data1.get("Auth") or data1.get("auth") or
            data1.get("token") or data1.get("access_token") or
            data1.get("jwtToken") or data1.get("jwt_token") or "")
    sid  = (data1.get("SID")  or data1.get("sid")  or
            data1.get("Sid")  or data1.get("session_id") or "")
    srv  = (data1.get("ServerID") or data1.get("serverId") or
            data1.get("server_id") or "")

    logs.append(f"auth={'..'+auth[-8:] if auth else 'MISSING'} "
                f"sid={'..'+str(sid)[-6:] if sid else 'MISSING'} "
                f"srv={srv or 'MISSING'}")

    if not auth:
        return None, f"No auth token in login response. Keys={list(data1.keys()) if isinstance(data1,dict) else '?'}", logs

    # ── Step 2: MPIN validate ────────────────────────────────────────────────
    h2 = {
        **base_h,
        "Auth": auth,
        "sid":  sid,
        "Sid":  sid,
        "neo-fin-key": f"neotradeapi{sid}",
    }
    try:
        r2 = requests.post(EP_MPIN, headers=h2,
            json={"mpin": mpin},
            timeout=15)
        logs.append(f"Validate HTTP {r2.status_code}")
        raw2 = r2.text[:500]
        logs.append(f"Validate raw: {raw2}")
    except Exception as e:
        return None, f"Validate request failed: {e}", logs

    try:
        d2 = r2.json()
    except Exception:
        return None, f"Validate non-JSON: {r2.text[:200]}", logs

    if d2.get("error") or d2.get("Error") or r2.status_code != 200:
        return None, f"Validate error: {json.dumps(d2)[:300]}", logs

    data2 = d2.get("data", d2)
    logs.append(f"Validate data keys: {list(data2.keys()) if isinstance(data2,dict) else type(data2)}")
    logs.append(f"Validate data: {str(data2)[:400]}")

    # Final token (validate may return a new token)
    final_tok = (data2.get("token") or data2.get("Token") or
                 data2.get("accessToken") or data2.get("access_token") or
                 data2.get("jwtToken") or auth)
    final_sid = (data2.get("SID") or data2.get("sid") or sid)

    session_h = {
        **base_h,
        "Auth":        final_tok,
        "sid":         final_sid,
        "Sid":         final_sid,
        "neo-fin-key": f"neotradeapi{final_sid}",
    }
    logs.append("✅ Session established")
    return session_h, "OK", logs


result = get_session()
s_headers, s_status, s_logs = result

if s_status == "OK":
    st.success("🟢 Broker Connected — Live data active")
else:
    st.error(f"🔴 Auth failed: {s_status}")

with st.expander("🔧 Diagnostic", expanded=(s_status != "OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    st.markdown("**Auth log:**")
    for l in s_logs:
        st.code(l)

# ── SCRIP — cached 1 h ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_scrip(seg, symbol, _cache_key):
    if not s_headers: return []
    try:
        r = requests.get(EP_SCRIP, headers=s_headers,
            params={"exchSeg": seg, "symbol": symbol, "series": ""},
            timeout=10)
        d = r.json()
        if isinstance(d, dict):
            return d.get("data",[]) or d.get("result",[]) or []
        return d if isinstance(d,list) else []
    except Exception:
        return []

# ── QUOTE ────────────────────────────────────────────────────────────────────
def get_quote(token_id, seg):
    if not s_headers: return {}
    exch_map = {
        "nse_fo":("N","FO"), "nse_cm":("N","C"),
        "mcx_fo":("M","FO"), "bse_cm":("B","C"),
    }
    exch, etype = exch_map.get(seg, ("N","FO"))
    try:
        r = requests.get(EP_QUOTE, headers=s_headers,
            params={
                "instrument_token": str(token_id),
                "market_protection": "0",
                "scrip_token": str(token_id),
                "exch": exch,
                "exchType": etype,
            }, timeout=8)
        d = r.json()
        items = d.get("data", d) if isinstance(d,dict) else d
        if isinstance(items,list) and items: return items[0]
        if isinstance(items,dict): return items
    except Exception:
        pass
    return {}

# ── HELPERS ──────────────────────────────────────────────────────────────────
def ltp(q):
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close"):
        v = q.get(k)
        if v not in (None,""):
            try:
                f=float(v)
                if f>0: return f
            except: pass
    return 0.0

def vol(q):
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq"):
        v = q.get(k)
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
    cache_key = str(s_headers.get("sid","")) if s_headers else ""

    for sym,meta in ASSET_ROUTING.items():
        exp=meta["exp"]; fo=get_scrip(meta["fo_seg"],sym,cache_key); und=0.0

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
            cm=get_scrip(meta["cm_seg"],sym,cache_key)
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

if s_headers and s_status=="OK":
    snap,got=capture()
    if got: st.session_state["buf"]=snap
    elif not st.session_state["buf"]: st.session_state["buf"]=fallback()
elif not st.session_state["buf"]:
    st.session_state["buf"]=fallback()

df=pd.DataFrame(st.session_state["buf"])
ist_now=datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")
ln=len(df[df["status"].str.contains("LIVE",na=False)]) if not df.empty else 0
st.caption(f"📦 Rows:{len(df)} | 🟢 Live:{ln} | 🌙 Fallback:{len(df)-ln} | IST:{ist_now}")

# ── RENDER ───────────────────────────────────────────────────────────────────
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
