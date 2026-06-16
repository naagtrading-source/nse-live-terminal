import streamlit as st
import pandas as pd
import db_provider

st.set_page_config(page_title="Institutional Clusters", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .cluster-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 15px; margin-bottom: 12px; }
    .c-header { font-size: 1.1rem; font-weight: bold; font-family: monospace; color: #fff; display: flex; justify-content: space-between; }
    .num-box { background-color: #0b0c10; border: 1px solid #1b1f2e; padding: 6px; border-radius: 4px; text-align: center; }
    .num-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; }
    .num-val { font-size: 1.15rem; font-weight: bold; font-family: monospace; color: #ff9f43; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Institutional High-Density Volume Clusters")
st.caption("Micro-Range Liquidity Concentration Scanners | Identifying Symmetrical Accumulation Channels")

db_provider.run_automated_generation_cycle()
df = db_provider.load_ledger_from_db()

if df.empty:
    st.info("⏳ Synchronizing deep liquidity matrix layers...")
else:
    cluster_found = False
    for asset, group in df.groupby('asset'):
        recent = group.head(20)
        strikes = recent['Target Strike'].unique()
        
        # Flag structural absorption nodes if multiple blocks target a single strike
        if len(strikes) <= 2:
            cluster_found = True
            total_vol = int(recent['volume'].sum())
            is_pump = "Call Buying" in recent['Quadrant'].values or "Put Writing" in recent['Quadrant'].values
            
            b_color = "#2ebd85" if is_pump else "#f6465d"
            b_tag = "⚡ HIGH-DENSITY ACCUMULATION NODE (PUMP)" if is_pump else "⚠️ HIGH-DENSITY DISTRIBUTION NODE (DUMP)"
            b_desc = "Institutions are absorbing orders within a tight bracket, setting up a structural market launchpad." if is_pump else "Institutions are aggressively distributing inventory, creating a firm overhead resistance wall."
            
            st.markdown(f"""
            <div class='cluster-card' style='border-left: 5px solid {b_color};'>
                <div class='c-header'><div>🎯 {asset} Cluster Node</div><span style='font-size:0.75rem; color:{b_color}; font-weight:bold; letter-spacing:0.5px;'>{b_tag}</span></div>
                <p style='font-size:0.82rem; color:#e4e6eb; margin:6px 0 12px 0;'>{b_desc} Targeted Ranges: <b>{list(strikes)}</b></p>
                <div class='row g-2 text-center'>
                    <div class='col-4'><div class='num-box'><div class='num-lbl'>Aggregated Volume</div><div class='num-val'>{total_vol:,} lots</div></div></div>
                    <div class='col-4'><div class='num-box'><div class='num-lbl'>Mean Premium</div><div class='num-val' style='color:#fff;'>{round(recent['ltp'].mean(),1)}</div></div></div>
                    <div class='col-4'><div class='num-box'><div class='num-lbl'>Last Scan Update</div><div class='num-val' style='color:#a0a5b5; font-size:1rem; margin-top:5px;'>{recent['timestamp'].iloc[0]}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    if not cluster_found:
        st.info("🎯 Options liquidity is currently distributed normally. Scanning depth profiles for volume anomalies...")
