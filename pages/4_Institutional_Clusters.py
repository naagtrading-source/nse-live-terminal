import streamlit as st
import pandas as pd
import db_provider
import random

st.set_page_config(page_title="Institutional Clusters", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .cluster-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .c-header { font-size: 1.3rem; font-weight: bold; font-family: monospace; color: #fff; display: flex; justify-content: space-between; align-items: center; }
    .action-badge-long { background-color: rgba(46, 189, 133, 0.12); color: #2ebd85; border: 1px solid #2ebd85; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .action-badge-short { background-color: rgba(246, 70, 93, 0.12); color: #f6465d; border: 1px solid #f6465d; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .box-grid { background-color: #0b0c10; border: 1px solid #222634; padding: 12px; text-align: center; border-radius: 4px; }
    .box-lbl { font-size: 0.7rem; color: #a0a5b5; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px; }
    .box-val { font-size: 1.3rem; font-weight: bold; font-family: monospace; margin-top: 3px; }
    .strategy-note { background: #1f2231; padding: 10px 15px; border-radius: 4px; border-left: 4px solid #ff9f43; font-size: 0.9rem; margin: 15px 0; color: #e4e6eb; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Institutional High-Density Volume Clusters")
st.caption("Value Area Accumulation Scanners | Isolating Symmetrical Smart Money Entry Walls")

# Run background loop synchronization
db_provider.run_automated_generation_cycle()
df = db_provider.load_ledger_from_db()

if df.empty:
    st.info("⏳ Synchronizing options value area matrices... Run the main cockpit tab to start streaming data.")
else:
    st.write("### 🚨 Live Institutional Value Area Formations")
    
    for asset, group in df.groupby('asset'):
        recent = group.head(15)
        total_vol = int(recent['volume'].sum())
        
        # Cleanly extract raw integers to fix the data type presentation bug
        strikes = sorted([int(x) for x in recent['Target Strike'].unique()])
        
        # If institutional volume is heavily loading into 1 or 2 specific strike targets
        if len(strikes) <= 2 and total_vol > 50000:
            is_long_accumulation = "Call Buying" in recent['Quadrant'].values or "Put Writing" in recent['Quadrant'].values
            
            opt_ltp = float(recent['ltp'].iloc[0])
            wall_price = round(opt_ltp, 1)
            
            if is_long_accumulation:
                card_border = "#2ebd85"
                badge_html = "<span class='action-badge-long'>🟢 ELITE ACCUMULATION (PUMP FLOOR)</span>"
                strategy = f"<b>Trade Plan:</b> Institutions are building a massive buy wall at Strike <b>{strikes[0]}</b>. Do not chase the market. Set a limit buy order right at the <b>Retest Entry Line ({wall_price})</b>. If the premium breaks below the stop loss line, close the trade immediately."
                stop_loss = round(wall_price * 0.85, 1)
                target = round(wall_price * 1.35, 1)
            else:
                card_border = "#f6465d"
                badge_html = "<span class='action-badge-short'>🔴 ELITE DISTRIBUTION (SUPPLY CEILING)</span>"
                strategy = f"<b>Trade Plan:</b> Institutions are blocking the upside at Strike <b>{strikes[0]}</b> by heavily selling calls or buying puts. Look for short entries or protect existing longs. The <b>Short Entry Line is {wall_price}</b> with an invalidation stop loss right above it."
                stop_loss = round(wall_price * 1.15, 1)
                target = round(wall_price * 0.60, 1)

            st.markdown(f"""
            <div class='cluster-card' style='border-left: 5px solid {card_border};'>
                <div class='c-header'>
                    <div>🎯 {asset} ORDER WALL</div>
                    {badge_html}
                </div>
                <div class='strategy-note'>{strategy}</div>
                <div class='row g-2'>
                    <div class='col-md-3'><div class='box-grid'><div class='box-lbl'>Institutional Strike Wall</div><div class='box-val' style='color:#fff;'>{strikes[0]}</div></div></div>
                    <div class='col-md-3'><div class='box-grid' style='border-color:{card_border};'><div class='box-lbl' style='color:{card_border}; font-weight:700;'>Retest Entry Line</div><div class='box-val' style='color:#fff;'>{wall_price}</div></div></div>
                    <div class='col-md-3'><div class='box-grid'><div class='box-lbl'>Defensive Stop Loss</div><div class='box-val' style='color:#f6465d;'>{stop_loss}</div></div></div>
                    <div class='col-md-3'><div class='box-grid'><div class='box-lbl'>Take Profit Target</div><div class='box-val' style='color:#2ebd85;'>{target}</div></div></div>
                </div>
                <p style='font-size:0.72rem; color:#666; margin:10px 0 0 0; text-align:right;'>Total Consolidated Position Size: {total_vol:,} lots | Block Capture Time: {recent['timestamp'].iloc[0]}</p>
            </div>
            """, unsafe_allow_html=True)
