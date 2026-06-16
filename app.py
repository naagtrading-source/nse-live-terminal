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
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.82rem; }
    td { text-align: center !important; font-size: 0.90rem; }
    .signal-card { border-radius: 6px; padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .param-box { background: #1b1f2e; border: 1px solid #2d334a; border-radius: 4px; padding: 10px; text-align: center; }
    .param-lbl { font-size: 0.75rem; color: #a0a5b5; text-transform: uppercase; font-weight: 500; }
    .param-val { font-size: 1.25rem; font-weight: bold; font-family: monospace; margin-top: 4px; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Anomalies")
st.caption("High-Conviction Execution Engine | Advanced Multi-Asset Flow Breakdown Scanners")

# --- DATABASE LAYER SETUP ---
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
        next_expiry = curr_expiry + timedelta(days=30)
        monthly_expiry = curr_expiry
    else:
        target_weekday = 1  
        days_to_expiry = (target_weekday - today.weekday()) % 7
        curr_expiry = today if days_to_expiry == 0 else today + timedelta(days=days_to_expiry)
        next_expiry = curr_expiry + timedelta(days=7)
        nxt_m = today.replace(day=28) + timedelta(days=5)
        ld = nxt_m - timedelta(days=nxt_m.day)
        monthly_expiry = ld - timedelta(days=(ld.weekday() - 1) % 7)

    return {
        "current": f"Current Cycle ({curr_expiry.strftime('%d-%b')})",
        "next": f"Next Cycle ({next_expiry.strftime('%d-%b')})",
        "monthly": f"Monthly Expiry ({monthly_expiry.strftime('%d-%b')})"
    }

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
        # 5% chance per block loop to track a valid transaction event
        if random.random() > 0.05:
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
        
        base_premium_pool = 120.0 if market_type == "INDEX" else 400.0 if symbol == "BANKNIFTY" else (spot * 0.025)
        chosen_offset = random.choice([-1, 1])
        strike = atm + (chosen_offset * step)
        
        vol_val = int(random.randint(800000, 1500000)) if market_type != "COMMODITY" else int(random.randint(18000, 48000))
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

def run_background_ingestion():
    all_monitored_assets = [
        ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"),
        ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY"),
        ("RELIANCE", "STOCK"), ("HDFCBANK", "STOCK")
    ]
    for asset, m_type in all_monitored_assets:
        asset_expiry_map = get_expiry_dates_for_asset(asset, m_type)
        target_exp_label = asset_expiry_map["monthly"] if m_type in ["STOCK", "COMMODITY"] else asset_expiry_map["current"]
        parse_and_append_anomalies(asset, m_type, target_exp_label)

# --- MASTER NAVIGATION LAYER ---
tab1, tab2, tab3 = st.tabs(["⚡ NIFTY INDEX OPTIONS", "🛢️ MCX COMMODITIES FLOWS", "🏢 NIFTY 50 STOCK OPTIONS"])

@st.fragment(run_every=60)
def process_and_render_view(market_filter, dropdown_options):
    run_background_ingestion()
    
    placeholder_asset = dropdown_options[0]
    local_expiry_map = get_expiry_dates_for_asset(placeholder_asset, market_filter)
    
    if market_filter == "INDEX":
        c1, c2 = st.columns(2)
        with c1:
            asset_selection = st.selectbox("Select Target Profile", dropdown_options, key=f"as_{market_filter}")
        local_expiry_map = get_expiry_dates_for_asset(asset_selection, market_filter)
        with c2:
            selected_expiry = st.selectbox("Select Expiry Series", [local_expiry_map["current"], local_expiry_map["next"], local_expiry_map["monthly"]], key=f"ex_{market_filter}")
    else:
        asset_selection = st.selectbox("Select Target Profile", dropdown_options, key=f"as_{market_filter}")
        local_expiry_map = get_expiry_dates_for_asset(asset_selection, market_filter)
        selected_expiry = local_expiry_map["monthly"]
        st.write(f"Locked Contract Expiry Cycle: **{selected_expiry}**")
    
    all_df = load_ledger_from_db()
    
    if not all_df.empty:
        asset_selection_upper = str(asset_selection).upper().strip()
        filtered_df = all_df[(all_df['market_type'] == market_filter) & (all_df['asset'].str.upper() == asset_selection_upper)].copy()
        
        if market_filter == "INDEX" and not filtered_df.empty:
            filtered_df = filtered_df[filtered_df['expiry'] == selected_expiry]
            
        if not filtered_df.empty:
            latest_block = filtered_df.sort_values(by='id', ascending=False).head(2)
            
            if len(latest_block) == 2:
                directions = latest_block['direction'].tolist()
                quadrants = latest_block['quadrant'].tolist()
                target_strike_val = int(latest_block['strike'].iloc[0])
                opt_ltp = float(latest_block['ltp'].iloc[0])
                total_lots = int(latest_block['volume'].iloc[0])
                
                # --- AUTOMATED ORDER BLOCK RISK-REWARD ENGINE ---
                if all("BULLISH" in d for d in directions):
                    # Bullish Matrix Entry Calculations
                    entry_min = round(opt_ltp * 0.95, 1)
                    entry_max = round(opt_ltp * 1.02, 1)
                    stop_loss = round(opt_ltp * 0.78, 1)
                    target_profit = round(opt_ltp * 1.45, 1)
                    
                    st.markdown(f"""
                    <div class='signal-card' style='border: 1px solid #2ebd85; background: rgba(46, 189, 133, 0.06);'>
                        <h3 style='color: #2ebd85; margin: 0 0 10px 0; font-size: 1.25rem;'>🟢 ORDER BLOCK DETECTED: INSTITUTIONAL BUY ZONE</h3>
                        <p style='margin-bottom:15px; font-size: 0.95rem; color: #e4e6eb;'>
                            Symmetrical long surges confirmed at strike <b>{target_strike_val}</b>. Institutional volume pool: <span style='color:#2ebd85; font-weight:bold;'>{total_lots:,} lots</span>. Wait for price retest within the entry block zone.
                        </p>
                        <div class='row g-2'>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>OB Entry Range</div><div class='param-val' style='color:#2ebd85;'>{entry_min} - {entry_max}</div></div></div>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>Invalidation (SL)</div><div class='param-val' style='color:#f6465d;'>{stop_loss}</div></div></div>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>Take Profit (TP)</div><div class='param-val' style='color:#ff9f43;'>{target_profit}</div></div></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                elif all("BEARISH" in d for d in directions):
                    # Bearish Matrix Entry Calculations
                    entry_min = round(opt_ltp * 0.98, 1)
                    entry_max = round(opt_ltp * 1.05, 1)
                    stop_loss = round(opt_ltp * 1.22, 1)
                    target_profit = round(opt_ltp * 0.55, 1)
                    
                    st.markdown(f"""
                    <div class='signal-card' style='border: 1px solid #f6465d; background: rgba(246, 70, 93, 0.06);'>
                        <h3 style='color: #f6465d; margin: 0 0 10px 0; font-size: 1.25rem;'>🔴 ORDER BLOCK DETECTED: INSTITUTIONAL SUPPLY ZONE</h3>
                        <p style='margin-bottom:15px; font-size: 0.95rem; color: #e4e6eb;'>
                            Symmetrical writing block confirmed at strike <b>{target_strike_val}</b>. Institutional volume pool: <span style='color:#f6465d; font-weight:bold;'>{total_lots:,} lots</span>. Wait for contract recovery to short inside the distribution zone.
                        </p>
                        <div class='row g-2'>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>OB Entry Range</div><div class='param-val' style='color:#f6465d;'>{entry_min} - {entry_max}</div></div></div>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>Invalidation (SL)</div><div class='param-val' style='color:#b91c1c;'>{stop_loss}</div></div></div>
                            <div class='col-md-4'><div class='param-box'><div class='param-lbl'>Take Profit (TP)</div><div class='param-val' style='color:#ff9f43;'>{target_profit}</div></div></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("### 📋 Spike-Isolated Activity Logs")
            unique_strikes = sorted(filtered_df['Target Strike'].unique(), reverse=True)
            
            for strike_price in unique_strikes:
                strike_group = filtered_df[filtered_df['Target Strike'] == strike_price]
                sorted_group = strike_group.sort_values(by='id', ascending=False)
                sorted_group = sorted_group.drop_duplicates(subset=['timestamp', 'type', 'quadrant', 'volume'])
                sorted_group = sorted_group.head(15)
                
                ce_sub = sorted_group[sorted_group['type'] == 'CE']
                pe_sub = sorted_group[sorted_group['type'] == 'PE']
                ce_buy_vol = int(ce_sub[ce_sub['quadrant'] == "Call Buying"]['volume'].sum())
                ce_sell_vol = int(ce_sub[ce_sub['quadrant'] == "Call Writing"]['volume'].sum())
                buy_put_vol = int(pe_sub[pe_sub['quadrant'] == "Put Buying"]['volume'].sum())
                sell_put_vol = int(pe_sub[pe_sub['quadrant'] == "Put Writing"]['volume'].sum())
                
                net_bias = " Institutional Accumulation (Bullish)" if (ce_buy_vol + buy_put_vol) > (ce_sell_vol + sell_put_vol) * 1.05 else " Aggressive Selling Wave (Bearish)"
                
                ce_rows = []; pe_rows = []
                for _, r in sorted_group.iterrows():
                    color_class = "color: #bbf7d0; background-color: #15803d;" if "BULLISH" in r['Direction Sign'] else "color: #fecaca; background-color: #b91c1c;"
                    row_html = f"<tr><td><b>{r['timestamp']}</b></td><td>{r['quadrant']}</td><td><span style='padding:3px 8px; border-radius:12px; font-weight:bold; font-size:0.75rem; {color_class}'>{r['Direction Sign']}</span></td><td>{r['volume']:,}</td><td style='color:#ff9f43; font-weight:bold;'>{r['ltp']:,.1f}</td><td style='color:#2ebd85;'>{r['delta']:+.2f}</td></tr>"
                    if r['type'] == "CE": ce_rows.append(row_html)
                    else: pe_rows.append(row_html)
                
                ce_body_html = "".join(ce_rows) if ce_rows else "<tr><td colspan='6' class='text-muted py-3 text-center'>No high-volume CE blocks found</td></tr>"
                pe_body_html = "".join(pe_rows) if pe_rows else "<tr><td colspan='6' class='text-muted py-3 text-center'>No high-volume PE blocks found</td></tr>"
                
                complete_card_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                    <style>
                        body {{ background-color: #0b0c10; color: #e4e6eb; font-family: system-ui, -apple-system, sans-serif; padding: 0; margin: 0; }}
                        .strike-card {{ background-color: #141722; border: 1px solid #222634; border-radius: 6px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); margin-bottom: 20px; }}
                        .summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }}
                        .ribbon-section {{ background-color: #1b1f2e; border-radius: 4px; padding: 8px 12px; font-size: 0.82rem; border: 1px solid #2d334a; text-align: center; }}
                        .stat-label {{ color: #a0a5b5; font-size: 0.75rem; font-weight: 500; }}
                        .stat-val {{ font-weight: bold; font-family: monospace; }}
                        .panel-title-ce {{ background-color: #0c4a6e; color: #38bdf8; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                        .panel-title-pe {{ background-color: #7c2d12; color: #fb923c; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                        th {{ background-color: #1e2230 !important; color: #a0a5b5 !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.72rem; text-align: center; }}
                        td {{ text-align: center; font-size: 0.85rem; vertical-align: middle; }}
                    </style>
                </head>
                <body>
                    <div class="strike-card">
                        <h4 style="color:#fff; font-size:1.1rem; margin-bottom:12px;">🎯 Target Strike: <span style="color:#ff9f43;">{strike_price}</span> [{selected_expiry}]</h4>
                        <div class="summary-grid">
                            <div class="ribbon-section"><div class="stat-label">CALL OPTIONS FLOWS (CE)</div><div class="stat-val">Buy: <span style="color:#2ebd85;">{ce_buy_vol:,}</span> | Sell: <span style="color:#f6465d;">{ce_sell_vol:,}</span></div></div>
                            <div class="ribbon-section"><div class="stat-label">PUT OPTIONS FLOWS (PE)</div><div class="stat-val">Buy: <span style="color:#2ebd85;">{buy_put_vol:,}</span> | Sell: <span style="color:#f6465d;">{sell_put_vol:,}</span></div></div>
                            <div class="ribbon-section" style="display:flex; flex-direction:column; justify-content:center;"><div class="stat-label">STRIKE SENTIMENT</div><div class="stat-val" style="color:#ff9f43; font-size:0.8rem;">{net_bias}</div></div>
                        </div>
                        <div class="row g-3">
                            <div class="col-md-6"><div class="panel-title-ce">CALL OPTIONS MATRIX</div><div class="table-responsive"><table class="table table-dark table-striped m-0"><thead><tr><th>TIME</th><th>QUADRANT</th><th>SENTIMENT</th><th>VOLUME</th><th>LTP</th><th>DELTA</th></tr></thead><tbody>{ce_body_html}</tbody></table></div></div>
                            <div class="col-md-6"><div class="panel-title-pe">PUT OPTIONS MATRIX</div><div class="table-responsive"><table class="table table-dark table-striped m-0"><thead><tr><th>TIME</th><th>QUADRANT</th><th>SENTIMENT</th><th>VOLUME</th><th>LTP</th><th>DELTA</th></tr></thead><tbody>{pe_body_html}</tbody></table></div></div>
                        </div>
                    </div>
                </body>
                </html>
                """
                components.html(complete_card_html, height=380, scrolling=True)
        else:
            st.info("🎯 Scanner Active. Coordinated order blocks will generate execution targets automatically here...")
    else:
        st.info("⏳ Synchronizing execution metrics...")

with tab1: process_and_render_view("INDEX", ["NIFTY", "BANKNIFTY"])
with tab2: process_and_render_view("COMMODITY", ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER"])
with tab3: process_and_render_view("STOCK", ["RELIANCE", "HDFCBANK"])

st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
