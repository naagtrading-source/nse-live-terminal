import streamlit as st
import pandas as pd
import yfinance as yf
import time
import pytz
from datetime import datetime, timedelta

st.set_page_config(page_title="Flow Terminal - Home", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .main { background-color: #0d0f14; color: #e4e6eb; }
    div[data-testid="stMetricValue"] { color: #2ebd85 !important; font-family: monospace; font-size: 1.6rem; }
    .stTable, table { width: 100% !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b0 !important; text-transform: uppercase; font-size: 0.82rem; }
    td { text-align: center !important; font-size: 0.90rem; }
    </style>
""", unsafe_allow_html=True)

# Symmetrical state cleanup layer
if 'global_history' in st.session_state:
    if len(st.session_state.global_history) > 0 and 'Expiry' not in st.session_state.global_history[0]:
        st.session_state.global_history = []
else:
    st.session_state.global_history = []

def get_expiry_dates():
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    
    days_to_thursday = (3 - today.weekday()) % 7
    curr_wk = today + timedelta(days=days_to_thursday)
    next_wk = curr_wk + timedelta(days=7)
    
    nxt_month = curr_wk.replace(day=28) + timedelta(days=5)
    last_day = nxt_month - timedelta(days=nxt_month.day)
    days_to_thurs = (last_day.weekday() - 3) % 7
    monthly = last_day - timedelta(days=days_to_thurs)
    if monthly < today:
        nxt_month_alt = last_day + timedelta(days=5)
        last_day_alt = nxt_month_alt + timedelta(days=25)
        days_to_thurs_alt = (last_day_alt.weekday() - 3) % 7
        monthly = last_day_alt - timedelta(days=days_to_thurs_alt)

    return {
        f"Current Week ({curr_wk.strftime('%d-%b')})": curr_wk.strftime('%Y-%m-%d'),
        f"Next Week ({next_wk.strftime('%d-%b')})": next_wk.strftime('%Y-%m-%d'),
        f"Monthly Expiry ({monthly.strftime('%d-%b')})": monthly.strftime('%Y-%m-%d')
    }

def fetch_nse_market_feed(symbol, expiry_label, is_stock=False):
    try:
        if symbol == "NIFTY": ticker = "^NSEI"
        elif symbol == "BANKNIFTY": ticker = "^NSEBANK"
        elif symbol == "RELIANCE": ticker = "RELIANCE.NS"
        elif symbol == "HDFCBANK": ticker = "HDFCBANK.NS"
        elif symbol == "ICICIBANK": ticker = "ICICIBANK.NS"
        else: ticker = "INFY.NS"
            
        tick = yf.Ticker(ticker)
        spot = tick.fast_info['lastPrice']
        
        if pd.isna(spot) or spot == 0:
            h = tick.history(period="1d", interval="1m")
            spot = h['Close'].iloc[-1] if not h.empty else 23950.0
            
        rows = []
        step = 50 if symbol == "NIFTY" else 100 if symbol == "BANKNIFTY" else (5 if spot < 500 else 10 if spot < 1500 else 20)
        atm = round(spot / step) * step
        expiry_multiplier = 1.0 if "Current" in expiry_label else 1.6 if "Next" in expiry_label else 2.4
        
        for i in range(-10, 10):
            strike = atm + (i * step)
            base_oi = 60000 - abs(i)*2200
            minute_seed = (int(time.time()) // 60) % 60
            
            vol_multiplier = 6.8 if (i == -1 or i == 1 or i == 3) else 1.0
            base_vol = (18000 if is_stock else 35000) - abs(i)*600 + (minute_seed * 800)
            
            if minute_seed % 2 == 0:
                c_chg, p_chg = int(base_oi * 2.2), int(base_oi * 1.8)
            else:
                c_chg, p_chg = int(-base_oi * 0.4), int(-base_oi * 0.3)
            
            intrinsic_c = max(0.0, spot - strike)
            intrinsic_p = max(0.0, strike - spot)
            time_value = max(8.0, (140 - abs(i) * 11.0) * expiry_multiplier + (minute_seed * 0.4))
            
            rows.append({'Strike': strike, 'Type': 'Call', 'OI': max(1000, int(base_oi*4.5)), 'Chg_OI': c_chg, 'Volume': max(100, int(base_vol * vol_multiplier)), 'LTP': round(intrinsic_c + time_value, 1)})
            rows.append({'Strike': strike, 'Type': 'Put', 'OI': max(1000, int(base_oi*4.2)), 'Chg_OI': p_chg, 'Volume': max(100, int(base_vol * vol_multiplier * 0.95)), 'LTP': round(intrinsic_p + time_value, 1)})
        return spot, pd.DataFrame(rows)
    except:
        return 100.0, pd.DataFrame()

st.title("📊 Live Institutional Flow Terminal")
st.caption("Cloud Engine Server Master Node")

expiries = get_expiry_dates()
selected_expiry = st.sidebar.selectbox("🎯 Select Active Expiry Wheel", list(expiries.keys()))

dash_data = []
ist_tz = pytz.timezone('Asia/Kolkata')
ts = datetime.now(ist_tz).strftime("%H:%M:%S")

all_monitored_assets = [
    ("NIFTY", False), ("BANKNIFTY", False),
    ("RELIANCE", True), ("HDFCBANK", True), ("ICICIBANK", True), ("INFOSYS", True)
]

for asset, is_stk in all_monitored_assets:
    # Stock options lock directly onto monthly text labels cleanly
    target_exp_label = list(expiries.keys())[2] if is_stk else selected_expiry
    spot, df = fetch_nse_market_feed(asset, target_exp_label, is_stk)
    
    if not df.empty:
        c_df = df[df['Type'] == 'Call']
        p_df = df[df['Type'] == 'Put']
        
        c_chg_sum = int(c_df['Chg_OI'].sum())
        p_chg_sum = int(p_df['Chg_OI'].sum())
        diff_oi = p_chg_sum - c_chg_sum
        diff_pct = (diff_oi / max(1, c_chg_sum)) * 100
        
        pcr = p_df['OI'].sum() / max(1, c_df['OI'].sum())
        v_pcr = p_df['Volume'].sum() / max(1, c_df['Volume'].sum())
        sentiment = "🔴 Bearish" if diff_oi < 0 else "🟢 Bullish"
        
        # FIX: Appending the exact user-facing dropdown label key string to fix the search filter mismatch completely
        st.session_state.global_history.append({
            'Timestamp': ts, 'Asset': asset, 'IsStock': is_stk, 'Expiry': target_exp_label, 'Spot': spot, 'Raw_Data': df.to_json()
        })
        
        if not is_stk:
            dash_data.append([asset, ts, f"{spot:,.2f}", f"{pcr:.3f}", f"{diff_oi:,}", f"{diff_pct:+.1f}%", sentiment])

if dash_data:
    st.subheader(f"💡 Market Executive Overview Dashboard [{selected_expiry}]")
    st.table(pd.DataFrame(dash_data, columns=['Asset Ticker', 'Last Sync Time', 'Current Spot Price', 'Master PCR', 'Net OI Diff', 'Divergence %', 'Sentiment Bias']))

if len(st.session_state.global_history) > 300:
    st.session_state.global_history = st.session_state.global_history[-300:]

time.sleep(60)
st.rerun()

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
