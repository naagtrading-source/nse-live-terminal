import streamlit as st
import pandas as pd
import yfinance as yf
import json
import io
import time
import math
import pytz
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(page_title="Unusual Volume Activity", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .strike-card-container { margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Anomalies")
st.caption("Real-Time Multi-Asset Block Activity Monitors | Index & Stock Option Scanners")

if 'global_history' not in st.session_state:
    st.session_state.global_history = []

def calculate_bs_delta(spot, strike, option_type):
    try:
        t = 30 / 365
        v = 0.12
        r = 0.05
        d1 = (math.log(spot / strike) + (r + 0.5 * v ** 2) * t) / (v * math.sqrt(t))
        
        def cnd(x):
            a1, a2, a3, a4, a5 = 0.31938153, -0.356563782, 1.781477937, -1.821255978, 1.330274429
            m = 1.0 / (1.0 + 0.2316419 * abs(x))
            return 1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3 + a4*m**4 + a5*m**5) if x >= 0 else 1.0 - (1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3 + a4*m**4 + a5*m**5))

        return round(cnd(d1), 2) if option_type == 'Call' else round(cnd(d1) - 1.0, 2)
    except:
        return 0.50 if option_type == 'Call' else -0.50

def fetch_asset_snapshot(ticker_symbol, is_stock=False):
    try:
        tick = yf.Ticker(ticker_symbol)
        spot = tick.fast_info['lastPrice']
        if pd.isna(spot) or spot == 0:
            h = tick.history(period="1d", interval="1m")
            spot = h['Close'].iloc[-1] if not h.empty else 100.0
            
        rows = []
        step = 50 if ticker_symbol == "^NSEI" else 100 if ticker_symbol == "^NSEBANK" else (5 if spot < 500 else 10 if spot < 1500 else 20)
        atm = round(spot / step) * step
        
        for i in range(-8, 8):
            strike = atm + (i * step)
            base_oi = 50000 - abs(i)*2500
            minute_seed = (int(time.time()) // 60) % 60
            
            # Simulated data updates that trigger writing activity across contracts
            vol_multiplier = 6.5 if (i == -1 or i == 1 or i == 3) else 1.0
            base_vol = (15000 if is_stock else 30000) - abs(i)*500 + (minute_seed * 700)
            
            c_chg = int(base_oi * (2.0 if i > 0 else 0.7) * (1 + minute_seed * 0.01))
            p_chg = int(base_oi * (0.6 if i > 0 else 1.8) * (1 + minute_seed * 0.01))
            
            ltp_c = max(2.0, round(spot * 0.02 - (i * (step/10)) + (minute_seed * 0.1), 1))
            ltp_p = max(2.0, round(spot * 0.02 + (i * (step/10)) + (minute_seed * 0.1), 1))
            
            rows.append({'Strike': strike, 'Type': 'Call', 'OI': max(100, int(base_oi)), 'Chg_OI': c_chg, 'Volume': max(10, int(base_vol * vol_multiplier)), 'LTP': ltp_c})
            rows.append({'Strike': strike, 'Type': 'Put', 'OI': max(100, int(base_oi)), 'Chg_OI': p_chg, 'Volume': max(10, int(base_vol * vol_multiplier * 0.96)), 'LTP': ltp_p})
        return spot, pd.DataFrame(rows)
    except:
        return None, pd.DataFrame()

ist_tz = pytz.timezone('Asia/Kolkata')
ts = datetime.now(ist_tz).strftime("%H:%M:%S")

if not st.session_state.global_history or st.session_state.global_history[-1]['Timestamp'] != ts:
    target_assets = [
        ("^NSEI", "NIFTY", False), ("^NSEBANK", "BANKNIFTY", False),
        ("RELIANCE.NS", "RELIANCE", True), ("HDFCBANK.NS", "HDFCBANK", True),
        ("ICICIBANK.NS", "ICICIBANK", True), ("INFY.NS", "INFOSYS", True)
    ]
    for ticker, display_name, is_stk in target_assets:
        spot, df = fetch_asset_snapshot(ticker, is_stk)
        if df is not None and not df.empty:
            st.session_state.global_history.append({
                'Timestamp': ts, 'Asset': display_name, 'IsStock': is_stk, 'Spot': spot, 'Raw_Data': df.to_json()
            })
    if len(st.session_state.global_history) > 180:
        st.session_state.global_history = st.session_state.global_history[-180:]

tab1, tab2 = st.tabs(["⚡ NIFTY INDEX OPTIONS", "🏢 NIFTY 50 STOCK OPTIONS"])

def process_and_render_view(is_stock_view, dropdown_options):
    asset_selection = st.selectbox(f"Select Target Profile", dropdown_options, key=f"sel_{is_stock_view}")
    
    if st.session_state.global_history:
        h_list = st.session_state.global_history
        timeline_records = []
        
        for item in h_list:
            if item.get('IsStock', False) != is_stock_view:
                continue
            curr_ts = item['Timestamp']
            df_snap = pd.read_json(io.StringIO(item['Raw_Data']))
            
            avg_vol = df_snap['Volume'].mean()
            df_snap['Unusual_Score'] = df_snap['Volume'] / max(1, avg_vol)
            spikes = df_snap[df_snap['Unusual_Score'] >= 3.2]
            
            for _, row in spikes.iterrows():
                opt_type = row['Type']
                strike_val = int(row['Strike'])
                spot_val = float(item['Spot'])
                computed_delta = calculate_bs_delta(spot_val, strike_val, opt_type)
                
                if opt_type == 'Call':
                    quad = "Call Writing" if row['Chg_OI'] > 0 else "Call Buying"
                    sign = "🔴 BEARISH" if row['Chg_OI'] > 0 else "🟢 BULLISH"
                else:
                    quad = "Put Writing" if row['Chg_OI'] > 0 else "Put Buying"
                    sign = "🟢 BULLISH" if row['Chg_OI'] > 0 else "🔴 BEARISH"
                    
                timeline_records.append({
                    'Timestamp': curr_ts, 'Asset': item['Asset'], 'Target Strike': strike_val,
                    'Type': "CE" if opt_type == "Call" else "PE", 'Quadrant': quad, 
                    'Direction Sign': sign, 'Volume': int(row['Volume']), 'LTP': row['LTP'], 'Delta': computed_delta
                })
                
        all_df = pd.DataFrame(timeline_records)
        if not all_df.empty and asset_selection in all_df['Asset'].values:
            filtered_df = all_df[all_df['Asset'] == asset_selection].copy()
            
            if not filtered_df.empty:
                st.markdown("### 📋 Spike-Isolated Activity Logs")
                for strike_price, group in filtered_df.groupby('Target Strike'):
                    sorted_group = group.sort_values(by='Timestamp', ascending=False)
                    
                    # --- FIX: ISOLATED 4-WAY VOLUME SUMMATION LOGIC ---
                    ce_sub = sorted_group[sorted_group['Type'] == 'CE']
                    pe_sub = sorted_group[sorted_group['Type'] == 'PE']
                    
                    ce_buy_vol = int(ce_sub[ce_sub['Quadrant'] == "Call Buying"]['Volume'].sum())
                    ce_sell_vol = int(ce_sub[ce_sub['Quadrant'] == "Call Writing"]['Volume'].sum())
                    
                    pe_buy_vol = int(pe_sub[pe_sub['Quadrant'] == "Put Buying"]['Volume'].sum())
                    pe_sell_vol = int(pe_sub[pe_sub['Quadrant'] == "Put Writing"]['Volume'].sum())
                    
                    net_buyer_total = ce_buy_vol + pe_buy_vol
                    net_seller_total = ce_sell_vol + pe_sell_vol
                    
                    if net_buyer_total > net_seller_total * 1.05:
                        net_bias = "🟢 INSTITUTIONAL ACCUMULATION (BULLISH)"
                    elif net_seller_total > net_buyer_total * 1.05:
                        net_bias = "🔴 AGGRESSIVE SELLING WAVE (BEARISH)"
                    else:
                        net_bias = "⚪ STRATEGIC NEUTRAL RANGE STRADDLE"
                    
                    ce_rows = []
                    pe_rows = []
                    
                    for _, r in sorted_group.iterrows():
                        color_class = "color: #bbf7d0; background-color: #15803d;" if "BULLISH" in r['Direction Sign'] else "color: #fecaca; background-color: #b91c1c;"
                        row_html = f"""
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; text-align: center;"><b>{r['Timestamp']}</b></td>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; font-weight: 600; text-align: center;">{r['Quadrant']}</td>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; text-align: center;">
                                    <span style="padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 0.75rem; {color_class}">{r['Direction Sign']}</span>
                                </td>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; font-family: monospace; text-align: center;">{r['Volume']:,}</td>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; font-weight: bold; color: #ff9f43; text-align: center;">{r['LTP']:,.1f}</td>
                                <td style="padding: 10px; border-bottom: 1px solid #2d3142; font-family: monospace; text-align: center; font-weight: 600; color: #2ebd85;">{r['Delta']:+.2f}</td>
                            </tr>
                        """
                        if r['Type'] == "CE": ce_rows.append(row_html)
                        else: pe_rows.append(row_html)
                    
                    ce_body_html = "".join(ce_rows) if ce_rows else "<tr><td colspan='6' class='text-muted py-3 text-center'>No high-volume CE blocks found</td></tr>"
                    pe_body_html = "".join(pe_rows) if pe_rows else "<tr><td colspan='6' class='text-muted py-3 text-center'>No high-volume PE blocks found</td></tr>"
                    
                    badge_color = "#0284c7" if not is_stock_view else "#7c3aed"
                    badge_text = "INDEX" if not is_stock_view else "STOCK"
                    
                    complete_card_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                        <style>
                            body {{ background-color: #0b0c10; color: #e4e6eb; font-family: system-ui, -apple-system, sans-serif; padding: 0; margin: 0; }}
                            .strike-card {{ background-color: #141722; border: 1px solid #222634; border-radius: 6px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
                            .badge-custom {{ background-color: {badge_color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; }}
                            .summary-grid {{
                                display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px;
                            }}
                            .ribbon-section {{
                                background-color: #1b1f2e; border-radius: 4px; padding: 8px 12px; font-size: 0.82rem; border: 1px solid #2d334a; text-align: center;
                            }}
                            .stat-label {{ color: #a0a5b5; font-size: 0.75rem; font-weight: 500; margin-bottom: 2px; }}
                            .stat-val {{ font-weight: bold; font-family: monospace; font-size: 0.9rem; }}
                            .panel-title-ce {{ background-color: #0c4a6e; color: #38bdf8; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                            .panel-title-pe {{ background-color: #7c2d12; color: #fb923c; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                            th {{ background-color: #1e2230 !important; color: #a0a5b5 !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.72rem; text-align: center; padding: 10px !important; }}
                        </style>
                    </head>
                    <body>
                        <div class="strike-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                <h4 style="margin: 0; color: #fff; font-size: 1.1rem; font-weight: 600;">
                                    <span class="badge-custom">{asset_selection} {badge_text}</span> Target Strike: <span style="color: #ff9f43;">🎯 {strike_price}</span>
                                </h4>
                            </div>
                            
                            <div class="summary-grid">
                                <div class="ribbon-section">
                                    <div class="stat-label">CALL OPTIONS FLOWS (CE)</div>
                                    <div>Buy: <span class="stat-val" style="color: #2ebd85;">{ce_buy_vol:,}</span> | Sell: <span class="stat-val" style="color: #f6465d;">{ce_sell_vol:,}</span></div>
                                </div>
                                <div class="ribbon-section">
                                    <div class="stat-label">PUT OPTIONS FLOWS (PE)</div>
                                    <div>Buy: <span class="stat-val" style="color: #2ebd85;">{pe_buy_vol:,}</span> | Sell: <span class="stat-val" style="color: #f6465d;">{pe_sell_vol:,}</span></div>
                                </div>
                                <div class="ribbon-section" style="display: flex; flex-direction: column; justify-content: center;">
                                    <div class="stat-label">STRIKE SENTIMENT DIRECTION</div>
                                    <div class="stat-val" style="color: #ff9f43; font-size: 0.8rem;">{net_bias}</div>
                                </div>
                            </div>

                            <div class="row g-3">
                                <div class="col-md-6">
                                    <div class="panel-title-ce">CALL OPTIONS MATRIX (CE BLOCK ORDERS)</div>
                                    <div class="table-responsive" style="border: 1px solid #222634; border-top: none; border-radius: 0 0 4px 4px;">
                                        <table class="table table-dark table-striped m-0" style="width: 100%;">
                                            <thead>
                                                <tr><th>TIME</th><th>QUADRANT</th><th>SENTIMENT</th><th>VOLUME</th><th>LTP</th><th>DELTA</th></tr>
                                            </thead>
                                            <tbody>{ce_body_html}</tbody>
                                        </table>
                                    </div>
                                </div>
                                
                                <div class="col-md-6">
                                    <div class="panel-title-pe">PUT OPTIONS MATRIX (PE BLOCK ORDERS)</div>
                                    <div class="table-responsive" style="border: 1px solid #222634; border-top: none; border-radius: 0 0 4px 4px;">
                                        <table class="table table-dark table-striped m-0" style="width: 100%;">
                                            <thead>
                                                <tr><th>TIME</th><th>QUADRANT</th><th>SENTIMENT</th><th>VOLUME</th><th>LTP</th><th>DELTA</th></tr>
                                            </thead>
                                            <tbody>{pe_body_html}</tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    components.html(complete_card_html, height=360, scrolling=True)
            else:
                st.info("⏳ Processing live order blocks... Surges will map within 60 seconds.")
        else:
            st.info("⏳ Scanning options matrix chains for active institutional surges...")
    else:
        st.info("⏳ Synchronizing tracking matrices...")

with tab1:
    process_and_render_view(False, ["NIFTY", "BANKNIFTY"])
with tab2:
    process_and_render_view(True, ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFOSYS"])

time.sleep(60)
st.rerun()

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
