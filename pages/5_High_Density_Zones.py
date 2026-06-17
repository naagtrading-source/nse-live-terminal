import streamlit as st
import pandas as pd
import sqlite3
from kotak_auth import get_kotak_client

st.set_page_config(page_title="High Density Zones", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .zone-card { background: #141722; border-radius: 6px; border: 1px solid #222634; padding: 18px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .asset-name { font-size: 1.3rem; font-weight: bold; font-family: monospace; color: #ffffff; letter-spacing: 0.5px; }
    .badge-pump { background-color: rgba(46, 189, 133, 0.12); color: #2ebd85; border: 1px solid #2ebd85; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .badge-dump { background-color: rgba(246, 70, 93, 0.12); color: #f6465d; border: 1px solid #f6465d; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .stat-box { background-color: #0b0c10; border: 1px solid #222634; padding: 10px; text-align: center; border-radius: 4px; }
    .stat-lbl { font-size: 0.68rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; }
    .stat-val { font-size: 1.25rem; font-weight: bold; font-family: monospace; margin-top: 2px; }
    .desc-text { font-size: 0.88rem; color: #d1d5db; margin-bottom: 15px; background: #1f2231; padding: 8px 12px; border-radius: 4px; border-left: 3px solid #ff9f43; }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 High-Density Institutional Volume Zones")
st.caption("Real-Time Price Range Absorption Dashboard | Live Active Kotak Feed Processing Matrix")

DB_FILE = "terminal_history.db"

def load_ledger_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.fragment(run_every=10)
def render_zones_dashboard():
    df = load_ledger_from_db()

    if df.empty:
        st.info("⏳ Awaiting strategic market data spikes... Stream tracking nodes remain connected.")
    else:
        st.write("### 🚀 Live Trade Configuration Blocks")
        
        for asset, group in df.groupby('asset'):
            recent = group.head(10)
            total_vol = int(recent['volume'].sum())
            
            # FIXED: Column mapping standardized to lowercase 'strike'
            strikes = [int(x) for x in recent['strike'].unique()]
            
            if len(strikes) <= 3 and total_vol > 10000:
                quadrants_seen = recent['quadrant'].astype(str).tolist()
                is_pump = any("Buying" in q or "Writing" in q for q in quadrants_seen)
                
                b_class = "badge-pump" if is_pump else "badge-dump"
                b_text = "🟢 PUMP NODE (ACCUMULATION FLOOR)" if is_pump else "🔴 DUMP NODE (SUPPLY CEILING)"
                b_color = "#2ebd85" if is_pump else "#f6465d"
                
                opt_ltp = float(recent['ltp'].iloc[0])
                vwap_anchor = round(opt_ltp, 1)
                
                entry_zone = f"{vwap_anchor}"
                if is_pump:
                    stop_loss = round(vwap_anchor * 0.84, 1)
                    take_profit = round(vwap_anchor * 1.40, 1)
                    action_plan = f"Institutions are absorbing supply at Strike {strikes[0]}. Look to place entry limit orders exactly as the price retests the cluster floor."
                else:
                    stop_loss = round(vwap_anchor * 1.14, 1)
                    take_profit = round(vwap_anchor * 0.55, 1)
                    action_plan = f"Institutions are distributing inventory at Strike {strikes[0]}. Look for short setups or avoid long exposure under this supply ceiling."

                st.markdown(f"""
                <div class='zone-card' style='border-left: 5px solid {b_color};'>
                    <div class='zone-header'>
                        <div class='asset-name'>🔍 {asset} PREMIUM MATRIX</div>
                        <span class='{b_class}'>{b_text}</span>
                    </div>
                    <div class='desc-text'><b>Execution Strategy:</b> {action_plan}</div>
                    <div class='row g-2'>
                        <div class='col-md-3'><div class='stat-box'><div class='stat-lbl'>Cluster Strike Area</div><div class='stat-val' style='color:#fff;'>{strikes[0]}</div></div></div>
                        <div class='col-md-3'><div class='stat-box' style='border-color:{b_color};'><div class='stat-lbl' style='color:{b_color}; font-weight:700;'>Limit Entry VWAP</div><div class='stat-val' style='color:#fff;'>{entry_zone}</div></div></div>
                        <div class='col-md-3'><div class='stat-box'><div class='stat-lbl'>Invalidation Line (SL)</div><div class='stat-val' style='color:#f6465d;'>{stop_loss}</div></div></div>
                        <div class='col-md-3'><div class='stat-box'><div class='stat-lbl'>Target Projection (TP)</div><div class='stat-val' style='color:#ff9f43;'>{take_profit}</div></div></div>
                    </div>
                    <p style='font-size:0.72rem; color:#666; margin:8px 0 0 0; text-align:right;'>Accumulated Block Volume: {total_vol:,} lots | Last Scan: {recent['timestamp'].iloc[0]}</p>
                </div>
                """, unsafe_allow_html=True)

render_zones_dashboard()
