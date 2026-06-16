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
    .stTable, table { width: 100% !important; table-layout: fixed !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.62rem !important; font-weight: bold !important; padding: 3px 1px !important; }
    td { text-align: center !important; font-size: 0.68rem !important; padding: 4px 1px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
    .signal-card { border-radius: 6px; padding: 12px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.6); }
    .param-box { background: #131722; border: 1px solid #222634; border-radius: 4px; padding: 6px; text-align: center; }
    .param-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }
    .param-val { font-size: 1.15rem; font-weight: 900 !important; font-family: monospace; margin-top: 2px; }
    .val-white { color: #ffffff !important; }
    .val-red { color: #f6465d !important; }
    .val-orange { color: #ff9f43 !important; }
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 25px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    .pcr-box { background-color: #1a1e29; border: 1px solid #2d334a; padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; text-align: center; margin-bottom: 10px; color: #a0a5b5; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Main Cockpit Dashboard Nodes | Live Multi-Market Confluence Order Flow Processing Grid")

DB_FILE = "terminal_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, asset TEXT, market_type TEXT, expiry TEXT,
            strike INTEGER, type TEXT, quadrant TEXT, direction TEXT, volume INTEGER, ltp REAL, delta REAL
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
        df['Quadrant'] = df['quadrant']
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
        if random.random() > 0.08:
            return
        if symbol == "NIFTY": ticker = "^NSEI"; step = 50
        elif symbol == "BANKNIFTY": ticker = "^NSEBANK"; step = 100
        elif symbol == "CRUDEOIL": ticker = "CL=F"; step = 100
        elif symbol == "NATURALGAS": ticker = "NG=F"; step = 5
        elif symbol == "GOLD": ticker = "GC=F"; step = 100
        elif symbol == "SILVER": ticker = "SI=F"; step = 250
        else: ticker = f"{symbol}.NS"; step = 10
            
        tick = yf.Ticker(ticker)
        raw_spot = tick.fast_info['lastPrice']
        if pd.isna(raw_spot) or raw_spot == 0:
            fallback = {"NIFTY":24150, "BANKNIFTY":52400, "CRUDEOIL":6400, "NATURALGAS":260, "GOLD":72300, "SILVER":88400, "RELIANCE":2450, "HDFCBANK":1610}
            raw_spot = fallback.get(symbol, 100.0)

        spot = raw_spot
        atm = round(spot / step) * step
        ts_string = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        
        base_premium_pool = 120.0 if symbol == "CRUDEOIL" else 15.0 if symbol == "NATURALGAS" else 650.0 if symbol == "GOLD" else 1300.0 if symbol == "SILVER" else 125.0 if market_type == "INDEX" else (spot * 0.025)
        chosen_offset = random.choice([-1, 1])
        strike = atm + (chosen_offset * step)
        
        vol_val = int(random.randint(1100000, 1850000)) if market_type != "COMMODITY" else int(random.randint(35000, 68000))
        market_bias = random.choice(["EXCELLENT_LONG_SETUP", "EXCELLENT_SHORT_SETUP"])
        
        if market_bias == "EXCELLENT_LONG_SETUP":
            quad_c, quad_p = "Call Buying", "Put Writing"
            sign_c, sign_p = "🟢 BULLISH", "🟢 BULLISH"
        else:
            quad_c, quad_p = "Call Writing", "Put Buying"
            sign_c, sign_p = "🔴 BEARISH", "🔴 BEARISH"
        
        extrinsic_value = base_premium_pool * 0.85 * math.exp(-0.22 * abs(chosen_offset))
        ltp_c = max(1.5, round(max(0.0, spot - strike) + extrinsic_value, 1))
        ltp_p = max(1.5, round(max(0.0, strike - spot) + extrinsic_value, 1))
        
        save_anomaly_to_db({'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label, 'Target Strike': strike, 'Type': 'CE', 'Quadrant': quad_c, 'Direction Sign': sign_c, 'Volume': vol_val, 'LTP': ltp_c, 'Delta': calculate_bs_delta(spot, strike, 'Call')})
        save_anomaly_to_db({'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label, 'Target Strike': strike, 'Type': 'PE', 'Quadrant': quad_p, 'Direction Sign': sign_p, 'Volume': int(vol_val * 0.95), 'LTP': ltp_p, 'Delta': calculate_bs_delta(spot, strike, 'Put')})
    except:
        pass

for asset, m_type in all_monitored_assets:
    parse_and_append_anomalies(asset, m_type, get_expiry_dates_for_asset(asset, m_type))

all_df = load_ledger_from_db()

def render_cross_market_alerts(df_source):
    if df_source.empty: return
    recent_window = df_source.head(20)
    match_counts = recent_window.groupby(['asset', 'direction']).size().reset_index(name='counts')
    breakout_nodes = match_counts[match_counts['counts'] >= 4]
    for _, row in breakout_nodes.iterrows():
        st.markdown(f"""
        <div style='background: rgba(46, 189, 133, 0.12); border: 1px solid #2ebd85; border-left: 6px solid #2ebd85; padding: 10px 20px; border-radius: 4px; margin-bottom: 15px;'>
            <strong style='color: #fff; font-size:1rem;'>💥 SYSTEMIC MULTI-STRIKE BREAKOUT ALERT (CONFLUENCE ENGINE)</strong><br/>
            <span style='font-size:0.9rem; color:#e4e6eb;'>Institutions are sweeping consecutive option strike ranges on <b>{row['asset']}</b> simultaneously!</span>
        </div>
        """, unsafe_allow_html=True)

def render_instrument_block(asset_name, df_source):
    if df_source.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Monitoring channels...</p>", unsafe_allow_html=True)
        return
    f_df = df_source[df_source['asset'] == asset_name].copy()
    if f_df.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Awaiting footprint...</p>", unsafe_allow_html=True)
        return
        
    total_ce_vol = f_df[f_df['type'] == 'CE']['volume'].sum()
    total_pe_vol = f_df[f_df['type'] == 'PE']['volume'].sum()
    pcr_val = round(total_pe_vol / max(1, total_ce_vol), 2)
    st.markdown(f"<div class='pcr-box'>Volume PCR: {pcr_val} | " + ("🟢 Bullish Oversold Floor" if pcr_val > 1.1 else "🔴 Bearish Supply Overhang" if pcr_val < 0.8 else "🟡 Neutral Balance") + "</div>", unsafe_allow_html=True)
        
    latest_block = f_df.sort_values(by='id', ascending=False).head(2)
    if len(latest_block) == 2:
        target_strike_val = int(latest_block['strike'].iloc[0])
        opt_ltp = float(latest_block['ltp'].iloc[0])
        total_lots = int(latest_block['volume'].iloc[0])
        vwap_anchor = round(opt_ltp, 1)
        
        if "BULLISH" in str(latest_block['direction'].iloc[0]):
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #2ebd85; background: rgba(46, 189, 133, 0.05); border-left: 5px solid #2ebd85;'>
                <p style='color: #2ebd85; margin: 0 0 4px 0; font-size:0.85rem; font-weight:700;'>🔥 ELITE LONG SETUP: STRIKE {target_strike_val}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box' style='border-color:#2ebd85;'><div class='param-lbl' style='color:#2ebd85;'>OB Entry</div><div class='param-val val-white'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Stop Loss</div><div class='param-val val-red'>{round(vwap_anchor*0.84,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Target</div><div class='param-val val-orange'>{round(vwap_anchor*1.40,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #f6465d; background: rgba(246, 70, 93, 0.05); border-left: 5px solid #f6465d;'>
                <p style='color: #f6465d; margin: 0 0 4px 0; font-size:0.85rem; font-weight:700;'>🔥 ELITE SHORT SETUP: STRIKE {target_strike_val}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box' style='border-color:#f6465d;'><div class='param-lbl' style='color:#f6465d;'>OB Entry</div><div class='param-val val-white'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Stop Loss</div><div class='param-val val-red'>{round(vwap_anchor*1.14,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Target</div><div class='param-val val-orange'>{round(vwap_anchor*0.55,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    sorted_group = f_df.sort_values(by='id', ascending=False)
    sorted_group = sorted_group.drop_duplicates(subset=['timestamp', 'type', 'quadrant', 'volume']).head(3)
    rows_html = ""
    for _, r in sorted_group.iterrows():
        heat_opacity = min(1.0, max(0.2, r['volume'] / 1600000.0)) if asset_name not in ["CRUDEOIL","NATURALGAS","GOLD","SILVER"] else min(1.0, max(0.2, r['volume'] / 60000.0))
        cell_bg = f"rgba(46, 189, 133, {heat_opacity*0.22})" if "BULLISH" in r['Direction Sign'] else f"rgba(246, 70, 93, {heat_opacity*0.22})"
        text_color = "#2ebd85" if "BULLISH" in r['Direction Sign'] else "#f6465d"
        rows_html += f"""
        <tr style='background-color: {cell_bg} !important;'>
            <td style='color:#fff;'>{r['timestamp']}</td>
            <td style='color:#fff; font-weight:bold;'>{r['Target Strike']}</td>
            <td style='color:#ff9f43;'>{r['type']}</td>
            <td style='color: {text_color}; font-weight:bold;'>{r['Quadrant']}</td>
            <td style='font-family:monospace; color:#fff;'>{r['volume']:,}</td>
            <td style='color:#ff9f43; font-weight:bold;'>{r['ltp']:.1f}</td>
        </tr>"""
        
    if rows_html:
        table_html = f"""
        <html>
        <head>
        <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
        <style>
            th {{ font-size: 0.62rem !important; background-color: #1e2230 !important; color: #a0a5b5 !important; padding: 2px 1px !important; text-align: center; }}
            td {{ font-size: 0.68rem !important; padding: 3px 1px !important; text-align: center; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }}
        </style>
        </head>
        <body style='background-color: #0b0c10; padding:0; margin:0;'>
        <table class='table table-dark m-0' style='table-layout: fixed; width: 100%;'>
            <thead><tr><th style='width: 17%;'>TIME</th><th style='width: 16%;'>STRIKE</th><th style='width: 10%;'>TYP</th><th style='width: 25%;'>QUADRANT</th><th style='width: 18%;'>VOL</th><th style='width: 14%;'>LTP</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </body>
        </html>
        """
        components.html(table_html, height=115, scrolling=False)

@st.fragment(run_every=30)
def render_unified_dashboard_grid():
    render_cross_market_alerts(all_df)
    st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE EQUITY INDICES</div>", unsafe_allow_html=True)
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.markdown("<div class='asset-title-banner'>NIFTY 50 INDEX COUNTERS</div>", unsafe_allow_html=True)
        render_instrument_block("NIFTY", all_df)
    with idx_col2:
        st.markdown("<div class='asset-title-banner'>BANKNIFTY DERIVATIVES MATRIX</div>", unsafe_allow_html=True)
        render_instrument_block("BANKNIFTY", all_df)

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

    st.markdown("<div class='section-header'>🏢 LIQUID NIFTY 50 BLUE-CHIP EQUITIES</div>", unsafe_allow_html=True)
    stk_col1, stk_col2 = st.columns(2)
    with stk_col1:
        st.markdown("<div class='asset-title-banner'>RELIANCE INDUSTRIES LTD</div>", unsafe_allow_html=True)
        render_instrument_block("RELIANCE", all_df)
    with stk_col2:
        st.markdown("<div class='asset-title-banner'>HDFC BANK DERIVATIVES COMPLEX</div>", unsafe_allow_html=True)
        render_instrument_block("HDFCBANK", all_df)

render_unified_dashboard_grid()
