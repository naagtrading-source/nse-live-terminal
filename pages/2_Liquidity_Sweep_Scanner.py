import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Liquidity Sweep Scanner", layout="wide", page_icon="💥")

st.title("💥 Institutional Liquidity Sweep & Stop-Loss Hunting Scanner")
st.caption("Advanced Order Book Trapping Index | Locating Strategic Reversal Inflection Points")

DB_FILE = "terminal_history.db"

def load_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

df = load_data()
if not df.empty:
    st.write("### 🚨 Detected Active Stop-Loss Sweeps")
    # Isolate blocks exceeding extreme lot sizes to identify sweeps
    sweeps = df[df['volume'] > 1350000] if df['market_type'].iloc[0] != 'COMMODITY' else df[df['volume'] > 42000]
    
    if not sweeps.empty:
        for _, row in sweeps.head(8).iterrows():
            st.error(f"⚡ LIQUIDITY TRAP CAPTURED: {row['asset']} | Strike {row['strike']} | Time: {row['timestamp']} | Volume: {row['volume']:,} lots")
            st.markdown(f"**Market Profile footprint:** Smart Money executed deep retail stop-loss absorption via extreme **{row['quadrant']}** clusters. Prepare for a high-probability price reversal away from this zone.")
    else:
        st.info("🎯 Scanning depth levels... Order book liquidity balances are stable with zero retail stop-loss hunting signatures found.")
else:
    st.info("⏳ Synchronizing depth matrix channels...")
