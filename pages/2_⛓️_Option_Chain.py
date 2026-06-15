import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="NSE Live Option Chain", layout="wide")

st.title("⛓️ NSE Institutional Live Option Chain")
st.caption("Reference Architecture: NiftyTrader Symmetrical Core Option Chain Dashboard")

asset = st.selectbox("Select Chain Base Asset", ["NIFTY", "BANKNIFTY"])

if 'global_history' in st.session_state and st.session_state.global_history:
    # Extract the absolute latest data snapshot record from the cache list
    latest_record = [r for r in st.session_state.global_history if r['Asset'] == asset][-1]
    
    spot = float(latest_record['Spot'].replace(',', '')) if isinstance(latest_record['Spot'], str) else latest_record['Spot']
    df = pd.read_json(latest_record['Raw_Data'])
    
    st.metric(label=f"Current {asset} Spot Premium Price", value=f"{spot:,.2f}")
    
    # Split call and put parameters to align side-by-side cleanly
    c_df = df[df['Type'] == 'Call'].sort_values('Strike')
    p_df = df[df['Type'] == 'Put'].sort_values('Strike')
    
    chain_rows = []
    for strike in c_df['Strike'].unique():
        c_row = c_df[c_df['Strike'] == strike].iloc[0]
        p_row = p_df[p_df['Strike'] == strike].iloc[0]
        
        # Color shade row cells depending on whether strikes are in-the-money (ITM)
        is_itm_call = "🔸" if strike < spot else ""
        is_itm_put = "🔸" if strike > spot else ""
        
        chain_rows.append({
            'CALL VOLUME': f"{int(c_row['Volume']):,}",
            'CALL LTP': f"{c_row['LTP']:.1f} {is_itm_call}",
            'CALL CHG OI': f"{int(c_row['Chg_OI']):+,}",
            'CALL OI': f"{int(c_row['OI']):,}",
            'STRIKE PRICE': f"🎯 {strike}",
            'PUT OI': f"{int(p_row['OI']):,}",
            'PUT CHG OI': f"{int(p_row['Chg_OI']):+,}",
            'PUT LTP': f"{is_itm_put} {p_row['LTP']:.1f}",
            'PUT VOLUME': f"{int(p_row['Volume']):,}"
        })
        
    chain_display_df = pd.DataFrame(chain_rows)
    
    # Center the table visualization around the active At-The-Money (ATM) zone
    atm_index = (df['Strike'] - spot).abs().idxmin()
    atm_strike = df.loc[atm_index, 'Strike']
    
    st.markdown("### Symmetrical Derivatives Matrix (Calls Left | Puts Right)")
    st.table(chain_display_df)
else:
    st.info("Synchronizing data arrays. Option matrix streaming active shortly...")
