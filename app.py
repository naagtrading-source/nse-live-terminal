import streamlit as st
import pandas as pd
import os, pytz, pyotp, re, io, sys, contextlib, threading, gc
from datetime import datetime
from collections import defaultdict

gc.enable()

st.set_page_config(page_title="SNY Block Detector", layout="wide", page_icon="⚡")
st.markdown("""
<style>
body,.stApp{background:#0d1117;color:#e6edf3}
div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
.stTabs [data-baseweb="tab-list"]{gap:6px;background:#161b22;padding:6px;border-radius:8px}
.stTabs [data-baseweb="tab"]{background:#21262d!important;color:#8b949e!important;
  border-radius:6px;padding:8px 20px;font-weight:600;border:1px solid #30363d!important}
.stTabs [aria-selected="true"]{background:#1f6feb!important;color:#fff!important;
  font-weight:700!important;border:1px solid #388bfd!important}
div[data-testid="metric-container"]{background:#161b22;border:1px solid #30363d;
  border-radius:8px;padding:10px 14px}
</style>""", unsafe_allow_html=True)

# ── Config ─────────────────────────────────────────────────────────────────────
# Reduced to top liquid symbols to fit 512MB memory
INDICES = {
    "NIFTY":     {"fo_seg":"nse_fo","step":50,  "lot":75},
    "BANKNIFTY": {"fo_seg":"nse_fo","step":100, "lot":30},
}
STOCKS = {
    "RELIANCE":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":50,  "lot":250},
    "HDFCBANK":  {"fo_seg":"nse_fo","cm_seg":"nse_cm","step":20,  "lot":550},
}
COMMODITIES = {
    "GOLDM":     {"fo_seg":"mcx_fo","step":100,  "lot":10},
    "CRUDEOIL":  {"fo_seg":"mcx_fo","step":100,  "lot":100},
}

# ── Block detection thresholds ────────────────────────────────────────────────
VOL_SPIKE_MULT   = 2.0       # volume jump > 2× recent average = block
MIN_VOL_JUMP     = 5000      # absolute floor: ignore tiny jumps
LARGE_VALUE_CR   = 0.5       # ₹ value of the volume jump > 50 lakh = notable
OI_CHANGE_PCT    = 5.0       # OI change > 5% = position buildup
STRIKE_RANGE     = 2         # strikes around ATM to monitor
FEED_MAX         = 40        # max rows in live feed

# ── Thread isolation for SDK ──────────────────────────────────────────────────
def _run_isolated(fn):
    result=[None]; error=[None]
    def _w():
        buf=io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                result[0]=fn()
        except Exception as e: error[0]=e
    t=threading.Thread(target=_w, daemon=True); t.start(); t.join(timeout=30)
    if error[0]: raise error[0]
    return result[0]

@st.cache_resource(ttl=1380, show_spinner=False)
def get_api():
    logs=[]
    try:
        from neo_api_client import NeoAPI
        ck=os.environ.get("KOTAK_CONSUMER_KEY","").strip()
        secret=os.environ.get("KOTAK_TOTP_SECRET","").replace(" ","")
        ucc=os.environ.get("KOTAK_UCC","").strip()
        mpin=os.environ.get("KOTAK_MPIN","").strip()
        mob_raw=os.environ.get("KOTAK_MOBILE","").strip()
        mob=mob_raw.lstrip("+").replace(" ","").replace("-","")
        if mob.startswith("91") and len(mob)==12: mob=mob[2:]
        elif mob.startswith("0") and len(mob)==11: mob=mob[1:]
        logs.append(f"mob='{mob}' ({len(mob)}d)")
        padded=secret+"="*(-len(secret)%8)
        try: totp=pyotp.TOTP(padded).now()
        except: totp=pyotp.TOTP(secret).now()
        api=_run_isolated(lambda: NeoAPI(environment="prod",consumer_key=ck))
        r1=None
        for mfmt in [f"+91{mob}", mob, f"91{mob}"]:
            r1=_run_isolated(lambda m=mfmt: api.totp_login(mobile_number=m,ucc=ucc,totp=totp))
            logs.append(f"login '{mfmt}' → {str(r1)[:100]}")
            if isinstance(r1,dict) and not r1.get("error"):
                logs.append(f"✅ login OK: {mfmt}"); break
        r2=_run_isolated(lambda: api.totp_validate(mpin=mpin))
        logs.append(f"validate → {str(r2)[:100]}")
        return api,"OK",logs
    except Exception as e:
        import traceback; logs.append(traceback.format_exc()[-350:])
        return None,str(e)[:120],logs

