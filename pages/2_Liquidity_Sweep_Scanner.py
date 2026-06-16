import streamlit as st
import pandas as pd
import db_provider

st.set_page_config(page_title="Liquidity Sweep Scanner", layout="wide", page_icon="💥")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .sweep-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 14px; margin-bottom: 12px; }
    .sweep-title { font-size: 1.05rem; font-weight: bold; font-family: monospace; }
    .metric-grid { background-color: #0b0c10; border: 1px solid #1b1f2e; border-radius: 4px; padding: 6px; text-align: center; }
    .m-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; }
    .m-val { font-size: 1.1rem; font-weight: bold; font-family: monospace; color: #fff; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("💥 Institutional Liquidity Sweep Scanner")
st.caption("Advanced Order Flow Trapping Index | Pinpointing Stop-Loss Hunting Turning Zones")

# Run the automated background engine process loop on this thread
db_provider.run_automated_generation_cycle()
df = db_provider.load_ledger_from_db()

if df.empty:
    st.info("⏳ Synchronizing deep order flow tracking matrices...")
else:
    st.write("### 🚨 Detected Active Liquidity Sweeps")
    
    # Filter for massive blocks relative to their asset class thresholds
    sweeps = df[(df['volume'] > 1350000) | ((df['market_type'] == 'COMMODITY') & (df['volume'] > 42000))].copy()
    
    if not sweeps.empty:
        # Drop duplicates to keep the layout perfectly clean
        sweeps = sweeps.drop_duplicates(subset=['timestamp', 'asset', 'strike', 'volume']).head(10)
        
        for _, r in sweeps.iterrows():
            is_bullish = "Buying" in r['Quadrant'] or "PUMP" in r['direction']
            border_color = "#2ebd85" if is_bullish else "#f6465d"
            text_color = "#2ebd85" if is_bullish else "#f6465d"
            action_type = "RETAIL SHORTS TRAPPED (BULLISH REVERSAL)" if is_bullish else "RETAIL LONGS TRAPPED (BEARISH REVERSAL)"
            
            st.markdown(f"""
            <div class='sweep-card' style='border-left: 5px solid {border_color};'>
                <div class='d-flex justify-content-between align-items-center mb-2'>
                    <span class='sweep-title' style='color:{text_color};'>⚡ {r['asset']} SWEEP NODE</span>
                    <span style='font-size:0.72rem; background:#1b1f2e; border:1px solid #2d334a; padding:2px 6px; border-radius:4px; font-weight:bold; color:#ff9f43;'>{action_type}</span>
                </div>
                <p style='font-size:0.82rem; color:#a0a5b5; margin-bottom:10px;'>
                    Extreme volume block detected out-of-bounds at strike <b>{r['Target Strike']}</b>. Institutions cleared out retail stops before price reversal.
                </p>
                <div class='row g-2'>
                    <div class='col-3'><div class='metric-grid'><div class='m-lbl'>Sweep Volume</div><div class='m-val' style='color:#ff9f43;'>{r['volume']:,}</div></div></div>
                    <div class='col-3'><div class='metric-grid'><div class='m-lbl'>Execution LTP</div><div class='m-val'>{r['ltp']}</div></div></div>
                    <div class='col-3'><div class='metric-grid'><div class='m-lbl'>Options Type</div><div class='m-val' style='color:#ff9f43;'>{r['type']}</div></div></div>
                    <div class='col-3'><div class='metric-grid'><div class='m-lbl'>Timestamp</div><div class='m-val' style='color:#a0a5b5;'>{r['timestamp']}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("🎯 Scanning market levels... No out-of-bounds retail stop hunting signatures found.")
