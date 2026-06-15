import streamlit as st
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title="Unusual Volume Activity", layout="wide")

st.title("🚨 Unusual Institutional Volatility Spikes")
st.caption("Intraday Multi-Line Strike Tracker & Real-Time Block Activity Log")

asset_filter = st.selectbox("Select Target Asset Index", ["NIFTY", "BANKNIFTY"])

# Safe execution block layout matching the multi-series line chart mechanics
if 'global_history' in st.session_state and st.session_state.global_history:
    h_list = st.session_state.global_history
    
    # 1. Gather historical anomalies dynamically from memory blocks
    timeline_records = []
    
    for item in h_list:
        ts = item['Timestamp']
        # Load raw data snapshot frame back to parse options parameters row by row
        df_snap = pd.read_json(item['Raw_Data'])
        
        # Identify options running at unusual contract volume multipliers
        avg_vol = df_snap['Volume'].mean()
        df_snap['Unusual_Score'] = df_snap['Volume'] / avg_vol
        spikes = df_snap[df_snap['Unusual_Score'] >= 2.2]
        
        for _, row in spikes.iterrows():
            quad = f"{row['Type']} Writing" if row['Chg_OI'] > 0 else f"{row['Type']} Buying"
            timeline_records.append({
                'Timestamp': ts,
                'Asset': item['Asset'],
                'Target Strike': int(row['Strike']),
                'Quadrant': quad,
                'Volume': int(row['Volume']),
                'LTP': row['LTP']
            })
            
    all_unusual_df = pd.DataFrame(timeline_records)
    
    if not all_unusual_df.empty:
        # Filter strictly for the currently selected asset layout row
        asset_unusual_df = all_unusual_df[all_unusual_df['Asset'] == asset_filter].copy()
        
        if not asset_unusual_df.empty:
            # --- SECTION 1: INTRADAY MULTI-LINE TIME-SERIES CHART ---
            st.markdown(f"### 📈 {asset_filter} Intraday Strike Volume Multi-Line Wave")
            
            # Map out unique timestamps and top 4 active unusual strikes to draw lines for
            timestamps = sorted(asset_unusual_df['Timestamp'].unique())
            top_strikes = asset_unusual_df.groupby('Target Strike')['Volume'].sum().nlargest(4).index.tolist()
            
            # Structure timeline vectors cleanly for chart processing matrix formats
            chart_data = {'Timeline': timestamps}
            for strike in top_strikes:
                strike_series = []
                for ts in timestamps:
                    match = asset_unusual_df[(asset_unusual_df['Timestamp'] == ts) & (asset_unusual_df['Target Strike'] == strike)]
                    strike_series.append(int(match['Volume'].iloc[-1]) if not match.empty else 0)
                chart_data[f"Strike {strike}"] = strike_series
                
            chart_df = pd.DataFrame(chart_data)
            st.line_chart(chart_df, x='Timeline', y=[f"Strike {s}" for s in top_strikes])
            
            # --- SECTION 2: LIVE BLOCK LOG TABLE ---
            st.markdown("### 📋 Real-Time Activity Log (Latest Spikes on Top)")
            # Reverse chart row outputs so the newest timestamps stay at the top section natively
            display_log_df = asset_unusual_df[['Timestamp', 'Asset', 'Target Strike', 'Quadrant', 'Volume', 'LTP']].copy()
            st.table(display_log_df.sort_values(by='Timestamp', ascending=False))
        else:
            st.info("⏳ Scanning open positions... Tracking chart streams active shortly.")
    else:
        st.info("⏳ Waiting for initial unusual option block activity anomalies to flag...")
else:
    st.info("⏳ Synchronizing tracking matrices. Streaming options volume logs active shortly...")

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