api,auth_status,auth_logs=get_api()

def safe_call(fn):
    try: return _run_isolated(fn)
    except: return None

# ── Extractors ─────────────────────────────────────────────────────────────────
def _unwrap(raw):
    if raw is None: return {}
    if isinstance(raw,list): raw=raw[0] if raw else {}
    if isinstance(raw,dict):
        for dk in ("data","Data","result","Result"):
            if dk in raw:
                inn=raw[dk]
                if isinstance(inn,list) and inn: return inn[0] if isinstance(inn[0],dict) else {}
                if isinstance(inn,dict): return inn
        return raw
    return {}
def _f(v):
    try: return float(str(v).replace(",","").strip())
    except: return 0.0
def _ltp(q):
    if not isinstance(q,dict): return 0.0
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close","last_price","Ltp","price"):
        v=q.get(k)
        if v not in (None,"",0,"0",0.0):
            f=_f(v)
            if f>0: return f
    return 0.0
def _vol(q):
    if not isinstance(q,dict): return 0
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","ltq","Volume"):
        v=q.get(k)
        if v not in (None,""):
            try: return max(0,int(_f(v)))
            except: pass
    return 0
def _oi(q):
    if not isinstance(q,dict): return 0
    for k in ("open_interest","oi","openInterest","OI"):
        v=q.get(k)
        if v not in (None,""):
            try: return max(0,int(_f(v)))
            except: pass
    return 0
def _ltq(q):
    """Last traded quantity — the size of the most recent single trade."""
    if not isinstance(q,dict): return 0
    for k in ("last_traded_quantity","ltq","lastTradedQty","ltSize","last_trade_qty"):
        v=q.get(k)
        if v not in (None,""):
            try: return max(0,int(_f(v)))
            except: pass
    return 0
def _tok(item):
    for k in ("pSymbol","token","instrument_token","Token","scripToken"):
        v=item.get(k)
        if v is not None: return str(v)
    return None
def _sym(item):
    for k in ("pTrdSymbol","trdSym","tradingSymbol","symbol"):
        v=item.get(k)
        if v: return str(v).upper().strip()
    return ""
def _matches(trd,target):
    trd=trd.upper(); target=target.upper()
    if not trd.startswith(target): return False
    rest=trd[len(target):]
    return (not rest) or rest[0].isdigit() or rest[0] in ("-"," ")
def _opt_type(item):
    raw=str(item.get("pOptionType",item.get("optTp",""))).strip().upper()
    if raw in ("CE","CALL","C"): return "CE"
    if raw in ("PE","PUT","P"): return "PE"
    return None
def _strike_val(item):
    for k in ("pStrikePrice","strkPrc","strikePrice","strike_price"):
        v=item.get(k)
        if v is not None:
            f=_f(v)
            if f>0: return f
    return None
def _parse_exp(item):
    today=datetime.now(pytz.timezone("Asia/Kolkata")).date()
    for k in ("pExpDate","expiry","expiryDate","ExpiryDate","expDate","pExpiryDate"):
        v=item.get(k)
        if not v: continue
        s=str(v).strip().upper()
        for fmt in ("%d%b%Y","%d-%b-%Y","%Y-%m-%d","%d/%m/%Y","%d%b%y","%d-%b-%y"):
            try:
                d=datetime.strptime(s,fmt).date()
                if d>=today: return d
            except: pass
    s=_sym(item)
    m=re.search(r'(\d{1,2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2,4})',s)
    if m:
        day,mon,yr=m.groups(); yi=int(yr) if len(yr)==4 else 2000+int(yr)
        try:
            d=datetime.strptime(f"{int(day):02d}{mon}{yi}","%d%b%Y").date()
            if d>=today: return d
        except: pass
    return None

def live_quote(token,seg):
    if not api or not token: return {}
    raw=safe_call(lambda: api.get_live_quotes([{"instrument_token":str(token),"exchange_segment":seg}]))
    return _unwrap(raw) if raw else {}

