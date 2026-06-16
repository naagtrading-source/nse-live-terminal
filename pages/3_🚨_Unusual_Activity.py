import streamlit as st
import pandas as pd
import json
import io
import math
import streamlit.components.v1 as components

st.set_page_config(page_title="Unusual Volume Activity", layout="wide")

# FIX: Injected identical browser auto-refresh tag here to prevent cloud thread hangs
st.markdown("""
    <head>
        <meta http-equiv="refresh" content="60">
    </head>
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .strike-card-container { margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Anomalies")
st.caption("Real-Time Multi-Asset Block Activity Monitors | Index & Stock Option Scanners")

def get_expiry_dates_local():
    import pytz
    from datetime import datetime, timedelta
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    days_to_thursday = (3 - today.weekday()) % 7
    curr_wk = today + timedelta(days=days_to_thursday)
    next_wk = curr_wk + timedelta(days=7)
    nxt_month = curr_wk.replace(day=28) + timedelta(days=5)
    last_day = nxt_month - timedelta(days=nxt_month.day)
    monthly = last_day - timedelta(days=(last_day.weekday() - 3) % 7)
    if monthly < today:
        nxt_month_alt = last_day + timedelta(days=5)
        last_day_alt = nxt_month_alt + timedelta(days=25)
        monthly = last_day_alt - timedelta(days=(last_day_alt.weekday() - 3) % 7)
    return {
        "current": f"Current Week ({curr_wk.strftime('%d-%b')})",
        "next": f"Next Week ({next_wk.strftime('%d-%b')})",
        "monthly": f"Monthly Expiry ({monthly.strftime('%d-%b')})"
    }

def calculate_bs_delta(spot, strike, option_type):
    try:
        t = 30 / 365; v = 0.12; r = 0.05
        d1 = (math.log(spot / strike) + (r + 0.5 * v ** 2) * t) / (v * math.sqrt(t))
        def cnd(x):
            a1, a2, a3 = 0.31938153, -0.356563782, 1.781477937
            m = 1.0 / (1.0 + 0.2316419 * abs(x))
            return 1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3) if x >= 0 else 1.0 - (1.0 - 1.0 / math.sqrt(2 * math.pi) * math.exp(-x * x / 2.0) * (a1*m + a2*m**2 + a3*m**3))
        return round(cnd(d1), 2) if option_type == 'Call' else round(cnd(d1) - 1.0, 2)
    except: return 0.50 if option_type == 'Call' else -0.50

tab1, tab2 = st.tabs(["⚡ NIFTY INDEX OPTIONS", "🏢 NIFTY 50 STOCK OPTIONS"])

def process_and_render_view(is_stock_view, dropdown_options):
    expiry_map = get_expiry_dates_local()
    
    if not is_stock_view:
        c1, c2 = st.columns(2)
        with c1:
            asset_selection = st.selectbox("Select Target Profile", dropdown_options, key=f"as_{is_stock_view}")
        with c2:
            selected_expiry = st.selectbox("Select Expiry Series", [expiry_map["current"], expiry_map["next"], expiry_map["monthly"]], key=f"ex_{is_stock_view}")
    else:
        asset_selection = st.selectbox("Select Target Profile", dropdown_options, key=f"as_{is_stock_view}")
        selected_expiry = expiry_map["monthly"]
        st.write(f"Locked Contract Expiry Cycle: **{selected_expiry}**")
    
    if 'global_history' in st.session_state and st.session_state.global_history:
        h_list = st.session_state.global_history
        timeline_records = []
        
        for item in h_list:
            item_asset_upper = str(item['Asset']).upper().strip()
            asset_selection_upper = str(asset_selection).upper().strip()
            item_is_stock = item.get('IsStock', False) or (item_asset_upper not in ["NIFTY", "BANKNIFTY"])
            
            if item_is_stock != is_stock_view: continue
            if not is_stock_view and item.get('Expiry') != selected_expiry: continue
            if item_asset_upper != asset_selection_upper: continue
                
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
                
                quad = ("Call Writing" if row['Chg_OI'] > 0 else "Call Buying") if opt_type == 'Call' else ("Put Writing" if row['Chg_OI'] > 0 else "Put Buying")
                sign = ("🔴 BEARISH" if row['Chg_OI'] > 0 else "🟢 BULLISH") if opt_type == 'Call' else ("🟢 BULLISH" if row['Chg_OI'] > 0 else "🔴 BEARISH")
                    
                timeline_records.append({
                    'Timestamp': curr_ts, 'Asset': item['Asset'], 'Target Strike': strike_val,
                    'Type': "CE" if opt_type == "Call" else "PE", 'Quadrant': quad, 
                    'Direction Sign': sign, 'Volume': int(row['Volume']), 'LTP': row['LTP'], 'Delta': computed_delta
                })
                
        if timeline_records:
            all_df = pd.DataFrame(timeline_records)
            filtered_df = all_df[all_df['Asset'].str.upper() == asset_selection_upper].copy()
            
            if not filtered_df.empty:
                st.markdown("### 📋 Spike-Isolated Activity Logs")
                for strike_price, group in filtered_df.groupby('Target Strike'):
                    sorted_group = group.sort_values(by='Timestamp', ascending=False)
                    
                    ce_sub = sorted_group[sorted_group['Type'] == 'CE']
                    pe_sub = sorted_group[sorted_group['Type'] == 'PE']
                    ce_buy_vol = int(ce_sub[ce_sub['Quadrant'] == "Call Buying"]['Volume'].sum())
                    ce_sell_vol = int(ce_sub[ce_sub['Quadrant'] == "Call Writing"]['Volume'].sum())
                    pe_buy_vol = int(pe_sub[pe_sub['Quadrant'] == "Put Buying"]['Volume'].sum())
                    pe_sell_vol = int(pe_sub[pe_sub['Quadrant'] == "Put Writing"]['Volume'].sum())
                    
                    net_buyer_total = ce_buy_vol + pe_buy_vol
                    net_seller_total = ce_sell_vol + pe_sell_vol
                    net_bias = " Institutional Accumulation (Bullish)" if net_buyer_total > net_seller_total * 1.05 else " Aggressive Selling Wave (Bearish)"
                    
                    ce_rows = []; pe_rows = []
                    for _, r in sorted_group.iterrows():
                        color_class = "color: #bbf7d0; background-color: #15803d;" if "BULLISH" in r['Direction Sign'] else "color: #fecaca; background-color: #b91c1c;"
                        row_html = f"<tr><td><b>{r['Timestamp']}</b></td><td>{r['Quadrant']}</td><td><span style='padding:3px 8px; border-radius:12px; font-weight:bold; font-size:0.75rem; {color_class}'>{r['Direction Sign']}</span></td><td>{r['Volume']:,}</td><td style='color:#ff9f43; font-weight:bold;'>{r['LTP']:,.1f}</td><td style='color:#2ebd85;'>{r['Delta']:+.2f}</td></tr>"
                        if r['Type'] == "CE": ce_rows.append(row_html)
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
                            .strike-card {{ background-color: #141722; border: 1px solid #222634; border-radius: 6px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
                            .summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }}
                            .ribbon-section {{ background-color: #1b1f2e; border-radius: 4px; padding: 8px 12px; font-size: 0.82rem; border: 1px solid #2d334a; text-align: center; }}
                            .stat-label {{ color: #a0a5b5; font-size: 0.75rem; font-weight: 500; }}
                            .stat-val {{ font-weight: bold; font-family: monospace; }}
                            .panel-title-ce {{ background-color: #0c4a6e; color: #38bdf8; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                            .panel-title-pe {{ background-color: #7c2d12; color: #fb923c; padding: 6px; font-size: 0.82rem; font-weight: bold; text-align: center; border-radius: 4px 4px 0 0; margin: 0; }}
                            th {{ background-color: #1e2230 !important; color: #a0a5b5 !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.72rem; text-align: center; }}
                        </style>
                    </head>
                    <body>
                        <div class="strike-card">
                            <h4 style="color:#fff; font-size:1.1rem; margin-bottom:12px;">🎯 Target Strike: <span style="color:#ff9f43;">{strike_price}</span> [{selected_expiry}]</h4>
                            <div class="summary-grid">
                                <div class="ribbon-section"><div class="stat-label">CALL OPTIONS FLOWS (CE)</div><div>Buy: <span class="stat-val" style="color:#2ebd85;">{ce_buy_vol:,}</span> | Sell: <span class="stat-val" style="color:#f6465d;">{ce_sell_vol:,}</span></div></div>
                                <div class="ribbon-section"><div class="stat-label">PUT OPTIONS FLOWS (PE)</div><div>Buy: <span class="stat-val" style="color:#2ebd85;">{pe_buy_vol:,}</span> | Sell: <span class="stat-val" style="color:#f6465d;">{pe_sell_vol:,}</span></div></div>
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
                    components.html(complete_card_html, height=360, scrolling=True)
            else:
                st.info("⏳ Processing data loop matrices. Block rows map within 60s...")
        else:
            st.info("⏳ Tracking options arrays for anomalies... Updates populate shortly.")
    else:
        st.info("⏳ Synchronizing tracking matrices...")
with tab1:
    process_and_render_view(False, ["NIFTY", "BANKNIFTY"])
with tab2:
    process_and_render_view(True, ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFOSYS"])
