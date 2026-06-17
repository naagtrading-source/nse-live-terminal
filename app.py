import streamlit as st
import pandas as pd
import os, pytz, pyotp, random, sys, unittest.mock as mock
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="SNY Institutional Flow", layout="wide", page_icon="⚡")

st.markdown("""
<style>
body, .stApp { background-color: #0d1117; color: #e6edf3; }
div[data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; background: #161b22; padding: 6px; border-radius: 8px; }
.stTabs [data-baseweb="tab"] {
    background-color: #21262d !important; color: #8b949e !important;
    border-radius: 6px; padding: 8px 20px; font-weight: 500; border: 1px solid #30363d !important;
}
.stTabs [aria-selected="true"] {
    background-color: #1f6feb !important; color: #ffffff !important;
    font-weight: 700 !important; border: 1px solid #388bfd !important;
}
div[data-testid="metric-container"] {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 12px 16px;
}
.stAlert { border-radius: 8px; }
</style>""", unsafe_allow_html=True)

st.markdown("## ⚡ SNY Institutional Flow Terminal")
st.caption("Unusual Volume Scanner | Real-Time Options & Futures | NSE + MCX")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
INDICES = {
    # Fallback base prices only — live prices fetched from API during market hours
    "NIFTY":     {"fo_seg":"nse_fo","step":50,  "base":24400,"exp":"26JUN26","lot":75},
    "BANKNIFTY": {"fo_seg":"nse_fo","step":100, "base":54000,"exp":"25JUN26","lot":30},
    "FINNIFTY":  {"fo_seg":"nse_fo","step":50,  "base":24000,"exp":"24JUN26","lot":40},
    "MIDCPNIFTY":{"fo_seg":"nse_fo","step":25,  "base":12500,"exp":"26JUN26","lot":75},
    "SENSEX":    {"fo_seg":"bse_fo","step":100, "base":80500,"exp":"27JUN26","lot":10},
}

