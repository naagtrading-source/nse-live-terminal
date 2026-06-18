"""
SNY Block Detector — BACKGROUND WORKER
=======================================
Runs the Kotak Neo SDK, logs in, continuously scans for institutional
block orders, and pushes detected events to Upstash Redis via REST.

This service does the heavy lifting (SDK + instrument master ~400MB).
It runs as a Render Background Worker — NO Streamlit, NO web server.

Required environment variables:
  KOTAK_CONSUMER_KEY, KOTAK_MOBILE, KOTAK_UCC, KOTAK_MPIN, KOTAK_TOTP_SECRET
  UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
"""
import os, time, json, re, io, sys, contextlib, threading, gc
import pyotp, pytz, requests
from datetime import datetime
from collections import defaultdict

gc.enable()
IST = pytz.timezone("Asia/Kolkata")

# ── Symbol config ─────────────────────────────────────────────────────────────
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

VOL_SPIKE_MULT = 2.0
MIN_VOL_JUMP   = 5000
LARGE_VALUE_CR = 0.5
OI_CHANGE_PCT  = 5.0
STRIKE_RANGE   = 3
SCAN_INTERVAL  = 20   # seconds between full scan cycles

# ── Upstash Redis REST helpers ────────────────────────────────────────────────
REDIS_URL   = os.environ.get("UPSTASH_REDIS_REST_URL","").rstrip("/")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN","")

