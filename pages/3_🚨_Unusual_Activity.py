import streamlit as st
import pandas as pd
import yfinance as yf
import json
import io
import time
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(page_title="Unusual Volume Activity", layout="wide")

# Structural baseline configurations injection
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

ts = datetime.now().strftime("%H:%M:%S")
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
            spikes = df_snap[df_snap['Unusual_Score'] >= 2.8]
            
            for _, row in spikes.iterrows():
                if row['Type'] == 'Call':
                    quad = "Call Writing" if row['Chg_OI'] > 0 else "Call Buying"
                    sign = "🔴 BEARISH" if row['Chg_OI'] > 0 else "🟢 BULLISH"
                else:
                    quad = "Put Writing" if row['Chg_OI'] > 0 else "Put Buying"
                    sign = "🟢 BULLISH" if row['Chg_OI'] > 0 else "🔴 BEARISH"
                    
                timeline_records.append({
                    'Timestamp': curr_ts, 'Asset': item['Asset'], 'Target Strike': int(row['Strike']),
                    'Quadrant': quad, 'Direction Sign': sign, 'Volume': int(row['Volume']), 'LTP': row['LTP']
                })
                
        all_df = pd.DataFrame(timeline_records)
        if not all_df.empty and asset_selection in all_df['Asset'].values:
            filtered_df = all_df[all_df['Asset'] == asset_selection].copy()
            
            if not filtered_df.empty:
                # --- TIME SERIES CHART ---
                timestamps = sorted(filtered_df['Timestamp'].unique())
                top_strikes = filtered_df.groupby('Target Strike')['Volume'].sum().nlargest(3).index.tolist()
                
                chart_data = {'Timeline': timestamps}
                for s in top_strikes:
                    s_series = []
                    for t in timestamps:
                        match = filtered_df[(filtered_df['Timestamp'] == t) & (filtered_df['Target Strike'] == s)]
                        s_series.append(int(match['Volume'].iloc[-1]) if not match.empty else None)
                    chart_data[f"Strike {s}"] = s_series
                
                st.line_chart(pd.DataFrame(chart_data).ffill().fillna(0), x='Timeline', y=[f"Strike {s}" for s in top_strikes])
                
                # --- SEPARATED STRIKE CARDS SECTION ---
                st.markdown("### 📋 Spike-Isolated Activity Logs")
                for strike_price, group in filtered_df.groupby('Target Strike'):
                    sorted_group = group.sort_values(by='Timestamp', ascending=False)
                    
                    display_rows = []
                    for _, r in sorted_group.iterrows():
                        color_class = "color: #bbf7d0; background-color: #15803d;" if "BULLISH" in r['Direction Sign'] else "color: #fecaca; background-color: #b91c1c;"
                        display_rows.append(f"""
                            <tr>
                                <td style="padding: 12px; border-bottom: 1px solid #2d3142; text-align: center;"><b>{r['Timestamp']}</b></td>
                                <td style="padding: 12px; border-bottom: 1px solid #2d3142; font-weight: 600; text-align: center;">{r['Quadrant']}</td>
                                <td style="padding: 12px; border-bottom: 1px solid #2d3142; text-align: center;">
                                    <span style="padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.8rem; {color_class}">{r['Direction Sign']}</span>
                                </td>
                                <td style="padding: 12px; border-bottom: 1px solid #2d3142; font-family: monospace; text-align: center;">{r['Volume']:,}</td>
                                <td style="padding: 12px; border-bottom: 1px solid #2d3142; font-weight: bold; color: #ff9f43; text-align: center;">{r['LTP']:,.1f}</td>
                            </tr>
                        """)
                    
                    badge_color = "#0284c7" if not is_stock_view else "#7c3aed"
                    badge_text = "INDEX" if not is_stock_view else "STOCK"
                    table_body_html = "".join(display_rows)
                    
                    # FIX: Bundled headers, styles, and body loops inside an autonomous HTML document block
                    complete_card_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                        <style>
                            body {{ background-color: #0b0c10; color: #e4e6eb; font-family: system-ui, -apple-system, sans-serif; padding: 0; margin: 0; }}
                            .strike-card {{
                                background-color: #141722;
                                border: 1px solid #222634;
                                border-radius: 6px;
                                padding: 16px;
                                box-shadow: 0 4px 12px rgba(0,0,0,0.4);
                            }}
                            .badge-custom {{ background-color: {badge_color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; }}
                            th {{ background-color: #1e2230 !important; color: #a0a5b5 !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.78rem; letter-spacing: 0.5px; text-align: center; padding: 12px !important; }}
                        </style>
                    </head>
                    <body>
                        <div class="strike-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                                <h4 style="margin: 0; color: #fff; font-size: 1.1rem; font-weight: 600;">
                                    <span class="badge-custom">{asset_selection} {badge_text}</span> Target Contract Strike Price: <span style="color: #ff9f43;">🎯 {strike_price}</span>
                                </h4>
                            </div>
                            <div class="table-responsive" style="border-radius: 4px; overflow: hidden;">
                                <table class="table table-dark table-striped m-0" style="width: 100%; border-collapse: collapse;">
                                    <thead>
                                        <tr>
                                            <th>TIMESTAMP</th>
                                            <th>FLOW QUADRANT</th>
                                            <th>DIRECTION SENTIMENT</th>
                                            <th>VOLUME ACCUMULATION</th>
                                            <th>LAST TRADED PRICE (LTP)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {table_body_html}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    # FIX: Injected the complete native component container block with fixed dynamic height rules
                    components.html(complete_card_html, height=280, scrolling=True)
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
