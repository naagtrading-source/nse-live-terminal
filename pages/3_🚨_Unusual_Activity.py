import streamlit as st
import pandas as pd
import json
import io
import time
from datetime import datetime

st.set_page_config(page_title="Unusual Volume Activity", layout="wide")

# Modern, structured presentation styling injection
st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .strike-card {
        background-color: #12141d;
        border: 1px solid #1f222e;
        border-left: 5px solid #ff9f43;
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .stTable, table { width: 100% !important; text-align: center !important; margin-bottom: 0px !important; }
    th { background-color: #1a1d28 !important; color: #a0a5b3 !important; font-weight: bold !important; text-align: center !important; font-size: 0.8rem !important; }
    td { text-align: center !important; font-size: 0.9rem !important; padding: 10px !important; }
    .badge-nifty { background-color: #0284c7; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    .badge-bank { background-color: #dc2626; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Unusual Institutional Volatility Spikes")
st.caption("Intraday Multi-Line Strike Tracker & Grouped Block Activity Logs")

if 'global_history' not in st.session_state:
    st.session_state.global_history = []

asset_filter = st.selectbox("Select Target Asset Index", ["NIFTY", "BANKNIFTY"])

if st.session_state.global_history:
    h_list = st.session_state.global_history
    timeline_records = []
    
    # Process historical memory cache blocks
    for item in h_list:
        curr_ts = item['Timestamp']
        df_snap = pd.read_json(io.StringIO(item['Raw_Data']))
        
        avg_vol = df_snap['Volume'].mean()
        df_snap['Unusual_Score'] = df_snap['Volume'] / avg_vol
        
        # CRITICAL FILTER: Raised from 2.2 to 3.5 to screen out noise and capture ONLY massive volume block anomalies
        spikes = df_snap[df_snap['Unusual_Score'] >= 3.5]
        
        for _, row in spikes.iterrows():
            quad = f"{row['Type']} Writing" if row['Chg_OI'] > 0 else f"{row['Type']} Buying"
            timeline_records.append({
                'Timestamp': curr_ts,
                'Asset': item['Asset'],
                'Target Strike': int(row['Strike']),
                'Quadrant': quad,
                'Volume': int(row['Volume']),
                'LTP': row['LTP']
            })
            
    all_unusual_df = pd.DataFrame(timeline_records)
    
    if not all_unusual_df.empty:
        asset_unusual_df = all_unusual_df[all_unusual_df['Asset'] == asset_filter].copy()
        
        if not asset_unusual_df.empty:
            # --- SECTION 1: INTRADAY TIME-SERIES VOLUME GRAPH ---
            st.markdown(f"### 📈 {asset_filter} Intraday Strike Volume Multi-Line Wave")
            
            timestamps = sorted(asset_unusual_df['Timestamp'].unique())
            top_strikes = asset_unusual_df.groupby('Target Strike')['Volume'].sum().nlargest(4).index.tolist()
            
            chart_data = {'Timeline': timestamps}
            for strike in top_strikes:
                strike_series = []
                for t in timestamps:
                    match = asset_unusual_df[(asset_unusual_df['Timestamp'] == t) & (asset_unusual_df['Target Strike'] == strike)]
                    strike_series.append(int(match['Volume'].iloc[-1]) if not match.empty else None)
                chart_data[f"Strike {strike}"] = strike_series
                
            chart_df = pd.DataFrame(chart_data).ffill().fillna(0)
            st.line_chart(chart_df, x='Timeline', y=[f"Strike {s}" for s in top_strikes])
            
            # --- SECTION 2: CRISP SEPARATED STRIKE CARDS ---
            st.markdown("### 📋 Strike-Specific Isolated Institutional Logs")
            
            # Group records cleanly by their target strike price
            grouped_strikes = asset_unusual_df.groupby('Target Strike')
            
            for strike_price, group_data in sorted(grouped_strikes, key=lambda x: x[0]):
                # Sort group internally so that the newest timestamp is positioned directly at the top
                sorted_group = group_data.sort_values(by='Timestamp', ascending=False)
                
                # Format clean visual table parameters
                display_df = sorted_group[['Timestamp', 'Quadrant', 'Volume', 'LTP']].copy()
                display_df['Volume'] = display_df['Volume'].map('{:,}'.format)
                display_df['LTP'] = display_df['LTP'].map('{:,.1f}'.format)
                display_df.columns = ['TIMESTAMP', 'FLOW DIRECTION (QUADRANT)', 'ACCUMULATED VOLUME', 'LAST TRADED PRICE (LTP)']
                
                badge_html = f"<span class='badge-nifty'>NIFTY</span>" if asset_filter == "NIFTY" else f"<span class='badge-bank'>BANKNIFTY</span>"
                
                # Generate clean HTML block containers for each contract strike
                st.markdown(f"""
                    <div class="strike-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <h4 style="margin: 0; color: #fff; font-size: 1.1rem;">
                                {badge_html} Target Contract Strike Price: <span style="color: #ff9f43;">🎯 {strike_price}</span>
                            </h4>
                            <span style="color: #a0a5b3; font-size: 0.8rem; font-weight: bold; background-color: #1b1e29; padding: 4px 10px; border-radius: 20px;">Institutional Wave Block</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Render table immediately underneath the custom header card box
                st.table(display_df)
                st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.info("⏳ Processing live order blocks... Massive surges will map shortly.")
    else:
        st.info("⏳ Waiting for initial massive option block activity to clear filter criteria...")
else:
    st.info("⏳ Synchronizing tracking matrices. Streaming active shortly...")

# Auto-refresh loop sync handler (60 seconds)
time.sleep(60)
st.rerun()

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
