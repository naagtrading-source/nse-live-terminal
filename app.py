import streamlit as st
import pandas as pd
import os, pytz, pyotp, random, re, io, sys, contextlib
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="SNY Flow Terminal", layout="wide", page_icon="⚡")
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

# ── No hardcoded expiries or base prices ──────────────────────────────────────
INDICES = {
    "NIFTY":     {"fo_seg":"nse_fo","step":50,  "lot":75},
    "BANKNIFTY": {"fo_seg":"nse_fo","step":100, "lot":30},
    "FINNIFTY":  {"fo_seg":"nse_fo","step":50,  "lot":40},
    "MIDCPNIFTY":{"fo_seg":"nse_fo","step":25,  "lot":75},
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
    "GOLDM":     {"fo_seg":"mcx_fo","step":100,  "lot":10},
    "SILVERM":   {"fo_seg":"mcx_fo","step":1000, "lot":5},
    "CRUDEOIL":  {"fo_seg":"mcx_fo","step":100,  "lot":100},
    "NATURALGAS":{"fo_seg":"mcx_fo","step":10,   "lot":1250},
    "COPPER":    {"fo_seg":"mcx_fo","step":5,    "lot":2500},
}
SPIKE_THRESHOLD = 2.0
STRIKE_RANGE    = 3

# ── Silence SDK output WITHOUT mock patches ───────────────────────────────────
# The Neo SDK calls st.success() internally. We silence it by temporarily
# replacing the st module reference inside neo_api_client with a no-op object.

class _Sink:
    """Silent sink — absorbs any attribute access and calls."""
    def __getattr__(self, name): return self
    def __call__(self, *a, **kw): return self
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter([])
    def __bool__(self): return False

_SINK = _Sink()

def _silent(fn):
    """Run fn with Neo SDK's internal streamlit calls silenced via _Sink."""
    # Find and temporarily replace 'st' inside neo_api_client modules
    swapped = {}
    for mod_name, mod in list(sys.modules.items()):
        if not mod_name.startswith("neo_api_client"):
            continue
        d = getattr(mod, "__dict__", {})
        if "st" in d and d["st"] is not _SINK:
            swapped[mod_name] = ("st", d["st"])
            d["st"] = _SINK
        for fn_name in ("success","error","warning","info","write",
                        "markdown","spinner","empty","caption"):
            if fn_name in d and callable(d[fn_name]) and d[fn_name] is not _SINK:
                swapped[f"{mod_name}.{fn_name}"] = (fn_name, d[fn_name], mod_name)

    # Also silence individual imported functions
    for key, val in list(swapped.items()):
        if len(val) == 3:
            fn_name, orig, mod_name = val
            sys.modules[mod_name].__dict__[fn_name] = _SINK

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return fn()
    finally:
        # Restore everything
        for key, val in swapped.items():
            if "." not in key:
                mod_name = key
                attr, orig = val
                if mod_name in sys.modules:
                    sys.modules[mod_name].__dict__[attr] = orig
            else:
                fn_name, orig, mod_name = val
                if mod_name in sys.modules:
                    sys.modules[mod_name].__dict__[fn_name] = orig

# ── Auth (cached 23 min) ──────────────────────────────────────────────────────
@st.cache_resource(ttl=1380, show_spinner=False)
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
        r1  = _silent(lambda: api.totp_login(mobile_number=mob, ucc=ucc, totp=totp))
        logs.append(f"login={str(r1)[:150]}")
        r2  = _silent(lambda: api.totp_validate(mpin=mpin))
        logs.append(f"validate={str(r2)[:150]}")
        return api, "OK", logs
    except Exception as e:
        import traceback
        logs.append(traceback.format_exc()[-400:])
        return None, str(e)[:150], logs

api, auth_status, auth_logs = get_api()

# ── Field extractors ──────────────────────────────────────────────────────────
def _unwrap(raw):
    if raw is None: return {}
    if isinstance(raw, list): raw = raw[0] if raw else {}
    if isinstance(raw, dict):
        for dk in ("data","Data","result","Result"):
            if dk in raw:
                inn = raw[dk]
                if isinstance(inn, list) and inn:
                    return inn[0] if isinstance(inn[0], dict) else {}
                if isinstance(inn, dict): return inn
        return raw
    return {}

def _f(val):
    try:
        f = float(str(val).replace(",","").strip())
        return f if f > 0 else 0.0
    except: return 0.0

def _ltp(q):
    if not isinstance(q, dict): return 0.0
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close",
              "last_price","Close","LastTradePrice","ltp_rate","Ltp",
              "price","Price","trade_price","lasttradedprice"):
        v = q.get(k)
        if v not in (None,"",0,"0",0.0,"0.0","0.00"):
            f = _f(v)
            if f > 0: return f
    return 0.0

