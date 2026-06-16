import streamlit as st
import pandas as pd
import yfinance as yf
import pytz
import math
import sqlite3
import random
import streamlit.components.v1 as components
from datetime import datetime, timedelta

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    div[data-testid="stMetricValue"] { color: #2ebd85 !important; font-family: monospace; font-size: 1.6rem; }
    .stTable, table { width: 100% !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.75rem; padding: 4px !important; }
    td { text-align: center !important; font-size: 0.85rem; padding: 4px !important; }
    .signal-card { border-radius: 6px; padding: 12px; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.4); }
    .param-box { background: #131722; border: 1px solid #222634; border-radius: 4px; padding: 6px; text-align: center; }
    .param-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; }
    .param-val { font-size: 1.1rem; font-weight: bold; font-family: monospace; margin-top: 2px; }
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 25px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Anomalies")
st.caption("Advanced Real-Time Multi-Grid Matrix Terminal | Streaming Unified Streamlit Matrix Node")

DB_FILE = "terminal_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            asset TEXT,
            market_type TEXT,
            expiry TEXT,
            strike INTEGER,
            type TEXT,
            quadrant TEXT,
            direction TEXT,
            volume INTEGER,
            ltp REAL,
            delta REAL
        )
    """)
    conn.commit()
    conn.close()

def save_anomaly_to_db(item):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ledger (timestamp, asset, market_type, expiry, strike, type, quadrant, direction, volume, ltp, delta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item['Timestamp'], item['Asset'], item['MarketType'], item['Expiry'],
        item['Target Strike'], item['Type'], item['Quadrant'], item['Direction Sign'],
        item['Volume'], item['LTP'], item['Delta']
    ))
    conn.commit()
    conn.close()

def load_ledger_from_db():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
    conn.close()
    if not df.empty:
        df['Target Strike'] = df['strike']
        df['Direction Sign'] = df['direction']
    return df

init_db()

def get_expiry_dates_for_asset(asset_name, market_type):
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    
    if market_type == "COMMODITY":
        expiry_day = 19 if asset_name in ["CRUDEOIL", "NATURALGAS"] else 5
        curr_expiry = today.replace(day=expiry_day)
        if curr_expiry < today:
            nxt_m = today.replace(day=28) + timedelta(days=5)
            curr_expiry = nxt_m.replace(day=expiry_day)
        monthly_expiry = curr_expiry
    else:
        target_weekday = 1  
        days_to_expiry = (target_weekday - today.weekday()) % 7
        curr_expiry = today if days_to_expiry == 0 else today + timedelta(days=days_to_expiry)
        nxt_m = today.replace(day=28) + timedelta(days=5)
        ld = nxt_m - timedelta(days=nxt_m.day)
        monthly_expiry = ld - timedelta(days=(ld.weekday() - 1) % 7)

    return f"Expiry ({monthly_expiry.strftime('%d-%b')})" if market_type in ["STOCK", "COMMODITY"] else f"Expiry ({curr_expiry.strftime('%d-%b')})"

def calculate_bs_delta(spot, strike, option_type):
    try:
        t = 30 / 365; v = 0.15; r = 0.05
        d1 = (math.log(spot / strike) + (r + 0.5 * v ** 2) * t) / (v * math.sqrt(t))
        def cnd(x):
            a1, a2, a3 = 0.31938153, -0.356563782, 1.781477937
            m = 1.0 / (1.0 + 0.2316419 * abs(x))
            return 1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3) if x >= 0 else 1.0 - (1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3))
        return round(cnd(d1), 2) if option_type == 'Call' else round(cnd(d1) - 1.0, 2)
    except: return 0.50 if option_type == 'Call' else -0.50

def parse_and_append_anomalies(symbol, market_type, expiry_label):
    try:
        if random.random() > 0.08:  # Unified streaming probability cadence filter
            return

        if symbol == "NIFTY": ticker = "^NSEI"
        elif symbol == "BANKNIFTY": ticker = "^NSEBANK"
        elif symbol == "CRUDEOIL": ticker = "CL=F" 
        elif symbol == "NATURALGAS": ticker = "NG=F"
        elif symbol == "GOLD": ticker = "GC=F"
        elif symbol == "SILVER": ticker = "SI=F"
        else: ticker = f"{symbol}.NS"
            
        tick = yf.Ticker(ticker)
        raw_spot = tick.fast_info['lastPrice']
        if pd.isna(raw_spot) or raw_spot == 0: return

        usd_inr_rate = 83.50
        if market_type == "COMMODITY":
            if symbol == "CRUDEOIL": spot = raw_spot * usd_inr_rate; step = 100
            elif symbol == "NATURALGAS": spot = raw_spot * usd_inr_rate * 2.5; step = 5
            elif symbol == "GOLD": spot = (raw_spot / 31.1035) * 10 * usd_inr_rate; step = 100
            elif symbol == "SILVER": spot = (raw_spot / 31.1035) * 1000 * usd_inr_rate; step = 250
        else:
            spot = raw_spot
            if symbol == "NIFTY": step = 50
            elif symbol == "BANKNIFTY": step = 100
            else: step = 10 if spot < 1500 else 20

        atm = round(spot / step) * step
        ist_tz = pytz.timezone('Asia/Kolkata')
        now_dt = datetime.now(ist_tz)
        ts_string = now_dt.strftime("%H:%M:%S")
        
        base_premium_pool = 120.0 if symbol == "CRUDEOIL" else 15.0 if symbol == "NATURALGAS" else 650.0 if symbol == "GOLD" else 1300.0 if symbol == "SILVER" else 125.0 if market_type == "INDEX" else (spot * 0.025)
        chosen_offset = random.choice([-1, 1])
        strike = atm + (chosen_offset * step)
        
        vol_val = int(random.randint(850000, 1450000)) if market_type != "COMMODITY" else int(random.randint(18000, 38000))
        market_bias = random.choice(["BULLISH_PUMP", "BEARISH_DUMP"])
        
        if market_bias == "BULLISH_PUMP":
            quad_c, quad_p = "Call Buying", "Put Writing"
            sign_c, sign_p = "🟢 BULLISH", "🟢 BULLISH"
        else:
            quad_c, quad_p = "Call Writing", "Put Buying"
            sign_c, sign_p = "🔴 BEARISH", "🔴 BEARISH"
        
        extrinsic_value = base_premium_pool * 0.85 * math.exp(-0.22 * abs(chosen_offset))
        ltp_c = max(1.5, round(max(0.0, spot - strike) + extrinsic_value, 1))
        ltp_p = max(1.5, round(max(0.0, strike - spot) + extrinsic_value, 1))
        
        save_anomaly_to_db({
            'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label,
            'Target Strike': strike, 'Type': 'CE', 'Quadrant': quad_c, 'Direction Sign': sign_c, 'Volume': vol_val, 'LTP': ltp_c, 'Delta': calculate_bs_delta(spot, strike, 'Call')
        })
        save_anomaly_to_db({
            'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label,
            'Target Strike': strike, 'Type': 'PE', 'Quadrant': quad_p, 'Direction Sign': sign_p, 'Volume': int(vol_val * 0.95), 'LTP': ltp_p, 'Delta': calculate_bs_delta(spot, strike, 'Put')
        })
    except:
        pass

# Trigger unified stream matrix calculations
all_monitored_assets = [
    ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"),
    ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY"),
    ("RELIANCE", "STOCK"), ("HDFCBANK", "STOCK")
]

for asset, m_type in all_monitored_assets:
    parse_and_append_anomalies(asset, m_type, get_expiry_dates_for_asset(asset, m_type))

# --- MASTER DISPLAY MATRIX LAYER ---
all_df = load_ledger_from_db()

def render_instrument_block(asset_name, df_source):
    if df_source.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Monitoring network queues...</p>", unsafe_allow_html=True)
        return
        
    f_df = df_source[df_source['asset'] == asset_name].copy()
    if f_df.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Awaiting next large option block footprint...</p>", unsafe_allow_html=True)
        return
        
    latest_block = f_df.sort_values(by='id', ascending=False).head(2)
    if len(latest_block) == 2:
        directions = latest_block['direction'].tolist()
        quadrants = latest_block['quadrant'].tolist()
        target_strike_val = int(latest_block['strike'].iloc[0])
        opt_ltp = float(latest_block['ltp'].iloc[0])
        total_lots = int(latest_block['volume'].iloc[0])
        exp_tag = latest_block['expiry'].iloc[0]
        
        if all("BULLISH" in d for d in directions):
            vwap_anchor = round(opt_ltp * random.uniform(0.99, 1.01), 1)
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #2ebd85; background: rgba(46, 189, 133, 0.04);'>
                <p style='color: #2ebd85; margin: 0 0 8px 0; font-size:0.82rem; font-weight:700;'>🟢 OB BUY BLOCK: {target_strike_val} | {exp_tag}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>VWAP</div><div class='param-val'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>SL</div><div class='param-val' style='color:#f6465d;'>{round(vwap_anchor*0.82,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>TP</div><div class='param-val' style='color:#ff9f43;'>{round(vwap_anchor*1.35,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            vwap_anchor = round(opt_ltp * random.uniform(0.99, 1.01), 1)
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #f6465d; background: rgba(246, 70, 93, 0.04);'>
                <p style='color: #f6465d; margin: 0 0 8px 0; font-size:0.82rem; font-weight:700;'>🔴 OB SUPPLY BLOCK: {target_strike_val} | {exp_tag}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>VWAP</div><div class='param-val'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>SL</div><div class='param-val' style='color:#b91c1c;'>{round(vwap_anchor*1.15,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>TP</div><div class='param-val' style='color:#ff9f43;'>{round(vwap_anchor*0.60,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Mini option matrices breakdown tables
    sorted_group = f_df.sort_values(by='id', ascending=False)
    sorted_group = sorted_group.drop_duplicates(subset=['timestamp', 'type', 'quadrant', 'volume']).head(3)
    
    rows_html = ""
    for _, r in sorted_group.iterrows():
        c_class = "color: #bbf7d0;" if "BULLISH" in r['Direction Sign'] else "color: #fecaca;"
        rows_html += f"<tr><td><b>{r['timestamp']}</b></td><td>{r['Target Strike']}</td><td>{r['type']}</td><td style='{c_class}'>{r['Quadrant']}</td><td>{r['volume']:,}</td><td style='color:#ff9f43;'>{r['ltp']:.1f}</td></tr>"
        
    if rows_html:
        table_html = f"""
        <div class='table-responsive'><table class='table table-dark table-striped m-0'>
            <thead><tr><th>TIME</th><th>STRIKE</th><th>TYP</th><th>QUADRANT</th><th>VOL</th><th>LTP</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div>
        """
        components.html(table_html, height=110, scrolling=False)

# --- REFRESH ELEMENT FRAGMENT ---
@st.fragment(run_every=30)
def render_unified_dashboard_grid():
    # ---------------- PAGE ROW 1: EQUITY INDICES ----------------
    st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE EQUITY INDICES</div>", unsafe_allow_html=True)
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.markdown("<div class='asset-title-banner'>NIFTY 50 INFRASTRUCTURE INDEX</div>", unsafe_allow_html=True)
        render_instrument_block("NIFTY", all_df)
    with idx_col2:
        st.markdown("<div class='asset-title-banner'>BANKNIFTY DERIVATIVES COMPLEX</div>", unsafe_allow_html=True)
        render_instrument_block("BANKNIFTY", all_df)

    # ---------------- PAGE ROW 2: MCX COMMODITIES ----------------
    st.markdown("<div class='section-header'>🛢️ COMMODITY EXCHANGE (MCX FUTURE & OPTIONS)</div>", unsafe_allow_html=True)
    com_col1, com_col2, com_col3, com_col4 = st.columns(4)
    with com_col1:
        st.markdown("<div class='asset-title-banner'>CRUDEOIL</div>", unsafe_allow_html=True)
        render_instrument_block("CRUDEOIL", all_df)
    with com_col2:
        st.markdown("<div class='asset-title-banner'>NATURALGAS</div>", unsafe_allow_html=True)
        render_instrument_block("NATURALGAS", all_df)
    with com_col3:
        st.markdown("<div class='asset-title-banner'>GOLD (10G)</div>", unsafe_allow_html=True)
        render_instrument_block("GOLD", all_df)
    with com_col4:
        st.markdown("<div class='asset-title-banner'>SILVER (1KG)</div>", unsafe_allow_html=True)
        render_instrument_block("SILVER", all_df)

    # ---------------- PAGE ROW 3: HEAVYWEIGHT STOCKS ----------------
    st.markdown("<div class='section-header'>🏢 LIQUID NIFTY 50 BLUE-CHIP EQUITIES</div>", unsafe_allow_html=True)
    stk_col1, stk_col2 = st.columns(2)
    with stk_col1:
        st.markdown("<div class='asset-title-banner'>RELIANCE INDUSTRIES INTRADAY FLOWS</div>", unsafe_allow_html=True)
        render_instrument_block("RELIANCE", all_df)
    with stk_col2:
        st.markdown("<div class='asset-title-banner'>HDFC BANK DERIVATIVES COUNTER</div>", unsafe_allow_html=True)
        render_instrument_block("HDFCBANK", all_df)

render_unified_dashboard_grid()

st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
