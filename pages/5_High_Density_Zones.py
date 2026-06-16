import streamlit as st
import pandas as pd
import db_provider

st.set_page_config(page_title="High Density Zones", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .zone-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 16px; margin-bottom: 15px; }
    .zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .asset-name { font-size: 1.25rem; font-weight: bold; font-family: monospace; color: #ffffff; }
    .badge-pump { color: #2ebd85; border: 1px solid #2ebd85; padding: 3px 8px; border-radius: 4px; font-size: 0.72rem; }
    .badge-dump { color: #f6465d; border: 1px solid #f6465d; padding: 3px 8px; border-radius: 4px; font-size: 0.72rem; }
    .stat-box { background-color: #0b0c10; border: 1px solid #222634; padding: 6px; text-align: center; border-radius: 4px; }
    .stat-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; }
    .stat-val { font-size: 1.1rem; font-weight: bold; color: #ff9f43; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 High-Density Institutional Volume Zones")

# Keep the background ingestion active on this thread as well
db_provider.run_automated_generation_cycle()
df = db_provider.load_ledger_from_db()

if df.empty:
    st.info("⏳ Awaiting market data streams...")
else:
    for asset, group in df.groupby('asset'):
        recent = group.head(10)
        total_vol = int(recent['volume'].sum())
        strikes = recent['Target Strike'].unique()
        
        # Flash active alerts if volume clusters on a single strike range
        if len(strikes) <= 2 and total_vol > 50000:
            is_pump = "Call Buying" in recent['Quadrant'].values or "Put Writing" in recent['Quadrant'].values
            b_class = "badge-pump" if is_pump else "badge-dump"
            b_text = "🟢 PUMP FLIPS" if is_pump else "🔴 DUMP MATRIX"
            b_color = "#2ebd85" if is_pump else "#f6465d"
            
            st.markdown(f"""
            <div class='zone-card' style='border-left: 5px solid {b_color};'>
                <div class='zone-header'>
                    <div class='asset-name'>🔍 {asset} COMPLEX</div>
                    <span class='{b_class}'>{b_text}</span>
                </div>
                <div class='row g-2'>
                    <div class='col-4'><div class='stat-box'><div class='stat-lbl'>Volume</div><div class='stat-val'>{total_vol:,}</div></div></div>
                    <div class='col-4'><div class='stat-box'><div class='stat-lbl'>Strikes</div><div class='stat-val' style='color:#fff;'>{list(strikes)}</div></div></div>
                    <div class='col-4'><div class='stat-box'><div class='stat-lbl'>Last Scan</div><div class='stat-val' style='color:#a0a5b5;'>{recent['timestamp'].iloc[0]}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