@st.cache_data(ttl=7200,show_spinner=False,max_entries=10)
def scrip_list(seg,symbol):
    """Cache scrip records but STRIP to only fields we need — saves memory.
    Each raw record has 30+ fields; we keep only 6."""
    if not api: return []
    import gc
    r=safe_call(lambda: api.search_scrip(exchange_segment=seg,symbol=symbol))
    raw = r.get("data",[]) or r.get("result",[]) if isinstance(r,dict) else (r if isinstance(r,list) else [])
    # Keep only essential fields to minimize memory
    slim=[]
    for item in raw:
        slim.append({
            "pSymbol": item.get("pSymbol", item.get("token")),
            "pTrdSymbol": item.get("pTrdSymbol", item.get("trdSym","")),
            "pOptionType": item.get("pOptionType", item.get("optTp","")),
            "pStrikePrice": item.get("pStrikePrice", item.get("strkPrc",0)),
            "pExpDate": item.get("pExpDate", item.get("expiry","")),
        })
    del raw, r
    gc.collect()
    return slim

# ── State: track previous volume & OI per instrument ──────────────────────────
def _state():
    if "prev" not in st.session_state: st.session_state["prev"]=defaultdict(dict)
    if "volhist" not in st.session_state: st.session_state["volhist"]=defaultdict(list)
    if "feed" not in st.session_state: st.session_state["feed"]=[]
    return st.session_state

def _vh_avg(key):
    h=st.session_state["volhist"].get(key,[])
    return sum(h[:-1])/len(h[:-1]) if len(h)>=3 else 0

def _trend(q,opt):
    bq=int(_f(q.get("total_buy_quantity",q.get("buyQty",0))or 0))
    sq=int(_f(q.get("total_sell_quantity",q.get("sellQty",0))or 0))
    if bq>0 and sq>0:
        if bq>sq*1.2: return "🟢 BUY"
        if sq>bq*1.2: return "🔴 SELL"
        return "⚪ NEUT"
    return "🟢 BULL" if opt=="CE" else "🔴 BEAR"