def redis_cmd(*args):
    """Execute a Redis command via Upstash REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    try:
        r = requests.post(
            REDIS_URL,
            headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
            json=list(args),
            timeout=10,
        )
        return r.json().get("result")
    except Exception as e:
        print(f"[redis] error: {e}", flush=True)
        return None

def push_block(block):
    """Push a block event to the Redis list 'blocks' (newest first), cap at 100."""
    redis_cmd("LPUSH", "blocks", json.dumps(block))
    redis_cmd("LTRIM", "blocks", "0", "99")

def set_status(status):
    redis_cmd("SET", "worker_status", json.dumps(status))

# ── Thread-isolated SDK calls (avoids any stdout pollution) ───────────────────
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

# ── Auth ──────────────────────────────────────────────────────────────────────
def login():
    from neo_api_client import NeoAPI
    ck=os.environ.get("KOTAK_CONSUMER_KEY","").strip()
    secret=os.environ.get("KOTAK_TOTP_SECRET","").replace(" ","")
    ucc=os.environ.get("KOTAK_UCC","").strip()
    mpin=os.environ.get("KOTAK_MPIN","").strip()
    mob=os.environ.get("KOTAK_MOBILE","").strip().lstrip("+").replace(" ","").replace("-","")
    if mob.startswith("91") and len(mob)==12: mob=mob[2:]
    elif mob.startswith("0") and len(mob)==11: mob=mob[1:]
    padded=secret+"="*(-len(secret)%8)
    try: totp=pyotp.TOTP(padded).now()
    except: totp=pyotp.TOTP(secret).now()

    api=_run_isolated(lambda: NeoAPI(environment="prod", consumer_key=ck))
    for mfmt in [f"+91{mob}", mob, f"91{mob}"]:
        r1=_run_isolated(lambda m=mfmt: api.totp_login(mobile_number=m,ucc=ucc,totp=totp))
        print(f"[auth] login '{mfmt}' → {str(r1)[:100]}", flush=True)
        if isinstance(r1,dict) and not r1.get("error"):
            print(f"[auth] ✅ login OK: {mfmt}", flush=True)
            break
    r2=_run_isolated(lambda: api.totp_validate(mpin=mpin))
    print(f"[auth] validate → {str(r2)[:100]}", flush=True)
    return api

# ── Extractors ─────────────────────────────────────────────────────────────────
def _f(v):
    try: return float(str(v).replace(",","").strip())
    except: return 0.0
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
def _ltp(q):
    if not isinstance(q,dict): return 0.0
    for k in ("ltp","last_traded_price","lastPrice","LTP","c","close","last_price","price"):
        v=q.get(k)
        if v not in (None,"",0,"0",0.0):
            f=_f(v)
            if f>0: return f
    return 0.0
def _vol(q):
    if not isinstance(q,dict): return 0
    for k in ("volume","vol","tradedQuantity","totalTradedVolume","Volume"):
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
    if not isinstance(q,dict): return 0
    for k in ("last_traded_quantity","ltq","lastTradedQty","ltSize"):
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
    today=datetime.now(IST).date()
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

# ── SDK wrappers ────────────────────────────────────────────────────────────────
_scrip_cache={}
def scrip_list(api, seg, symbol):
    key=f"{seg}:{symbol}"
    if key in _scrip_cache: return _scrip_cache[key]
    try:
        r=_run_isolated(lambda: api.search_scrip(exchange_segment=seg,symbol=symbol))
        raw=r.get("data",[]) or r.get("result",[]) if isinstance(r,dict) else (r if isinstance(r,list) else [])
    except: raw=[]
    slim=[{
        "pSymbol":i.get("pSymbol",i.get("token")),
        "pTrdSymbol":i.get("pTrdSymbol",i.get("trdSym","")),
        "pOptionType":i.get("pOptionType",i.get("optTp","")),
        "pStrikePrice":i.get("pStrikePrice",i.get("strkPrc",0)),
        "pExpDate":i.get("pExpDate",i.get("expiry","")),
    } for i in raw]
    _scrip_cache[key]=slim
    del raw; gc.collect()
    return slim

def live_quote(api, token, seg):
    if not token: return {}
    try:
        raw=_run_isolated(lambda: api.get_live_quotes(
            [{"instrument_token":str(token),"exchange_segment":seg}]))
        return _unwrap(raw)
    except: return {}

def _trend(q,opt):
    bq=int(_f(q.get("total_buy_quantity",q.get("buyQty",0))or 0))
    sq=int(_f(q.get("total_sell_quantity",q.get("sellQty",0))or 0))
    if bq>0 and sq>0:
        if bq>sq*1.2: return "🟢 BUY"
        if sq>bq*1.2: return "🔴 SELL"
        return "⚪ NEUT"
    return "🟢 BULL" if opt=="CE" else "🔴 BEAR"

# ── Block detection ───────────────────────────────────────────────────────────
prev_state=defaultdict(dict)
vol_hist=defaultdict(list)

def scan_category(api, cat_name, symbols_meta):
    ts=datetime.now(IST).strftime("%H:%M:%S")
    today=datetime.now(IST).date()
    found=0

    for symbol,meta in symbols_meta.items():
        fo_seg=meta["fo_seg"]; step=meta["step"]; lot=meta["lot"]
        fo=scrip_list(api, fo_seg, symbol)
        if not fo: continue

        futs=sorted([(d,i) for i in fo for d in [_parse_exp(i)]
                     if d and "FUT" in _sym(i) and _matches(_sym(i),symbol)],
                    key=lambda x:x[0])
        und=0.0
        for d,item in futs:
            tok=_tok(item)
            if tok:
                v=_ltp(live_quote(api,tok,fo_seg))
                if v>0: und=v; break
        if und<=0 and "cm_seg" in meta:
            cm=scrip_list(api, meta["cm_seg"], symbol)
            for item in cm:
                if _sym(item) in (f"{symbol}-EQ",symbol,f"{symbol}EQ"):
                    tok=_tok(item)
                    if tok:
                        und=_ltp(live_quote(api,tok,meta["cm_seg"]))
                        if und>0: break
        if und<=0: continue

        atm=round(und/step)*step
        watch=[atm+i*step for i in range(-STRIKE_RANGE,STRIKE_RANGE+1)]

        targets=[]
        for item in fo:
            s_item=_sym(item)
            if not _matches(s_item,symbol): continue
            d=_parse_exp(item)
            if not d or d<today: continue
            if "FUT" in s_item:
                targets.append((item,"FUT",None,d))
            else:
                opt=_opt_type(item); sk=_strike_val(item)
                if opt and sk and sk in watch:
                    targets.append((item,opt,int(sk),d))

        for item,kind,strike,exp_d in targets:
            tok=_tok(item)
            if not tok: continue
            q=live_quote(api,tok,fo_seg)
            vol=_vol(q); ltp=_ltp(q); oi=_oi(q); ltq=_ltq(q)
            if vol<=0 and ltp<=0: continue

            ikey=f"{symbol}|{kind}|{strike}|{exp_d}"
            vol_hist[ikey].append(vol)
            if len(vol_hist[ikey])>10: vol_hist[ikey].pop(0)

            prev=prev_state.get(ikey,{})
            prev_vol=prev.get("vol",vol); prev_oi=prev.get("oi",oi)
            vol_jump=vol-prev_vol
            h=vol_hist[ikey]
            avg=sum(h[:-1])/len(h[:-1]) if len(h)>=3 else 0
            oi_chg=oi-prev_oi
            oi_pct=(oi_chg/prev_oi*100) if prev_oi>0 else 0

            is_block=False; reasons=[]
            if avg>0 and vol_jump>=MIN_VOL_JUMP and vol_jump>=avg*VOL_SPIKE_MULT:
                is_block=True; reasons.append(f"Vol+{vol_jump:,} ({vol_jump/avg:.1f}×avg)")
            value_cr=(vol_jump*ltp)/1e7
            if value_cr>=LARGE_VALUE_CR and vol_jump>=MIN_VOL_JUMP:
                is_block=True; reasons.append(f"₹{value_cr:.2f}Cr")
            if ltq>=lot*50 and ltq>0:
                is_block=True; reasons.append(f"BigTrade {ltq:,}")
            if abs(oi_pct)>=OI_CHANGE_PCT and prev_oi>0:
                is_block=True
                reasons.append(f"OI {'↑ADD' if oi_chg>0 else '↓EXIT'} {abs(oi_pct):.0f}%")

            prev_state[ikey]={"vol":vol,"oi":oi,"ltp":ltp}

            if is_block:
                push_block({
                    "time":ts,"category":cat_name,"symbol":symbol,
                    "strike":str(strike) if strike else "FUT","type":kind,
                    "expiry":str(exp_d),"ltp":ltp,"vol_jump":vol_jump,
                    "total_vol":vol,"avg_vol":int(avg),"value_cr":round(value_cr,2),
                    "ltq":ltq,"oi":oi,"oi_chg_pct":round(oi_pct,1),
                    "trend":_trend(q,kind if kind in ("CE","PE") else "CE"),
                    "underlying":und,"reasons":" | ".join(reasons),
                })
                found+=1
            del q
        del fo, targets, futs
        gc.collect()
    return found

# ── Market hours ───────────────────────────────────────────────────────────────
def market_open():
    now=datetime.now(IST); wd=now.weekday()
    nse=(now.replace(hour=9,minute=15,second=0)<=now<=now.replace(hour=15,minute=30,second=0)) and wd<5
    mcx=((wd<5) and now.replace(hour=9,minute=0,second=0)<=now<=now.replace(hour=23,minute=30,second=0)) or \
        ((wd==5) and now.replace(hour=9,minute=0,second=0)<=now<=now.replace(hour=14,minute=0,second=0))
    return nse,mcx

# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    print("[worker] Starting SNY Block Detector worker...", flush=True)
    if not REDIS_URL:
        print("[worker] ❌ UPSTASH_REDIS_REST_URL not set — exiting", flush=True)
        return

    api=None
    last_login=0
    while True:
        try:
            nse,mcx=market_open()
            if not (nse or mcx):
                set_status({"state":"closed","time":datetime.now(IST).strftime("%H:%M:%S")})
                print("[worker] Markets closed, sleeping 60s", flush=True)
                time.sleep(60)
                continue

            # Login / re-login every 20 min
            if api is None or time.time()-last_login>1200:
                print("[worker] Logging in...", flush=True)
                api=login()
                last_login=time.time()

            total=0
            if nse:
                total+=scan_category(api,"Index",INDICES)
                total+=scan_category(api,"Stock",STOCKS)
            if mcx:
                total+=scan_category(api,"Commodity",COMMODITIES)

            set_status({
                "state":"scanning","time":datetime.now(IST).strftime("%H:%M:%S"),
                "blocks_this_cycle":total,"nse":nse,"mcx":mcx,
            })
            print(f"[worker] Cycle done — {total} blocks detected", flush=True)
            gc.collect()
            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            import traceback
            print(f"[worker] ERROR: {e}\n{traceback.format_exc()[-300:]}", flush=True)
            set_status({"state":"error","msg":str(e)[:150],"time":datetime.now(IST).strftime("%H:%M:%S")})
            api=None  # force re-login
            time.sleep(30)

if __name__=="__main__":
    main()
