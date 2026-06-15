import streamlit as st
import pandas as pd
import json
import io

st.set_page_config(page_title="NSE Live Option Chain", layout="wide")

st.title("⛓️ NSE Institutional Live Option Chain")
st.caption("Reference Architecture: NiftyTrader Symmetrical Core Option Chain Dashboard")

asset = st.selectbox("Select Chain Base Asset", ["NIFTY", "BANKNIFTY"])

if 'global_history' in st.session_state and st.session_state.global_history:
    asset_records = [r for r in st.session_state.global_history if r['Asset'] == asset]
    
    if asset_records:
        latest_record = asset_records[-1]
        spot = float(latest_record['Spot'].replace(',', '')) if isinstance(latest_record['Spot'], str) else latest_record['Spot']
        
        # FIX: Wrapped raw string structure into io.StringIO memory stream buffer to bypass file path lookups
        raw_json_string = latest_record['Raw_Data']
        df = pd.read_json(io.StringIO(raw_json_string))
        
        st.metric(label=f"Current {asset} Spot Premium Price", value=f"{spot:,.2f}")
        
        c_df = df[df['Type'] == 'Call'].sort_values('Strike')
        p_df = df[df['Type'] == 'Put'].sort_values('Strike')
        
        chain_rows = []
        for strike in c_df['Strike'].unique():
            c_row = c_df[c_df['Strike'] == strike].iloc[0]
            p_row = p_df[p_df['Strike'] == strike].iloc[0]
            
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
            
        st.markdown("### Symmetrical Derivatives Matrix (Calls Left | Puts Right)")
        st.table(pd.DataFrame(chain_rows))
    else:
        st.info("⏳ Processing data feed for selected asset. Streaming active shortly...")
else:
    st.info("⏳ Synchronizing cloud network data maps. Streaming active shortly...")

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