STOCKS = {
    # Fallback base prices only — live prices fetched from API during market hours
    "RELIANCE":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":50,  "base":1450, "exp":"26JUN26","lot":250},
    "HDFCBANK":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":20,  "base":1950, "exp":"26JUN26","lot":550},
    "TCS":       {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":100, "base":3600, "exp":"26JUN26","lot":175},
    "INFY":      {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":50,  "base":1650, "exp":"26JUN26","lot":400},
    "ICICIBANK": {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":20,  "base":1450, "exp":"26JUN26","lot":700},
    "SBIN":      {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":10,  "base":840,  "exp":"26JUN26","lot":1500},
}

COMMODITIES = {
    # MCX prices as of Jun 2026 — used only as fallback when market is closed
    # Live prices always fetched from API during market hours
    "GOLD":      {"fo_seg":"mcx_fo","step":100,  "base":96000, "exp":"05AUG26","lot":100},
    "SILVER":    {"fo_seg":"mcx_fo","step":100,  "base":93000, "exp":"05JUL26","lot":30},
    "CRUDEOIL":  {"fo_seg":"mcx_fo","step":100,  "base":6500,  "exp":"17JUL26","lot":100},
    "NATURALGAS":{"fo_seg":"mcx_fo","step":10,   "base":330,   "exp":"25JUL26","lot":1250},
    "COPPER":    {"fo_seg":"mcx_fo","step":5,    "base":870,   "exp":"28JUL26","lot":2500},
}

# Volume spike threshold: flag if current vol > N× average
SPIKE_THRESHOLD = 2.0
# Strikes to scan around ATM
STRIKE_RANGE    = 3

# ─────────────────────────────────────────────────────────────────────────────
# SDK AUTH  (cached 25 min)
# ─────────────────────────────────────────────────────────────────────────────
def _patch_neo_st():
    """Return list of patches that suppress all streamlit calls inside neo SDK."""
    dummy = mock.MagicMock()
    patches = []
    for mod_name, mod in list(sys.modules.items()):
        if "neo" in mod_name.lower() and hasattr(mod, "__dict__"):
            if hasattr(mod, "st"):
                try: patches.append(mock.patch.object(mod, "st", dummy))
                except: pass
            for fn in ("success","error","warning","info","write","markdown","spinner","empty","caption"):
                if hasattr(mod, fn):
                    try: patches.append(mock.patch.object(mod, fn, dummy))
                    except: pass
    # Also patch top-level streamlit in case SDK uses it directly
    import streamlit as _st
    for fn in ("success","error","warning","info","write","markdown","spinner","empty","caption"):
        try: patches.append(mock.patch.object(_st, fn, dummy))
        except: pass
    return patches

def _run(fn):
    patches = _patch_neo_st()
    for p in patches:
        try: p.start()
        except: pass
    try:    return fn()
    except Exception as e: raise e
    finally:
        for p in patches:
            try: p.stop()
            except: pass

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
        if mob.startswith("91") and len(mob)==12: mob = mob[2:]
        elif mob.startswith("0") and len(mob)==11: mob = mob[1:]

        # Pad base32 secret
        padded = secret + "=" * (-len(secret) % 8)
        try:    totp = pyotp.TOTP(padded).now()
        except: totp = pyotp.TOTP(secret).now()
        logs.append(f"TOTP={totp} mob=...{mob[-4:]}({len(mob)}d)")

        api = NeoAPI(environment="prod", consumer_key=ck)

        # Login — suppress all internal st calls
        r1 = _run(lambda: api.totp_login(mobile_number=mob, ucc=ucc, totp=totp))
        logs.append(f"login type={type(r1).__name__} val={str(r1)[:200]}")

        # Validate — SDK stores Auth/SID internally after login; just pass mpin
        r2 = _run(lambda: api.totp_validate(mpin=mpin))
        logs.append(f"validate type={type(r2).__name__} val={str(r2)[:200]}")

        # Check validate didn't error
        if isinstance(r2, dict) and r2.get("error"):
            errs = r2["error"]
            # If missing Auth/Sid, it means login didn't store session → try session_2fa
            logs.append(f"validate error: {errs}")
            # Try alternative method names
            for method in ["session_2fa","login_with_totp","complete_login"]:
                if hasattr(api, method):
                    r2b = _run(lambda: getattr(api, method)(mpin=mpin))
                    logs.append(f"{method} → {str(r2b)[:150]}")
                    if isinstance(r2b, dict) and not r2b.get("error"):
                        r2 = r2b
                        break

        logs.append("✅ Auth complete")
        return api, "OK", logs

    except Exception as e:
        import traceback
        logs.append(f"❌ {type(e).__name__}: {e}")
        logs.append(traceback.format_exc()[-400:])
        return None, str(e)[:150], logs

api, auth_status, auth_logs = get_api()

# ─────────────────────────────────────────────────────────────────────────────
# SCRIP CACHE  (1 hour — large payload, rarely changes)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def scrip_list(seg, symbol):
    if api is None: return []
    try:
        r = _run(lambda: api.search_scrip(exchange_segment=seg, symbol=symbol))
        if isinstance(r, dict): return r.get("data",[]) or r.get("result",[]) or []
        return r if isinstance(r,list) else []
    except: return []

# ─────────────────────────────────────────────────────────────────────────────
# LIVE QUOTE
# ─────────────────────────────────────────────────────────────────────────────
def live_quote(token, seg):
    if api is None: return {}
    try:
        q = _run(lambda: api.get_live_quotes(
            [{"instrument_token": str(token), "exchange_segment": seg}]
        ))
        if isinstance(q, list) and q: return q[0]
        if isinstance(q, dict):
            d = q.get("data", [])
            if d: return d[0]
    except: pass
    return {}

# ─────────────────────────────────────────────────────────────────────────────
# FIELD EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────
def _ltp(q):
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close","last_price"):
        v = q.get(k)
        if v not in (None, "", 0, "0"):
            try:
                f = float(v)
                if f > 0: return f
            except: pass
    return 0.0

def _vol(q):
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq","total_traded_volume"):
        v = q.get(k)
        if v is not None:
            try: return int(float(v))
            except: pass
    return 0

def _oi(q):
    for k in ("open_interest","oi","openInterest","OI","open_int"):
        v = q.get(k)
        if v is not None:
            try: return int(float(v))
            except: pass
    return 0

def _tok(item):
    for k in ("pSymbol","token","instrument_token","Token","scripToken"):
        v = item.get(k)
        if v is not None: return v
    return None

def _sym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol","Trading_Symbol"):
        v = item.get(k)
        if v: return str(v).upper()
    return ""

def _strike(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price","StrikePrice"):
        v = item.get(k)
        if v is not None:
            try: return int(float(v))
            except: pass
    return None

def _opt(item):
    raw = str(item.get("pOptionType", item.get("optTp", item.get("option_type","")))).strip().upper()
    return "CE" if raw in("CE","CALL","C") else "PE" if raw in("PE","PUT","P") else None

def _exp_match(sym, tag):
    return tag.upper() in sym.upper()

# ─────────────────────────────────────────────────────────────────────────────
# VOLUME SPIKE DETECTION
# History stored in session_state keyed by (symbol, strike, opt_type)
# ─────────────────────────────────────────────────────────────────────────────
def update_vol_history(key, vol_now):
    if "vol_history" not in st.session_state:
        st.session_state["vol_history"] = defaultdict(list)
    hist = st.session_state["vol_history"][key]
    hist.append(vol_now)
    if len(hist) > 20: hist.pop(0)  # keep last 20 samples

def avg_vol(key):
    if "vol_history" not in st.session_state: return 0
    hist = st.session_state["vol_history"].get(key, [])
    if len(hist) < 2: return 0
    return sum(hist[:-1]) / len(hist[:-1])  # exclude current reading

def vol_spike_pct(current, average):
    if average <= 0: return 0
    return ((current - average) / average) * 100

# ─────────────────────────────────────────────────────────────────────────────
# TREND (buying vs selling pressure)
# ─────────────────────────────────────────────────────────────────────────────
def detect_trend(q, opt_type):
    ltp_val = _ltp(q)
    # Use bid/ask if available
    bid = float(q.get("bid_price", q.get("best_bid_price", q.get("bidPrice", 0))) or 0)
    ask = float(q.get("ask_price", q.get("best_ask_price", q.get("askPrice", 0))) or 0)
    buy_qty = int(float(q.get("total_buy_quantity", q.get("buy_qty", q.get("buyQty", 0))) or 0))
    sell_qty = int(float(q.get("total_sell_quantity", q.get("sell_qty", q.get("sellQty", 0))) or 0))

    if buy_qty > 0 and sell_qty > 0:
        if buy_qty > sell_qty * 1.2:
            return "🟢 BUYING", "green"
        elif sell_qty > buy_qty * 1.2:
            return "🔴 SELLING", "red"
        return "⚪ NEUTRAL", "gray"

    if bid > 0 and ask > 0:
        mid = (bid + ask) / 2
        if ltp_val >= mid * 1.01:
            return "🟢 BUYING", "green"
        elif ltp_val <= mid * 0.99:
            return "🔴 SELLING", "red"
        return "⚪ NEUTRAL", "gray"

    # Fallback: CE buying = bullish, PE buying = bearish
    if opt_type == "CE": return "🟢 BULLISH", "green"
    return "🔴 BEARISH", "red"

# ─────────────────────────────────────────────────────────────────────────────
# CORE SCANNER — returns list of spike rows for one symbol
# ─────────────────────────────────────────────────────────────────────────────
def scan_symbol(symbol, meta, is_index=True):
    exp     = meta["exp"]
    fo_seg  = meta["fo_seg"]
    step    = meta["step"]
    lot     = meta["lot"]
    results = []

    fo = scrip_list(fo_seg, symbol)
    if not fo: return results

    # ── Resolve underlying price ─────────────────────────────────────────────
    und = 0.0
    if is_index or meta.get("is_fut", True):
        for item in fo:
            s = _sym(item)
            if "FUT" in s and _exp_match(s, exp):
                t = _tok(item)
                if t:
                    v = _ltp(live_quote(t, fo_seg))
                    if v > 0: und = v; break
        if und <= 0:
            for item in fo:
                if "FUT" in _sym(item):
                    t = _tok(item)
                    if t:
                        v = _ltp(live_quote(t, fo_seg))
                        if v > 0: und = v; break
    else:
        cm_seg = meta.get("cm_seg","nse_cm")
        cm = scrip_list(cm_seg, symbol)
        for item in cm:
            s = _sym(item)
            if s in (f"{symbol}-EQ", symbol, f"{symbol}EQ"):
                t = _tok(item)
                if t:
                    v = _ltp(live_quote(t, cm_seg))
                    if v > 0: und = v; break

    # Use base price if live unavailable (off-hours)
    if und <= 0: und = meta["base"]

    atm     = int(round(und / step) * step)
    strikes = [atm + i * step for i in range(-STRIKE_RANGE, STRIKE_RANGE + 1)]

    # ── Also fetch futures row ──────────────────────────────────────────────
    for item in fo:
        s = _sym(item)
        if "FUT" in s and _exp_match(s, exp):
            t = _tok(item)
            if not t: continue
            q   = live_quote(t, fo_seg)
            vol_now = _vol(q)
            ltp_val = _ltp(q)
            if ltp_val <= 0 and vol_now <= 0: continue
            key = (symbol, "FUT", "FUT")
            update_vol_history(key, vol_now)
            avg = avg_vol(key)
            spk = vol_spike_pct(vol_now, avg)
            results.append({
                "symbol": symbol, "type": "FUT", "strike": "—",
                "opt": "FUT", "ltp": ltp_val, "volume": vol_now,
                "oi": _oi(q), "avg_vol": int(avg),
                "spike_pct": spk, "trend": "📈 LONG" if ltp_val > und*0.999 else "📉 SHORT",
                "trend_color": "green",
                "is_spike": spk >= (SPIKE_THRESHOLD - 1) * 100,
                "seg": fo_seg, "underlying": und,
            })
            break

    # ── Scan options ────────────────────────────────────────────────────────
    for item in fo:
        try:
            s      = _sym(item)
            if not _exp_match(s, exp): continue
            opt    = _opt(item)
            if not opt: continue
            sk     = _strike(item)
            if sk not in strikes: continue
            t      = _tok(item)
            if not t: continue

            q       = live_quote(t, fo_seg)
            vol_now = _vol(q)
            ltp_val = _ltp(q)
            oi_val  = _oi(q)

            key = (symbol, sk, opt)
            update_vol_history(key, vol_now)
            avg  = avg_vol(key)
            spk  = vol_spike_pct(vol_now, avg)
            trend_label, trend_color = detect_trend(q, opt)

            results.append({
                "symbol": symbol, "type": "OPT", "strike": sk,
                "opt": opt, "ltp": ltp_val, "volume": vol_now,
                "oi": oi_val, "avg_vol": int(avg),
                "spike_pct": spk, "trend": trend_label,
                "trend_color": trend_color,
                "is_spike": spk >= SPIKE_THRESHOLD * 100,
                "seg": fo_seg, "underlying": und,
                "formatted_symbol": s,
            })
        except: continue

    return results

# ─────────────────────────────────────────────────────────────────────────────
# RENDER — spike table for one category
# ─────────────────────────────────────────────────────────────────────────────
def render_scanner(label, symbols_meta, is_index=True):
    st.markdown(f"#### {label}")

    ist       = pytz.timezone("Asia/Kolkata")
    now_ist   = datetime.now(ist)
    wd        = now_ist.weekday()  # 0=Mon, 6=Sun

    # NSE: Mon–Fri 09:15–15:30
    nse_open  = now_ist.replace(hour=9,  minute=15, second=0, microsecond=0)
    nse_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    nse_live  = nse_open <= now_ist <= nse_close and wd < 5

    # MCX: Mon–Fri 09:00–23:30, Sat 09:00–14:00
    mcx_open  = now_ist.replace(hour=9,  minute=0,  second=0, microsecond=0)
    mcx_close_wkday = now_ist.replace(hour=23, minute=30, second=0, microsecond=0)
    mcx_close_sat   = now_ist.replace(hour=14, minute=0,  second=0, microsecond=0)
    if wd < 5:
        mcx_live = mcx_open <= now_ist <= mcx_close_wkday
    elif wd == 5:  # Saturday
        mcx_live = mcx_open <= now_ist <= mcx_close_sat
    else:
        mcx_live = False

    # Determine if THIS tab's segment is live
    is_mcx  = any("mcx" in m.get("fo_seg","") for m in symbols_meta.values())
    is_live = mcx_live if is_mcx else nse_live

    if not is_live:
        seg_label = "MCX" if is_mcx else "NSE"
        open_time = "9:00 AM" if is_mcx else "9:15 AM"
        close_time= "11:30 PM (Mon–Fri), 2:00 PM (Sat)" if is_mcx else "3:30 PM"
        st.info(f"🌙 {seg_label} market closed — showing simulated preview. Hours: {open_time}–{close_time} IST")

    all_rows = []
    cols = st.columns(min(len(symbols_meta), 3))

    for idx, (symbol, meta) in enumerate(symbols_meta.items()):
        with cols[idx % len(cols)]:
            with st.spinner(f"Scanning {symbol}..."):
                if api and auth_status == "OK" and is_live:
                    rows = scan_symbol(symbol, meta, is_index or is_mcx)
                else:
                    rows = _fake_scan(symbol, meta)

            if not rows:
                st.warning(f"⏳ {symbol}: No data")
                continue

            und_val = rows[0]["underlying"]
            st.metric(f"**{symbol}**", f"₹{und_val:,.1f}")

            # Show all rows sorted by spike_pct desc
            rows_sorted = sorted(rows, key=lambda x: x["spike_pct"], reverse=True)
            for r in rows_sorted[:8]:
                spike_flag = "🚨 " if r["is_spike"] else ""
                opt_label  = r["opt"]
                strike_str = str(r["strike"]) if r["strike"] != "—" else "FUT"
                spk_str    = f"+{r['spike_pct']:.0f}%" if r["spike_pct"] > 0 else "—"
                vol_str    = f"{r['volume']:,}" if r["volume"] else "—"
                avg_str    = f"{r['avg_vol']:,}" if r["avg_vol"] else "new"

                if r["is_spike"]:
                    st.error(
                        f"{spike_flag}**{symbol} {strike_str} {opt_label}** | "
                        f"LTP: ₹{r['ltp']} | Vol: {vol_str} (avg {avg_str}) | "
                        f"Spike: **{spk_str}** | {r['trend']}"
                    )
                elif r["spike_pct"] > 50:
                    st.warning(
                        f"⚠️ **{symbol} {strike_str} {opt_label}** | "
                        f"LTP: ₹{r['ltp']} | Vol: {vol_str} | +{r['spike_pct']:.0f}% | {r['trend']}"
                    )
                else:
                    st.info(
                        f"**{symbol} {strike_str} {opt_label}** | "
                        f"LTP: ₹{r['ltp']} | Vol: {vol_str} | {r['trend']}"
                    )

            all_rows.extend(rows_sorted)

    # Summary spike table
    spikes = [r for r in all_rows if r["is_spike"]]
    if spikes:
        st.markdown("---")
        st.markdown("##### 🚨 Unusual Volume Alerts")
        df = pd.DataFrame([{
            "Symbol":   r["symbol"],
            "Strike":   r["strike"],
            "Type":     r["opt"],
            "LTP":      f"₹{r['ltp']}",
            "Volume":   f"{r['volume']:,}",
            "Avg Vol":  f"{r['avg_vol']:,}" if r["avg_vol"] else "—",
            "Spike %":  f"+{r['spike_pct']:.0f}%",
            "Trend":    r["trend"],
            "Underlying": f"₹{r['underlying']:,.1f}",
        } for r in spikes])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# FAKE DATA for off-hours preview
# ─────────────────────────────────────────────────────────────────────────────
def _fake_scan(symbol, meta):
    base  = meta["base"]
    step  = meta["step"]
    atm   = int(round(base / step) * step)
    lot   = meta["lot"]
    rows  = []

    # Fake underlying from base
    und = base * random.uniform(0.998, 1.002)

    # Futures row
    rows.append({
        "symbol": symbol, "type": "FUT", "strike": "—", "opt": "FUT",
        "ltp": round(und * 1.001, 1), "volume": random.randint(5000, 50000),
        "oi": random.randint(10000, 200000), "avg_vol": random.randint(4000, 40000),
        "spike_pct": random.uniform(-20, 60), "trend": "📈 LONG",
        "trend_color": "green", "is_spike": False, "underlying": round(und, 1),
        "formatted_symbol": f"{symbol}FUT",
    })

    for i in range(-STRIKE_RANGE, STRIKE_RANGE + 1):
        sk = atm + i * step
        for opt in ["CE", "PE"]:
            # Randomly inject a spike for preview
            base_vol = random.randint(10000, 80000)
            spike    = random.random() < 0.15  # 15% chance of spike
            vol_now  = base_vol * random.uniform(2.5, 5.0) if spike else base_vol
            avg      = base_vol * random.uniform(0.8, 1.2)
            spk_pct  = ((vol_now - avg) / avg * 100) if avg > 0 else 0

            dist   = abs(i)
            ltp_ce = max(0.5, round((STRIKE_RANGE - dist + 1) * step * 0.015 * random.uniform(0.7,1.3), 1))
            ltp_pe = max(0.5, round((dist + 1) * step * 0.012 * random.uniform(0.7,1.3), 1))
            ltp_v  = ltp_ce if opt == "CE" else ltp_pe

            trend_label = random.choice(["🟢 BUYING","🔴 SELLING","⚪ NEUTRAL"])
            rows.append({
                "symbol": symbol, "type": "OPT", "strike": sk, "opt": opt,
                "ltp": ltp_v, "volume": int(vol_now), "oi": random.randint(5000,500000),
                "avg_vol": int(avg), "spike_pct": spk_pct,
                "trend": trend_label, "trend_color": "green" if "BUY" in trend_label else "red",
                "is_spike": spk_pct >= SPIKE_THRESHOLD * 100,
                "underlying": round(und, 1),
                "formatted_symbol": f"{symbol}{meta['exp']}{sk}{opt}",
            })
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# HEADER STATUS
# ─────────────────────────────────────────────────────────────────────────────
ist_now = datetime.now(pytz.timezone("Asia/Kolkata"))
_wd = ist_now.weekday()
_nse_live = (ist_now.replace(hour=9,minute=15,second=0) <= ist_now <= ist_now.replace(hour=15,minute=30,second=0)) and _wd < 5
_mcx_live = (ist_now.replace(hour=9,minute=0,second=0) <= ist_now <= ist_now.replace(hour=23,minute=30,second=0)) and _wd < 5 or             (ist_now.replace(hour=9,minute=0,second=0) <= ist_now <= ist_now.replace(hour=14,minute=0,second=0)) and _wd == 5
is_mkt = _nse_live or _mcx_live

c1, c2, c3, c4 = st.columns(4)
with c1:
    if auth_status == "OK": st.success("🟢 Broker Connected")
    else: st.error(f"🔴 Auth Failed")
with c2:
    st.metric("Market", "🟢 OPEN" if is_mkt else "🔴 CLOSED")
with c3:
    st.metric("IST Time", ist_now.strftime("%H:%M:%S"))
with c4:
    st.metric("Spike Threshold", f"{SPIKE_THRESHOLD}× Avg Vol")

with st.expander("🔧 Auth Diagnostic", expanded=(auth_status != "OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v = os.environ.get(k)
        st.success(f"✅ {k} ({len(v)} chars)") if v else st.error(f"❌ {k} MISSING")
    for l in auth_logs: st.code(l)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📈 Index Options & Futures",
    "📊 Stock Options & Futures",
    "🛢️ MCX Commodities",
])

with tab1:
    render_scanner("📈 Index Options & Futures — Unusual Volume Scanner", INDICES, is_index=True)

with tab2:
    render_scanner("📊 Stock Options & Futures — Unusual Volume Scanner", STOCKS, is_index=False)

with tab3:
    render_scanner("🛢️ MCX Commodity Options & Futures — Unusual Volume Scanner", COMMODITIES, is_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# AUTO REFRESH  (30s during market hours, 5 min otherwise)
# ─────────────────────────────────────────────────────────────────────────────
refresh_ms = 30000 if is_mkt else 300000
st.components.v1.html(
    f"<script>setTimeout(function(){{window.location.reload();}},{refresh_ms});</script>",
    height=0, width=0
)
