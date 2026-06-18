import streamlit as st
import pandas as pd
import os, pytz, pyotp, random, sys, re
import unittest.mock as mock
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="SNY Institutional Flow", layout="wide", page_icon="⚡")
st.markdown("""
<style>
body,.stApp{background:#0d1117;color:#e6edf3}
div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
.stTabs [data-baseweb="tab-list"]{gap:6px;background:#161b22;padding:6px;border-radius:8px}
.stTabs [data-baseweb="tab"]{background:#21262d!important;color:#8b949e!important;
  border-radius:6px;padding:8px 20px;font-weight:500;border:1px solid #30363d!important}
.stTabs [aria-selected="true"]{background:#1f6feb!important;color:#fff!important;
  font-weight:700!important;border:1px solid #388bfd!important}
div[data-testid="metric-container"]{background:#161b22;border:1px solid #30363d;
  border-radius:8px;padding:12px 16px}
</style>""", unsafe_allow_html=True)

st.markdown("## ⚡ SNY Institutional Flow Terminal")
st.caption("Unusual Volume Scanner | Dynamic Expiry | NSE + MCX Real-Time")
st.markdown("---")

# ── Symbol registry — NO hardcoded expiries ───────────────────────────────────
INDICES = {
    "NIFTY":     {"fo_seg":"nse_fo","step":50,   "lot":75},
    "BANKNIFTY": {"fo_seg":"nse_fo","step":100,  "lot":30},
    "FINNIFTY":  {"fo_seg":"nse_fo","step":50,   "lot":40},
    "MIDCPNIFTY":{"fo_seg":"nse_fo","step":25,   "lot":75},
}
STOCKS = {
    "RELIANCE":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":50,  "lot":250},
    "HDFCBANK":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":20,  "lot":550},
    "TCS":       {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":100, "lot":175},
    "INFY":      {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":50,  "lot":400},
    "ICICIBANK": {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":20,  "lot":700},
    "SBIN":      {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":10,  "lot":1500},
}
COMMODITIES = {
    "GOLDM":      {"fo_seg":"mcx_fo","step":100,  "lot":10},
    "SILVERM":    {"fo_seg":"mcx_fo","step":1000, "lot":5},
    "CRUDEOIL":   {"fo_seg":"mcx_fo","step":100,  "lot":100},
    "NATURALGAS": {"fo_seg":"mcx_fo","step":10,   "lot":1250},
    "COPPER":     {"fo_seg":"mcx_fo","step":5,    "lot":2500},
}

SPIKE_THRESHOLD = 2.0
STRIKE_RANGE    = 3

# ── Suppress Streamlit calls inside Neo SDK ───────────────────────────────────
def _run(fn):
    """
    Run fn while suppressing any streamlit calls the Neo SDK makes internally.
    Uses stdout/stderr redirect + replaces st references inside neo modules only.
    Patches are always cleaned up and never leak to the main app.
    """
    import io, contextlib
    dummy = mock.MagicMock()
    dummy.__enter__ = lambda s: s
    dummy.__exit__  = lambda s, *a: False
    dummy.return_value = dummy

    # Collect patches ONLY for neo_api_client submodules
    patches = []
    for mod_name, mod in list(sys.modules.items()):
        if not mod_name.startswith("neo_api_client"):
            continue
        if not hasattr(mod, "__dict__"):
            continue
        # Replace the entire 'st' object the module holds
        if "st" in mod.__dict__:
            try: patches.append(mock.patch.object(mod, "st", dummy))
            except: pass
        # Replace any individually imported st functions
        for fn_name in ("success","error","warning","info","write","markdown",
                        "spinner","empty","caption","subheader","header","text"):
            if fn_name in mod.__dict__:
                try: patches.append(mock.patch.object(mod, fn_name, dummy))
                except: pass

    started = []
    for p in patches:
        try: p.start(); started.append(p)
        except: pass
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return fn()
    finally:
        for p in started:
            try: p.stop()
            except: pass

# ── Auth ──────────────────────────────────────────────────────────────────────
@st.cache_resource(ttl=1400, show_spinner=False)
def get_api():
    logs = []
    try:
        from neo_api_client import NeoAPI
        ck     = os.environ.get("KOTAK_CONSUMER_KEY","").strip()
        secret = os.environ.get("KOTAK_TOTP_SECRET","").replace(" ","")
        ucc    = os.environ.get("KOTAK_UCC","").strip()
        mpin   = os.environ.get("KOTAK_MPIN","").strip()
        mob    = os.environ.get("KOTAK_MOBILE","").strip().lstrip("+")
        if mob.startswith("91") and len(mob)==12: mob=mob[2:]
        elif mob.startswith("0") and len(mob)==11: mob=mob[1:]
        padded = secret+"="*(-len(secret)%8)
        try:    totp=pyotp.TOTP(padded).now()
        except: totp=pyotp.TOTP(secret).now()
        logs.append(f"TOTP={totp} mob=...{mob[-4:]}({len(mob)}d)")
        api = NeoAPI(environment="prod", consumer_key=ck)
        r1  = _run(lambda: api.totp_login(mobile_number=mob,ucc=ucc,totp=totp))
        logs.append(f"login={str(r1)[:120]}")
        r2  = _run(lambda: api.totp_validate(mpin=mpin))
        logs.append(f"validate={str(r2)[:120]}")
        return api,"OK",logs
    except Exception as e:
        import traceback
        logs.append(traceback.format_exc()[-300:])
        return None,str(e)[:120],logs

api,auth_status,auth_logs = get_api()

# Safety: ensure no st patches are active after auth
import streamlit as _st_real
import inspect
_st_fns = ["success","error","warning","info","write","markdown",
           "spinner","empty","caption","subheader","header","text"]
for _fn in _st_fns:
    _orig = getattr(_st_real, _fn, None)
    if _orig is not None and isinstance(_orig, mock.MagicMock):
        # This function got leaked — force reload streamlit to restore
        import importlib
        try: importlib.reload(_st_real)
        except: pass
        break

# ── Field extractors ──────────────────────────────────────────────────────────
def _unwrap(raw):
    if raw is None: return {}
    if isinstance(raw,list): raw=raw[0] if raw else {}
    if isinstance(raw,dict):
        for dk in ("data","Data","result","Result","quotes"):
            if dk in raw:
                inn=raw[dk]
                if isinstance(inn,list) and inn: return inn[0] if isinstance(inn[0],dict) else {}
                if isinstance(inn,dict): return inn
        return raw
    return {}

def _ltp(q):
    if not q or not isinstance(q,dict): return 0.0
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close",
              "last_price","Close","LastTradePrice","ltp_rate","ltP","Ltp",
              "price","Price","trade_price","regularMarketPrice","lasttradedprice"):
        v=q.get(k)
        if v not in (None,"",0,"0",0.0,"0.0","0.00"):
            try:
                f=float(str(v).replace(",",""))
                if f>0: return f
            except: pass
    return 0.0

def _vol(q):
    if not q: return 0
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq","total_traded_volume","Volume"):
        v=q.get(k)
        if v is not None:
            try: return int(float(str(v).replace(",","")))
            except: pass
    return 0

def _oi(q):
    if not q: return 0
    for k in ("open_interest","oi","openInterest","OI","open_int","openint"):
        v=q.get(k)
        if v is not None:
            try: return int(float(str(v).replace(",","")))
            except: pass
    return 0

def _tok(item):
    for k in ("pSymbol","token","instrument_token","Token","scripToken"):
        v=item.get(k)
        if v is not None: return str(v)
    return None

def _sym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol","Trading_Symbol","symbol"):
        v=item.get(k)
        if v: return str(v).upper()
    return ""

def _opt(item):
    raw=str(item.get("pOptionType",item.get("optTp",item.get("option_type","")))).strip().upper()
    return "CE" if raw in("CE","CALL","C") else "PE" if raw in("PE","PUT","P") else None

def _strike(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price","StrikePrice"):
        v=item.get(k)
        if v is not None:
            try: return float(v)
            except: pass
    return None

def _expiry_date(item):
    """Parse expiry date from scrip item. Returns datetime.date or None."""
    for k in ("pExpDate","expiry","expiryDate","ExpiryDate","expDate","exp_date","pExpiryDate"):
        v=item.get(k)
        if v:
            s=str(v).strip()
            for fmt in ("%d%b%Y","%d-%b-%Y","%Y-%m-%d","%d/%m/%Y","%d%b%y","%d-%b-%y","%b%Y"):
                try: return datetime.strptime(s.upper(),fmt).date()
                except: pass
            # Try extracting from trading symbol like GOLDM03JUL26FUT
            m=re.search(r'(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2,4})',s.upper())
            if m:
                d,mo,y=m.groups()
                yr=int(y) if len(y)==4 else 2000+int(y)
                try: return datetime.strptime(f"{d}{mo}{yr}","%d%b%Y").date()
                except: pass
    # Last resort: parse from trading symbol itself
    s=_sym(item)
    m=re.search(r'(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2,4})',s)
    if m:
        d,mo,y=m.groups()
        yr=int(y) if len(y)==4 else 2000+int(y)
        try: return datetime.strptime(f"{d}{mo}{yr}","%d%b%Y").date()
        except: pass
    return None

# ── Live quote ─────────────────────────────────────────────────────────────────
def live_quote(token, seg):
    if not api or not token: return {}
    try:
        raw=_run(lambda: api.get_live_quotes(
            [{"instrument_token":str(token),"exchange_segment":seg}]
        ))
        q=_unwrap(raw)
        return q if isinstance(q,dict) else {}
    except: return {}

# ── Scrip cache (1 hr) ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def scrip_list(seg, symbol):
    if not api: return []
    try:
        r=_run(lambda: api.search_scrip(exchange_segment=seg,symbol=symbol))
        if isinstance(r,dict): return r.get("data",[]) or r.get("result",[]) or []
        return r if isinstance(r,list) else []
    except: return []

# ── CORE: Discover expiries dynamically ───────────────────────────────────────
def get_expiries(fo_records, symbol):
    """
    From all scrip records, extract unique expiry dates for FUT and OPT contracts.
    Returns sorted list of (date, date_str) for current + next 2 expiries.
    """
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    dates = set()
    for item in fo_records:
        d = _expiry_date(item)
        if d and d >= today:
            dates.add(d)
    sorted_dates = sorted(dates)
    return sorted_dates[:3]  # current + next 2 expiries

def get_nearest_fut_ltp(fo_records, seg):
    """
    Find the nearest-expiry FUT, fetch its LTP. Returns (ltp, token, expiry_date, sym).
    """
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    futs  = []
    for item in fo_records:
        s = _sym(item)
        if "FUT" not in s: continue
        d = _expiry_date(item)
        if d and d >= today:
            futs.append((d, item))
    if not futs: return 0.0, None, None, ""
    futs.sort(key=lambda x: x[0])
    for exp_date, item in futs:
        tok = _tok(item)
        if not tok: continue
        q   = live_quote(tok, seg)
        ltp = _ltp(q)
        if ltp > 0:
            return ltp, tok, exp_date, _sym(item)
    return 0.0, None, None, ""

# ── Volume history ─────────────────────────────────────────────────────────────
def update_vol(key, v):
    if "vh" not in st.session_state: st.session_state["vh"]=defaultdict(list)
    h=st.session_state["vh"][key]
    h.append(v)
    if len(h)>20: h.pop(0)

def avg_vol(key):
    if "vh" not in st.session_state: return 0
    h=st.session_state["vh"].get(key,[])
    return sum(h[:-1])/len(h[:-1]) if len(h)>=2 else 0

# ── Trend ─────────────────────────────────────────────────────────────────────
def detect_trend(q, opt):
    bq=int(float(q.get("total_buy_quantity",q.get("buyQty",q.get("buy_qty",0)))or 0))
    sq=int(float(q.get("total_sell_quantity",q.get("sellQty",q.get("sell_qty",0)))or 0))
    if bq>0 and sq>0:
        if bq>sq*1.2: return "🟢 BUYING"
        if sq>bq*1.2: return "🔴 SELLING"
        return "⚪ NEUTRAL"
    return "🟢 BULLISH" if opt=="CE" else "🔴 BEARISH"

# ── Scanner ───────────────────────────────────────────────────────────────────
def scan_symbol(symbol, meta):
    fo_seg = meta["fo_seg"]
    step   = meta["step"]
    results= []

    fo = scrip_list(fo_seg, symbol)
    if not fo: return results, 0.0, []

    # ── 1. Discover all expiries dynamically ─────────────────────────────────
    expiries = get_expiries(fo, symbol)  # sorted list of datetime.date

    # ── 2. Get underlying price from nearest FUT ──────────────────────────────
    und, fut_tok, fut_exp, fut_sym = get_nearest_fut_ltp(fo, fo_seg)

    # For stocks: fallback to cash segment
    if und <= 0 and "cm_seg" in meta:
        cm = scrip_list(meta["cm_seg"], symbol)
        for item in cm:
            s=_sym(item)
            if s in (f"{symbol}-EQ",symbol,f"{symbol}EQ"):
                tok=_tok(item)
                if tok:
                    q=live_quote(tok, meta["cm_seg"])
                    und=_ltp(q)
                    if und>0: break

    if und <= 0: return results, 0.0, expiries

    # ── 3. FUT row for each expiry ────────────────────────────────────────────
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    for item in fo:
        s=_sym(item)
        if "FUT" not in s: continue
        d=_expiry_date(item)
        if not d or d<today: continue
        tok=_tok(item)
        if not tok: continue
        q=live_quote(tok, fo_seg)
        ltp=_ltp(q); vol=_vol(q)
        if ltp<=0 and vol<=0: continue
        key=(symbol,s,"FUT")
        update_vol(key,vol)
        avg=avg_vol(key)
        spk=((vol-avg)/avg*100) if avg>0 else 0
        results.append({
            "symbol":symbol,"expiry":str(d),"type":"FUT","strike":"—",
            "opt":"FUT","ltp":ltp,"volume":vol,"oi":_oi(q),
            "avg_vol":int(avg),"spike_pct":spk,
            "trend":"📈 LONG" if ltp>=und*0.999 else "📉 SHORT",
            "is_spike":spk>=SPIKE_THRESHOLD*100,"underlying":und,
            "formatted_symbol":s,
        })

    # ── 4. Options for each expiry ────────────────────────────────────────────
    atm    = round(und/step)*step
    strikes= [atm+i*step for i in range(-STRIKE_RANGE, STRIKE_RANGE+1)]

    for item in fo:
        try:
            opt=_opt(item)
            if not opt: continue
            sk=_strike(item)
            if sk is None: continue
            # Accept strikes within range of ATM
            if abs(sk-atm) > STRIKE_RANGE*step*1.5: continue
            d=_expiry_date(item)
            if not d or d<today: continue
            tok=_tok(item)
            if not tok: continue
            q=live_quote(tok,fo_seg)
            ltp=_ltp(q); vol=_vol(q)
            if ltp<=0 and vol<=0: continue
            key=(symbol,sk,opt,str(d))
            update_vol(key,vol)
            avg=avg_vol(key)
            spk=((vol-avg)/avg*100) if avg>0 else 0
            results.append({
                "symbol":symbol,"expiry":str(d),"type":"OPT",
                "strike":int(sk),"opt":opt,"ltp":ltp,"volume":vol,
                "oi":_oi(q),"avg_vol":int(avg),"spike_pct":spk,
                "trend":detect_trend(q,opt),
                "is_spike":spk>=SPIKE_THRESHOLD*100,"underlying":und,
                "formatted_symbol":_sym(item),
            })
        except: continue

    return results, und, expiries

# ── Render ────────────────────────────────────────────────────────────────────
def render_scanner(label, symbols_meta):
    st.markdown(f"#### {label}")

    ist=pytz.timezone("Asia/Kolkata")
    now=datetime.now(ist)
    wd=now.weekday()
    nse_live=(now.replace(hour=9,minute=15,second=0)<=now<=now.replace(hour=15,minute=30,second=0)) and wd<5
    mcx_live=((now.replace(hour=9,minute=0,second=0)<=now<=now.replace(hour=23,minute=30,second=0)) and wd<5) or \
             ((now.replace(hour=9,minute=0,second=0)<=now<=now.replace(hour=14,minute=0,second=0)) and wd==5)
    is_mcx=any("mcx" in m.get("fo_seg","") for m in symbols_meta.values())
    is_live=(mcx_live if is_mcx else nse_live) and auth_status=="OK"

    if not is_live:
        seg="MCX" if is_mcx else "NSE"
        hrs="9:00 AM–11:30 PM (Mon–Fri), 9:00 AM–2:00 PM (Sat)" if is_mcx else "9:15 AM–3:30 PM (Mon–Fri)"
        st.info(f"🌙 {seg} market closed or broker not connected. Hours: {hrs} IST")

    all_rows=[]
    ncols=min(len(symbols_meta),3)
    cols=st.columns(ncols)

    for idx,(symbol,meta) in enumerate(symbols_meta.items()):
        col=cols[idx%ncols]
        with col:
            if is_live:
                with st.spinner(f"Scanning {symbol}..."):
                    rows, und, expiries = scan_symbol(symbol, meta)
            else:
                rows, und, expiries = _fake_scan(symbol, meta), meta.get("base",0), []

            if not rows:
                st.warning(f"⏳ {symbol}: No data")
                continue

            und_val = rows[0]["underlying"] if rows else und
            exp_str = ", ".join(str(e) for e in expiries) if expiries else "—"
            st.metric(f"**{symbol}**", f"₹{und_val:,.1f}")
            st.caption(f"Expiries: {exp_str}")

            # Sort by spike desc, then show top rows
            rows_s=sorted(rows,key=lambda x:x["spike_pct"],reverse=True)
            for r in rows_s[:8]:
                sk   = str(r["strike"]) if r["strike"]!="—" else "FUT"
                exp  = r["expiry"]
                spk  = f"+{r['spike_pct']:.0f}%" if r["spike_pct"]>0 else "—"
                vol  = f"{r['volume']:,}" if r["volume"] else "—"
                avg  = f"{r['avg_vol']:,}" if r["avg_vol"] else "new"
                flag = "🚨 " if r["is_spike"] else ""

                line = (f"{flag}**{symbol} {sk} {r['opt']}** [{exp}] | "
                        f"LTP:₹{r['ltp']} | Vol:{vol}"
                        +(f" (avg {avg}) | Spike:**{spk}**" if r["avg_vol"] else "")
                        +f" | {r['trend']}")

                if r["is_spike"]:   st.error(line)
                elif r["spike_pct"]>50: st.warning(line)
                else:               st.info(line)

            all_rows.extend(rows_s)

    # Spike summary table
    spikes=[r for r in all_rows if r["is_spike"]]
    if spikes:
        st.markdown("---")
        st.markdown("##### 🚨 Unusual Volume Alerts")
        df=pd.DataFrame([{
            "Symbol":r["symbol"],"Expiry":r["expiry"],"Strike":r["strike"],
            "Type":r["opt"],"LTP":f"₹{r['ltp']}",
            "Volume":f"{r['volume']:,}","Avg Vol":f"{r['avg_vol']:,}" if r["avg_vol"] else "—",
            "Spike%":f"+{r['spike_pct']:.0f}%","Trend":r["trend"],
            "Underlying":f"₹{r['underlying']:,.1f}",
        } for r in spikes])
        st.dataframe(df,use_container_width=True,hide_index=True)

# ── Fake scan for off-hours preview ───────────────────────────────────────────
def _fake_scan(symbol, meta):
    step=meta.get("step",50); base=meta.get("base",1000)
    atm=round(base/step)*step; rows=[]
    today=datetime.now(pytz.timezone("Asia/Kolkata")).date()
    rows.append({
        "symbol":symbol,"expiry":str(today),"type":"FUT","strike":"—","opt":"FUT",
        "ltp":round(base*1.001,1),"volume":random.randint(5000,50000),
        "oi":random.randint(10000,200000),"avg_vol":random.randint(4000,40000),
        "spike_pct":random.uniform(-20,60),"trend":"📈 LONG",
        "is_spike":False,"underlying":base,"formatted_symbol":f"{symbol}FUT",
    })
    for i in range(-STRIKE_RANGE,STRIKE_RANGE+1):
        sk=atm+i*step
        for opt in["CE","PE"]:
            vol=random.randint(10000,80000)
            spike=random.random()<0.15
            vol_now=vol*random.uniform(2.5,5) if spike else vol
            avg=vol*random.uniform(0.8,1.2)
            spk=((vol_now-avg)/avg*100) if avg>0 else 0
            rows.append({
                "symbol":symbol,"expiry":str(today),"type":"OPT","strike":sk,
                "opt":opt,"ltp":round(abs(i-STRIKE_RANGE)*step*0.015*random.uniform(0.7,1.3),1),
                "volume":int(vol_now),"oi":random.randint(5000,500000),
                "avg_vol":int(avg),"spike_pct":spk,
                "trend":random.choice(["🟢 BUYING","🔴 SELLING","⚪ NEUTRAL"]),
                "is_spike":spk>=SPIKE_THRESHOLD*100,"underlying":base,
                "formatted_symbol":f"{symbol}{sk}{opt}",
            })
    return rows

# ── Header ────────────────────────────────────────────────────────────────────
ist_now=datetime.now(pytz.timezone("Asia/Kolkata"))
wd=ist_now.weekday()
nse_l=(ist_now.replace(hour=9,minute=15,second=0)<=ist_now<=ist_now.replace(hour=15,minute=30,second=0)) and wd<5
mcx_l=((ist_now.replace(hour=9,minute=0,second=0)<=ist_now<=ist_now.replace(hour=23,minute=30,second=0)) and wd<5) or \
      ((ist_now.replace(hour=9,minute=0,second=0)<=ist_now<=ist_now.replace(hour=14,minute=0,second=0)) and wd==5)

c1,c2,c3,c4=st.columns(4)
if auth_status=="OK":
    c1.success("🟢 Connected")
else:
    c1.error("🔴 Auth Failed")
c2.metric("NSE","🟢 OPEN" if nse_l else "🔴 CLOSED")
c3.metric("MCX","🟢 OPEN" if mcx_l else "🔴 CLOSED")
c4.metric("IST",ist_now.strftime("%H:%M:%S"))

with st.expander("🔧 Auth Diagnostic",expanded=(auth_status!="OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v=os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    for l in auth_logs: st.code(l)
    if auth_status=="OK":
        st.markdown("**Raw quote test — NIFTY FUT:**")
        try:
            recs=scrip_list("nse_fo","NIFTY")
            futs=[(item,_sym(item)) for item in recs if "FUT" in _sym(item)]
            if futs:
                item,s=futs[0]; tok=_tok(item)
                raw=_run(lambda: api.get_live_quotes(
                    [{"instrument_token":str(tok),"exchange_segment":"nse_fo"}]
                ))
                st.code(f"sym={s} tok={tok}")
                st.code(f"raw={str(raw)[:500]}")
            else:
                st.warning("No NIFTY FUT found in scrip list")
                st.code(f"First 3 records: {[_sym(i) for i in recs[:3]]}")
        except Exception as e:
            st.error(str(e))

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1,t2,t3=st.tabs([
    "📈 Index Options & Futures",
    "📊 Stock Options & Futures",
    "🛢️ MCX Commodities",
])
with t1: render_scanner("📈 Index Options & Futures",INDICES)
with t2: render_scanner("📊 Stock Options & Futures",STOCKS)
with t3: render_scanner("🛢️ MCX Commodities",COMMODITIES)

# Refresh: 30s market hours, 5 min otherwise
is_any_live=(nse_l or mcx_l) and auth_status=="OK"
ms=30000 if is_any_live else 300000
st.components.v1.html(
    f"<script>setTimeout(function(){{window.location.reload();}},{ms});</script>",
    height=0,width=0)