def _vol(q):
    if not isinstance(q, dict): return 0
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq","Volume"):
        v = q.get(k)
        if v not in (None,""):
            try: return max(0, int(_f(v)))
            except: pass
    return 0

def _oi(q):
    if not isinstance(q, dict): return 0
    for k in ("open_interest","oi","openInterest","OI"):
        v = q.get(k)
        if v not in (None,""):
            try: return max(0, int(_f(v)))
            except: pass
    return 0

def _tok(item):
    for k in ("pSymbol","token","instrument_token","Token","scripToken"):
        v = item.get(k)
        if v is not None: return str(v)
    return None

def _sym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol","symbol"):
        v = item.get(k)
        if v: return str(v).upper().strip()
    return ""

def _opt_type(item):
    raw = str(item.get("pOptionType", item.get("optTp",""))).strip().upper()
    if raw in ("CE","CALL","C"): return "CE"
    if raw in ("PE","PUT","P"):  return "PE"
    return None

def _strike_val(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price"):
        v = item.get(k)
        if v is not None:
            f = _f(v)
            if f > 0: return f
    return None

def _parse_expiry(item):
    """Extract expiry date from item. Returns datetime.date or None."""
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    # Try dedicated expiry fields first
    for k in ("pExpDate","expiry","expiryDate","ExpiryDate","expDate","pExpiryDate"):
        v = item.get(k)
        if not v: continue
        s = str(v).strip().upper()
        for fmt in ("%d%b%Y","%d-%b-%Y","%Y-%m-%d","%d/%m/%Y",
                    "%d%b%y","%d-%b-%y","%d %b %Y","%d %b %y"):
            try:
                d = datetime.strptime(s, fmt).date()
                if d >= today: return d
            except: pass
    # Parse from trading symbol e.g. NIFTY30JUN26FUT, GOLDM03JUL26CE
    s = _sym(item)
    m = re.search(r'(\d{1,2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2,4})', s)
    if m:
        day, mon, yr = m.groups()
        yr_int = int(yr) if len(yr)==4 else 2000+int(yr)
        try:
            d = datetime.strptime(f"{int(day):02d}{mon}{yr_int}", "%d%b%Y").date()
            if d >= today: return d
        except: pass
    return None

# ── Live quote ────────────────────────────────────────────────────────────────
def live_quote(token, seg):
    if not api or not token: return {}
    try:
        raw = _silent(lambda: api.get_live_quotes(
            [{"instrument_token": str(token), "exchange_segment": seg}]
        ))
        return _unwrap(raw)
    except: return {}

# ── Scrip cache (1 hr) ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def scrip_list(seg, symbol):
    if not api: return []
    try:
        r = _silent(lambda: api.search_scrip(exchange_segment=seg, symbol=symbol))
        if isinstance(r, dict): return r.get("data",[]) or r.get("result",[]) or []
        return r if isinstance(r, list) else []
    except: return []

# ── Volume history ─────────────────────────────────────────────────────────────
def _vh_update(key, v):
    if "vh" not in st.session_state: st.session_state["vh"] = defaultdict(list)
    h = st.session_state["vh"][key]
    h.append(v)
    if len(h) > 30: h.pop(0)

def _vh_avg(key):
    if "vh" not in st.session_state: return 0
    h = st.session_state["vh"].get(key, [])
    return sum(h[:-1])/len(h[:-1]) if len(h) >= 3 else 0

# ── Trend ─────────────────────────────────────────────────────────────────────
def _trend(q, opt):
    bq = int(_f(q.get("total_buy_quantity", q.get("buyQty", 0)) or 0))
    sq = int(_f(q.get("total_sell_quantity", q.get("sellQty", 0)) or 0))
    if bq > 0 and sq > 0:
        if bq > sq * 1.2: return "🟢 BUYING"
        if sq > bq * 1.2: return "🔴 SELLING"
        return "⚪ NEUTRAL"
    return "🟢 BULLISH" if opt == "CE" else "🔴 BEARISH"

# ── Core scanner ──────────────────────────────────────────────────────────────
def scan_symbol(symbol, meta):
    fo_seg = meta["fo_seg"]
    step   = meta["step"]
    today  = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    results = []

    fo = scrip_list(fo_seg, symbol)
    if not fo: return [], 0.0, []

    # ── Step 1: Find nearest FUT → underlying price ───────────────────────────
    futs = []
    for item in fo:
        s = _sym(item)
        if "FUT" not in s: continue
        d = _parse_expiry(item)
        if d and d >= today: futs.append((d, item))
    futs.sort(key=lambda x: x[0])

    und = 0.0
    for exp_d, item in futs:
        tok = _tok(item)
        if not tok: continue
        q   = live_quote(tok, fo_seg)
        ltp = _ltp(q)
        if ltp > 0:
            und = ltp
            # Add this FUT to results
            vol = _vol(q)
            key = (symbol, "FUT", str(exp_d))
            _vh_update(key, vol)
            avg = _vh_avg(key)
            spk = ((vol-avg)/avg*100) if avg > 0 else 0
            results.append({
                "symbol":symbol, "expiry":str(exp_d), "type":"FUT",
                "strike":"—", "opt":"FUT", "ltp":ltp, "volume":vol,
                "oi":_oi(q), "avg_vol":int(avg), "spike_pct":spk,
                "trend":"📈 LONG", "is_spike":spk>=SPIKE_THRESHOLD*100,
                "underlying":und, "formatted_symbol":_sym(item),
            })
            break  # Use only nearest FUT for underlying

    # For stocks: cash segment fallback
    if und <= 0 and "cm_seg" in meta:
        cm = scrip_list(meta["cm_seg"], symbol)
        for item in cm:
            s = _sym(item)
            if s in (f"{symbol}-EQ", symbol, f"{symbol}EQ"):
                tok = _tok(item)
                if tok:
                    q = live_quote(tok, meta["cm_seg"])
                    und = _ltp(q)
                    if und > 0: break

    if und <= 0: return results, 0.0, []

    # ── Step 2: Collect all unique expiries ───────────────────────────────────
    expiries = sorted(set(d for d, _ in futs))

    # ── Step 3: ATM strikes based on live underlying ──────────────────────────
    atm     = round(und / step) * step
    strikes = {atm + i*step for i in range(-STRIKE_RANGE, STRIKE_RANGE+1)}

    # ── Step 4: Scan all options ──────────────────────────────────────────────
    for item in fo:
        try:
            opt = _opt_type(item)
            if not opt: continue
            sk = _strike_val(item)
            if sk is None: continue
            # Only scan strikes near ATM
            if abs(sk - atm) > STRIKE_RANGE * step * 1.5: continue
            exp_d = _parse_expiry(item)
            if not exp_d or exp_d < today: continue
            tok = _tok(item)
            if not tok: continue
            q   = live_quote(tok, fo_seg)
            ltp = _ltp(q)
            vol = _vol(q)
            if ltp <= 0 and vol <= 0: continue
            key = (symbol, int(sk), opt, str(exp_d))
            _vh_update(key, vol)
            avg = _vh_avg(key)
            spk = ((vol-avg)/avg*100) if avg > 0 else 0
            results.append({
                "symbol":symbol, "expiry":str(exp_d), "type":"OPT",
                "strike":int(sk), "opt":opt, "ltp":ltp, "volume":vol,
                "oi":_oi(q), "avg_vol":int(avg), "spike_pct":spk,
                "trend":_trend(q, opt),
                "is_spike":spk >= SPIKE_THRESHOLD*100,
                "underlying":und, "formatted_symbol":_sym(item),
            })
        except: continue

    return results, und, expiries

# ── Render ────────────────────────────────────────────────────────────────────
def render_scanner(label, symbols_meta):
    st.markdown(f"#### {label}")
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    wd  = now.weekday()
    nse_live = (now.replace(hour=9,minute=15,second=0,microsecond=0) <= now <=
                now.replace(hour=15,minute=30,second=0,microsecond=0)) and wd < 5
    mcx_live = (wd < 5 and now.replace(hour=9,minute=0,second=0,microsecond=0) <= now <=
                now.replace(hour=23,minute=30,second=0,microsecond=0)) or \
               (wd == 5 and now.replace(hour=9,minute=0,second=0,microsecond=0) <= now <=
                now.replace(hour=14,minute=0,second=0,microsecond=0))
    is_mcx  = any("mcx" in m.get("fo_seg","") for m in symbols_meta.values())
    is_live = (mcx_live if is_mcx else nse_live) and auth_status == "OK"

    if not is_live:
        seg = "MCX" if is_mcx else "NSE"
        hrs = "9:00 AM–11:30 PM Mon–Fri, 9:00 AM–2:00 PM Sat" if is_mcx else "9:15 AM–3:30 PM Mon–Fri"
        st.info(f"🌙 {seg} market closed. Hours: {hrs} IST")

    all_rows = []
    ncols = min(len(symbols_meta), 3)
    cols  = st.columns(ncols)

    for idx, (symbol, meta) in enumerate(symbols_meta.items()):
        col = cols[idx % ncols]
        if is_live:
            with st.spinner(f"Scanning {symbol}..."):
                rows, und, expiries = scan_symbol(symbol, meta)
        else:
            rows, und, expiries = [], 0.0, []

        if not rows and not is_live:
            col.warning(f"⏳ {symbol}: Market closed")
            continue
        if not rows:
            col.warning(f"⏳ {symbol}: No live data yet")
            continue

        exp_str = " | ".join(str(e) for e in expiries[:3]) if expiries else "—"
        col.metric(f"**{symbol}**", f"₹{und:,.1f}")
        col.caption(f"Active expiries: {exp_str}")

        rows_s = sorted(rows, key=lambda x: x["spike_pct"], reverse=True)
        for r in rows_s[:8]:
            sk  = str(r["strike"]) if r["strike"] != "—" else "FUT"
            spk = f"+{r['spike_pct']:.0f}%" if r["spike_pct"] > 0 else "—"
            vol = f"{r['volume']:,}" if r["volume"] else "—"
            avg = f"{r['avg_vol']:,}" if r["avg_vol"] > 0 else "new"
            flg = "🚨 " if r["is_spike"] else ""
            line = (f"{flg}**{symbol} {sk} {r['opt']}** "
                    f"[{r['expiry']}] | LTP:₹{r['ltp']} | Vol:{vol}"
                    + (f" (avg {avg}) | **{spk}**" if r["avg_vol"] > 0 else "")
                    + f" | {r['trend']}")
            if r["is_spike"]:         col.error(line)
            elif r["spike_pct"] > 50: col.warning(line)
            else:                     col.info(line)

        all_rows.extend(rows_s)

    spikes = [r for r in all_rows if r["is_spike"]]
    if spikes:
        st.markdown("---")
        st.markdown("##### 🚨 Unusual Volume Alerts")
        df = pd.DataFrame([{
            "Symbol":r["symbol"], "Expiry":r["expiry"],
            "Strike":r["strike"], "Type":r["opt"],
            "LTP":f"₹{r['ltp']}", "Volume":f"{r['volume']:,}",
            "Avg Vol":f"{r['avg_vol']:,}" if r["avg_vol"] else "—",
            "Spike%":f"+{r['spike_pct']:.0f}%", "Trend":r["trend"],
            "Underlying":f"₹{r['underlying']:,.1f}",
        } for r in spikes])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── Header ────────────────────────────────────────────────────────────────────
ist_now = datetime.now(pytz.timezone("Asia/Kolkata"))
wd      = ist_now.weekday()
nse_l   = (ist_now.replace(hour=9,minute=15,second=0,microsecond=0) <= ist_now <=
            ist_now.replace(hour=15,minute=30,second=0,microsecond=0)) and wd < 5
mcx_l   = (wd < 5 and ist_now.replace(hour=9,minute=0,second=0,microsecond=0) <= ist_now <=
            ist_now.replace(hour=23,minute=30,second=0,microsecond=0)) or \
           (wd == 5 and ist_now.replace(hour=9,minute=0,second=0,microsecond=0) <= ist_now <=
            ist_now.replace(hour=14,minute=0,second=0,microsecond=0))

c1,c2,c3,c4 = st.columns(4)
c1.success("🟢 Broker Connected") if auth_status=="OK" else c1.error("🔴 Auth Failed")
c2.metric("NSE", "🟢 OPEN" if nse_l else "🔴 CLOSED")
c3.metric("MCX", "🟢 OPEN" if mcx_l else "🔴 CLOSED")
c4.metric("IST", ist_now.strftime("%H:%M:%S"))

with st.expander("🔧 Auth Diagnostic", expanded=(auth_status!="OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    for l in auth_logs: st.code(l)
    if auth_status == "OK":
        st.markdown("**Raw quote test (NIFTY nearest FUT):**")
        try:
            recs = scrip_list("nse_fo","NIFTY")
            futs = sorted(
                [(item,_sym(item),_parse_expiry(item)) for item in recs
                 if "FUT" in _sym(item) and _parse_expiry(item)],
                key=lambda x: x[2]
            )
            if futs:
                item,s,d = futs[0]
                tok = _tok(item)
                raw = _silent(lambda: api.get_live_quotes(
                    [{"instrument_token":str(tok),"exchange_segment":"nse_fo"}]
                ))
                st.code(f"Symbol: {s} | Expiry: {d} | Token: {tok}")
                st.code(f"Raw response: {str(raw)[:600]}")
            else:
                st.warning("No NIFTY FUT found")
                st.code(f"Total records: {len(recs)}")
                st.code(f"First 5: {[_sym(i) for i in recs[:5]]}")
        except Exception as e:
            st.error(str(e))

st.markdown("---")
t1,t2,t3 = st.tabs(["📈 Index Options & Futures","📊 Stock Options & Futures","🛢️ MCX Commodities"])
with t1: render_scanner("📈 Index Options & Futures", INDICES)
with t2: render_scanner("📊 Stock Options & Futures", STOCKS)
with t3: render_scanner("🛢️ MCX Commodities", COMMODITIES)

ms = 30000 if ((nse_l or mcx_l) and auth_status=="OK") else 300000
st.components.v1.html(
    f"<script>setTimeout(function(){{window.location.reload();}},{ms});</script>",
    height=0, width=0)
