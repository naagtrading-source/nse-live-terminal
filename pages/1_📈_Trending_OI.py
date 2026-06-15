import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Trending OI Data", layout="wide")

st.title("🔥 Trending OI Live Activity Matrix")
st.caption("Reference Architecture: NiftyTrader Trending OI Framework Model")

asset_filter = st.selectbox("Select Target Index Asset", ["NIFTY", "BANKNIFTY"])

if 'global_history' in st.session_state and st.session_state.global_history:
    h_list = st.session_state.global_history
    
    rows = []
    # Loop backward to place the latest data points chronologically at the top
    for item in reversed(h_list):
        if item['Asset'] == asset_filter:
            rows.append({
                'TIME': item['Timestamp'],
                'SPOT PRICE': f"{item['Spot']:,.2f}",
                'CALLS CHG OI': f"{item['Calls_Chg']:,}",
                'PUTS CHG OI': f"{item['Puts_Chg']:,}",
                'DIFF IN OI': f"{item['Diff']:,}",
                'DIFF %': f"{item['Diff_Pct']:+.1f}%",
                'PCR': f"{item['PCR']:.3f}",
                'VOL PCR': f"{item['Vol_PCR']:.3f}",
                'SENTIMENT': item['Sentiment']
            })
            
    if rows:
        st.table(pd.DataFrame(rows))
    else:
        st.info("Gathering background stream blocks. Updates display inside 60 seconds...")
else:
    st.info("Establishing cloud server matrix handshake pipeline logs. Please wait...")