# ── BLOCK DETECTION CORE ──────────────────────────────────────────────────────
def detect_blocks(category_name, symbols_meta):
    """
    For each symbol+strike+expiry, fetch quote, compare to previous snapshot,
    and flag a block if volume jumps significantly. Returns list of block events.
    """
    s=_state()
    ist=pytz.timezone("Asia/Kolkata")
    ts=datetime.now(ist).strftime("%H:%M:%S")
    blocks=[]

    for symbol,meta in symbols_meta.items():
        fo_seg=meta["fo_seg"]; step=meta["step"]; lot=meta["lot"]
        today=datetime.now(ist).date()
        fo=scrip_list(fo_seg,symbol)
        if not fo: continue

        # Underlying from nearest FUT
        futs=sorted([(d,i) for i in fo for d in [_parse_exp(i)]
                     if d and "FUT" in _sym(i) and _matches(_sym(i),symbol)],
                    key=lambda x:x[0])
        und=0.0
        for d,item in futs:
            tok=_tok(item)
            if tok:
                v=_ltp(live_quote(tok,fo_seg))
                if v>0: und=v; break
        if und<=0 and "cm_seg" in meta:
            cm=scrip_list(meta["cm_seg"],symbol)
            for item in cm:
                if _sym(item) in (f"{symbol}-EQ",symbol,f"{symbol}EQ"):
                    tok=_tok(item)
                    if tok:
                        und=_ltp(live_quote(tok,meta["cm_seg"]))
                        if und>0: break
        if und<=0: continue

        atm=round(und/step)*step
        watch=[atm+i*step for i in range(-STRIKE_RANGE,STRIKE_RANGE+1)]

        # Scan FUT + options near ATM
        targets=[]
        for item in fo:
            s_item=_sym(item)
            if not _matches(s_item,symbol): continue
            d=_parse_exp(item)
            if not d or d<today: continue
            if "FUT" in s_item:
                targets.append((item,"FUT",None,d))
            else:
                opt=_opt_type(item)
                sk=_strike_val(item)
                if opt and sk and sk in watch:
                    targets.append((item,opt,int(sk),d))

        for item,kind,strike,exp_d in targets:
            tok=_tok(item)
            if not tok: continue
            q=live_quote(tok,fo_seg)
            vol=_vol(q); ltp=_ltp(q); oi=_oi(q); ltq=_ltq(q)
            if vol<=0 and ltp<=0: continue

            ikey=f"{symbol}|{kind}|{strike}|{exp_d}"

            # Update volume history
            s["volhist"][ikey].append(vol)
            if len(s["volhist"][ikey])>10: s["volhist"][ikey].pop(0)

            prev=s["prev"].get(ikey,{})
            prev_vol=prev.get("vol",vol)
            prev_oi =prev.get("oi",oi)

            vol_jump = vol - prev_vol            # new volume since last tick
            avg      = _vh_avg(ikey)
            oi_chg   = oi - prev_oi
            oi_pct   = (oi_chg/prev_oi*100) if prev_oi>0 else 0

            # ── BLOCK CONDITIONS ──────────────────────────────────────────────
            is_block=False; reasons=[]

            # 1. Volume jump vs average (PRIMARY)
            if avg>0 and vol_jump>=MIN_VOL_JUMP and vol_jump >= avg*VOL_SPIKE_MULT:
                is_block=True
                reasons.append(f"Vol+{vol_jump:,} ({vol_jump/avg:.1f}×avg)")

            # 2. Large ₹ value of the jump
            value_cr = (vol_jump * ltp) / 1e7   # in crores
            if value_cr >= LARGE_VALUE_CR and vol_jump>=MIN_VOL_JUMP:
                is_block=True
                reasons.append(f"₹{value_cr:.2f}Cr")

            # 3. Large single trade (LTQ)
            if ltq >= lot*50 and ltq>0:
                is_block=True
                reasons.append(f"BigTrade {ltq:,}")

            # 4. OI buildup
            if abs(oi_pct) >= OI_CHANGE_PCT and prev_oi>0:
                is_block=True
                direction="↑ADD" if oi_chg>0 else "↓EXIT"
                reasons.append(f"OI {direction} {abs(oi_pct):.0f}%")

            # Save current as previous for next tick
            s["prev"][ikey]={"vol":vol,"oi":oi,"ltp":ltp}

            if is_block:
                strike_lbl=str(strike) if strike else "FUT"
                blocks.append({
                    "time":ts,"category":category_name,"symbol":symbol,
                    "strike":strike_lbl,"type":kind,"expiry":str(exp_d),
                    "ltp":ltp,"vol_jump":vol_jump,"total_vol":vol,
                    "avg_vol":int(avg),"value_cr":round(value_cr,2),
                    "ltq":ltq,"oi":oi,"oi_chg_pct":round(oi_pct,1),
                    "trend":_trend(q,kind if kind in ("CE","PE") else "CE"),
                    "underlying":und,"reasons":" | ".join(reasons),
                })
            del q   # free quote dict immediately

        # Free per-symbol data and collect garbage
        del fo, targets, futs
        gc.collect()

    return blocks

# ── Push blocks into the live feed ────────────────────────────────────────────
def push_feed(blocks):
    s=_state()
    for b in blocks:
        s["feed"].insert(0, b)   # newest on top
    # Dedupe consecutive identical and trim
    s["feed"]=s["feed"][:FEED_MAX]

# ── Market hours ───────────────────────────────────────────────────────────────
def market_state():
    now=datetime.now(pytz.timezone("Asia/Kolkata")); wd=now.weekday()
    nse=(now.replace(hour=9,minute=15,second=0,microsecond=0)<=now<=
         now.replace(hour=15,minute=30,second=0,microsecond=0)) and wd<5
    mcx=((wd<5) and now.replace(hour=9,minute=0,second=0,microsecond=0)<=now<=
         now.replace(hour=23,minute=30,second=0,microsecond=0)) or \
        ((wd==5) and now.replace(hour=9,minute=0,second=0,microsecond=0)<=now<=
         now.replace(hour=14,minute=0,second=0,microsecond=0))
    return nse,mcx

nse_l,mcx_l=market_state()

# ── HEADER ─────────────────────────────────────────────────────────────────────
st.markdown("## ⚡ SNY Block Order Detector")
st.caption("Real-time large/unusual order block scanner — Index · Stocks · Commodities")

ist_now=datetime.now(pytz.timezone("Asia/Kolkata"))
c1,c2,c3,c4=st.columns(4)
with c1:
    if auth_status=="OK": st.success("🟢 Broker OK")
    else: st.error("🔴 Auth Failed")
