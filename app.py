"""
SNY Block Detector — STREAMLIT UI
==================================
Lightweight read-only dashboard. NO Kotak SDK, NO heavy imports.
Reads block events from Upstash Redis (written by worker.py) and
renders a live feed + summary tables.

Memory footprint: ~80MB — fits comfortably in 512MB free tier.

Required environment variables:
  UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
"""
import streamlit as st
import pandas as pd
import os, json, requests
from datetime import datetime
import pytz

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

IST = pytz.timezone("Asia/Kolkata")
REDIS_URL   = os.environ.get("UPSTASH_REDIS_REST_URL","").rstrip("/")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN","")

def redis_cmd(*args):
    if not REDIS_URL or not REDIS_TOKEN: return None
    try:
        r=requests.post(REDIS_URL,
            headers={"Authorization":f"Bearer {REDIS_TOKEN}"},
            json=list(args), timeout=10)
        return r.json().get("result")
    except Exception as e:
        return None

def get_blocks():
    """Read all block events from Redis list."""
    raw=redis_cmd("LRANGE","blocks","0","99")
    if not raw: return []
    out=[]
    for item in raw:
        try: out.append(json.loads(item))
        except: pass
    return out

def get_status():
    raw=redis_cmd("GET","worker_status")
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## ⚡ SNY Block Order Detector")
st.caption("Real-time institutional block scanner — Index · Stocks · Commodities")

status=get_status()
blocks=get_blocks()
ist_now=datetime.now(IST)

c1,c2,c3,c4=st.columns(4)
with c1:
    state=status.get("state","unknown")
    if state=="scanning": st.success("🟢 Worker Active")
    elif state=="closed": st.info("🌙 Markets Closed")
    elif state=="error":  st.error("🔴 Worker Error")
    else: st.warning("⏳ Connecting...")
with c2: st.metric("NSE","🟢 OPEN" if status.get("nse") else "🔴 CLOSED")
with c3: st.metric("MCX","🟢 OPEN" if status.get("mcx") else "🔴 CLOSED")
with c4: st.metric("IST",ist_now.strftime("%H:%M:%S"))

if not REDIS_URL:
    st.error("⚠️ UPSTASH_REDIS_REST_URL / TOKEN not configured. Add them in environment settings.")

if status.get("state")=="error":
    st.error(f"Worker error: {status.get('msg','unknown')}")

st.markdown("---")

# ── Live Feed ──────────────────────────────────────────────────────────────────
st.markdown("### 📡 Live Block Feed")
if not blocks:
    if status.get("state")=="closed":
        st.info("🌙 Markets closed. Block feed runs during market hours.\nNSE 9:15–15:30 | MCX 9:00–23:30 IST")
    else:
        st.caption("⏳ Monitoring... no blocks detected yet. Large orders appear here as they trigger.")
else:
    for b in blocks[:25]:
        icon="🔵" if b["type"]=="CE" else "🔴" if b["type"]=="PE" else "🟡"
        line=(f"`{b['time']}` {icon} **{b['symbol']} {b['strike']} {b['type']}** "
              f"[{b['expiry']}] | LTP ₹{b['ltp']} | **{b['reasons']}** | {b['trend']}")
        val=b.get("value_cr",0)
        if val>=2.0:   st.error(line)
        elif val>=0.5: st.warning(line)
        else:          st.info(line)

st.markdown("---")

# ── Summary tables ─────────────────────────────────────────────────────────────
t1,t2,t3=st.tabs(["📈 Index Blocks","📊 Stock Blocks","🛢️ Commodity Blocks"])

def table(cat):
    rows=[b for b in blocks if b["category"]==cat]
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

with t1: table("Index")
with t2: table("Stock")
with t3: table("Commodity")

st.caption(f"Last worker scan: {status.get('time','—')} | Blocks stored: {len(blocks)}")

# ── Auto-refresh every 10s (UI is light, can refresh fast) ────────────────────
st.components.v1.html(
    "<script>setTimeout(function(){window.location.reload();},10000);</script>",
    height=0,width=0)
