import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="NSE Live Option Chain", layout="wide")

st.title("⛓️ NSE Institutional Live Option Chain")
st.caption("Reference Architecture: NiftyTrader Symmetrical Core Option Chain Dashboard")

# Initialize identical navigation matrices here to maintain state
def get_expiry_dates_local():
    import pytz
    from datetime import datetime, timedelta
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    days_to_thursday = (3 - today.weekday()) % 7
    curr_wk = today + timedelta(days=days_to_thursday)
    next_wk = curr_wk + timedelta(days=7)
    nxt_month = curr_wk.replace(day=28) + timedelta(days=5)
    last_day = nxt_month - timedelta(days=nxt_month.day)
    monthly = last_day - timedelta(days=(last_day.weekday() - 3) % 7)
    if monthly < today:
        nxt_month_alt = last_day + timedelta(days=5)
        last_day_alt = nxt_month_alt + timedelta(days=25)
        monthly = last_day_alt - timedelta(days=(last_day_alt.weekday() - 3) % 7)
    return [f"Current Week ({curr_wk.strftime('%d-%b')})", f"Next Week ({next_wk.strftime('%d-%b')})", f"Monthly Expiry ({monthly.strftime('%d-%b')})"]

c1, c2 = st.columns(2)
with c1:
    asset = st.selectbox("Select Chain Base Asset", ["NIFTY", "BANKNIFTY"])
with c2:
    selected_expiry = st.selectbox("Select Contract Expiry Series", get_expiry_dates_local())

if 'global_history' in st.session_state and st.session_state.global_history:
    # Filter memory logs strictly matching selected Asset AND selected Expiry Series
    asset_records = [r for r in st.session_state.global_history if r['Asset'] == asset and r.get('Expiry') == selected_expiry]
    
    if asset_records:
        latest_record = asset_records[-1]
        spot = latest_record['Spot']
        df = pd.read_json(io.StringIO(latest_record['Raw_Data']))
        
        st.metric(label=f"Current {asset} Spot Price", value=f"{spot:,.2f}")
        
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
        st.info("⏳ Initializing selected contract parameters. Feed activates inside 60s...")
else:
    st.info("⏳ Synchronizing tracking matrices...")

# --- DEVELOPER FOOTER BRANDING ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666; font-size: 0.85rem;'>This site is developed by SNY</p>", unsafe_allow_html=True)