with c2: st.metric("NSE","🟢 OPEN" if nse_l else "🔴 CLOSED")
with c3: st.metric("MCX","🟢 OPEN" if mcx_l else "🔴 CLOSED")
with c4: st.metric("IST",ist_now.strftime("%H:%M:%S"))

with st.expander("🔧 Diagnostic",expanded=(auth_status!="OK")):
    for k in ["KOTAK_CONSUMER_KEY","KOTAK_MOBILE","KOTAK_UCC","KOTAK_MPIN","KOTAK_TOTP_SECRET"]:
        v=os.environ.get(k)
        if v: st.success(f"✅ {k} ({len(v)} chars)")
        else: st.error(f"❌ {k} MISSING")
    for l in auth_logs: st.code(l)

st.markdown("---")

# ── RUN DETECTION — rotate ONE category per refresh to save memory ────────────
s=_state()
if "scan_rotation" not in st.session_state:
    st.session_state["scan_rotation"]=0

all_blocks=[]
if auth_status=="OK":
    # Build list of active categories
    active=[]
    if nse_l: active+=[("Index",INDICES),("Stock",STOCKS)]
    if mcx_l: active+=[("Commodity",COMMODITIES)]

    if active:
        # Process only ONE category this cycle, rotate next time
        rot=st.session_state["scan_rotation"] % len(active)
        cat_name, cat_meta = active[rot]
        all_blocks = detect_blocks(cat_name, cat_meta)
        st.session_state["scan_rotation"] = (rot+1) % len(active)
        st.caption(f"🔄 Scanning: **{cat_name}** ({rot+1}/{len(active)}) — rotates each refresh")
        if all_blocks:
            push_feed(all_blocks)
        gc.collect()

# ── LIVE FEED (tape) ──────────────────────────────────────────────────────────
st.markdown("### 📡 Live Block Feed")
if not (nse_l or mcx_l):
    st.info("🌙 Markets closed. Block feed runs during market hours. NSE 9:15–15:30 | MCX 9:00–23:30 IST")
elif not s["feed"]:
    st.caption("⏳ Monitoring... no blocks detected yet. Large orders will appear here as they trigger.")
else:
    for b in s["feed"][:20]:
        icon="🔵" if b["type"]=="CE" else "🔴" if b["type"]=="PE" else "🟡"
        sk=b["strike"]
        line=(f"`{b['time']}` {icon} **{b['symbol']} {sk} {b['type']}** "
              f"[{b['expiry']}] | LTP ₹{b['ltp']} | **{b['reasons']}** | {b['trend']}")
        val=b["value_cr"]
        if val>=2.0:   st.error(line)
        elif val>=0.5: st.warning(line)
        else:          st.info(line)

st.markdown("---")

# ── SUMMARY TABLES per category ───────────────────────────────────────────────
t1,t2,t3=st.tabs(["📈 Index Blocks","📊 Stock Blocks","🛢️ Commodity Blocks"])

def render_table(cat):
    rows=[b for b in s["feed"] if b["category"]==cat]
    if not rows:
        st.caption(f"No {cat.lower()} blocks yet.")
        return
    df=pd.DataFrame([{
        "Time":b["time"],"Symbol":b["symbol"],"Strike":b["strike"],
        "Type":b["type"],"Expiry":b["expiry"],"LTP":f"₹{b['ltp']}",
        "Vol Jump":f"{b['vol_jump']:,}","Total Vol":f"{b['total_vol']:,}",
        "Avg Vol":f"{b['avg_vol']:,}","Value":f"₹{b['value_cr']}Cr",
        "OI Δ%":f"{b['oi_chg_pct']:+.0f}%","Trend":b["trend"],
        "Signals":b["reasons"],
    } for b in rows])
    st.dataframe(df,use_container_width=True,hide_index=True)

with t1: render_table("Index")
with t2: render_table("Stock")
with t3: render_table("Commodity")

# ── Auto-refresh ───────────────────────────────────────────────────────────────
ms=15000 if ((nse_l or mcx_l) and auth_status=="OK") else 300000
st.components.v1.html(
    f"<script>setTimeout(function(){{window.location.reload();}},{ms});</script>",
    height=0,width=0)
