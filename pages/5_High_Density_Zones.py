import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="High Density Zones Scanners", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .zone-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 16px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #2d334a; padding-bottom: 8px; }
    .asset-name { font-size: 1.25rem; font-weight: bold; font-family: monospace; color: #ffffff; }
    .badge-pump { background-color: rgba(46, 189, 133, 0.12); color: #2ebd85; border: 1px solid #2ebd85; padding: 3px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: bold; text-transform: uppercase; }
    .badge-dump { background-color: rgba(246, 70, 93, 0.12); color: #f6465d; border: 1px solid #f6465d; padding: 3px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: bold; text-transform: uppercase; }
    .stat-container { background-color: #0b0c10; border: 1px solid #1b1f2e; border-radius: 4px; padding: 8px; text-align: center; }
    .stat-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; }
    .stat-val { font-size: 1.2rem; font-weight: bold; font-family: monospace; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 High-Density Institutional Volume Zones")
st.caption("Real-Time Price Range Absorption Engine | Pinpointing Massive Pump & Dump Blocks")

DB_FILE = "terminal_history.db"

def load_historical_ledger():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.fragment(run_every=15)
def scan_and_render_density_nodes():
    df = load_historical_ledger()
    if df.empty:
        st.info("⏳ Synchronizing deep order flow tracking matrices... Keep your main app page open to stream active ticks.")
        return

    st.write("### 🚨 Active Institutional Absorption Zones")
    
    # Process assets to check for heavy volume loading inside narrow strike brackets
    grouped = df.groupby('asset')
    zones_detected = 0
    
    for asset, group in grouped:
        # Evaluate recent blocks per asset channel
        recent_window = group.head(25)
        if recent_window.empty: continue
        
        # Isolate peak activity parameters
        unique_strikes = recent_window['strike'].unique()
        
        # A true density zone means heavy block volume is targeted at 1 or 2 specific strikes
        if len(unique_strikes) <= 2:
            zones_detected += 1
            total_zone_volume = int(recent_window['volume'].sum())
            
            quadrants = recent_window['quadrant'].tolist()
            ce_count = len(recent_window[recent_window['type'] == 'CE'])
            pe_count = len(recent_window[recent_window['type'] == 'PE'])
            
            # Formulate the directional bias based on structural accumulation vs distribution rules
            if "Call Buying" in quadrants or "Put Writing" in quadrants:
                bias_class = "badge-pump"
                bias_text = "⚡ HEAVY ACCUMULATION FLIPS (PUMP FLOOR)"
                border_color = "#2ebd85"
                explanation = "Smart money is actively absorbing offers inside a narrow range, building a strong support floor for an upward trend."
            else:
                bias_class = "badge-dump"
                bias_text = "⚠️ HEAVY DISTRIBUTION SWEEPS (DUMP CEILING)"
                border_color = "#f6465d"
                explanation = "Smart money is capping the market upside and distributing inventory, setting up a supply ceiling for a potential breakdown."

            mean_ltp = round(recent_window['ltp'].mean(), 1)
            last_timestamp = recent_window['timestamp'].iloc[0]
            strike_range_str = ", ".join(map(str, sorted(unique_strikes)))
            
            st.markdown(f"""
            <div class='zone-card' style='border-left: 5px solid {border_color};'>
                <div class='zone-header'>
                    <div class='asset-name'>🔍 {asset} COMPLEX</div>
                    <span class='{bias_class}'>{bias_text}</span>
                </div>
                <p style='font-size: 0.85rem; color: #e4e6eb; margin-bottom: 12px;'>
                    <b>Institutional Footprint Tracker:</b> {explanation}
                </p>
                <div class='row g-2'>
                    <div class='col-md-3'>
                        <div class='stat-container'>
                            <div class='stat-lbl'>Accumulated Volume</div>
                            <div class='stat-val' style='color: #ff9f43;'>{total_zone_volume:,} lots</div>
                        </div>
                    </div>
                    <div class='col-md-3'>
                        <div class='stat-container'>
                            <div class='stat-lbl'>Concentration Range</div>
                            <div class='stat-val' style='color: #ffffff;'>Strikes: {strike_range_str}</div>
                        </div>
                    </div>
                    <div class='col-md-3'>
                        <div class='stat-container'>
                            <div class='stat-lbl'>Mean Contract Premium</div>
                            <div class='stat-val' style='color: #ff9f43;'>{mean_ltp}</div>
                        </div>
                    </div>
                    <div class='col-md-3'>
                        <div class='stat-container'>
                            <div class='stat-lbl'>Last Captured Activity</div>
                            <div class='stat-val' style='color: #a0a5b5;'>{last_timestamp}</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    if zones_detected == 0:
        st.info("🎯 Exchange options order books are balanced. Scanning depth files for massive micro-range loading activity...")

scan_and_render_density_nodes()
