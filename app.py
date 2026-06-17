import streamlit as st
import pandas as pd
import sqlite3
import streamlit.components.v1 as components
from kotak_auth import get_kotak_client

st.set_page_config(page_title="Symmetrical Institutional Flow Terminal", layout="wide", page_icon="🚨")

st.markdown("""
    <style>
    .main { background-color: #0b0c10; color: #e4e6eb; }
    .stTable, table { width: 100% !important; table-layout: fixed !important; text-align: center !important; }
    th { background-color: #1b1e29 !important; color: #a0a5b5 !important; text-transform: uppercase; font-size: 0.62rem !important; font-weight: bold !important; padding: 3px 1px !important; }
    td { text-align: center !important; font-size: 0.68rem !important; padding: 4px 1px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
    .signal-card { border-radius: 6px; padding: 12px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.6); }
    .param-box { background: #131722; border: 1px solid #222634; border-radius: 4px; padding: 6px; text-align: center; }
    .param-lbl { font-size: 0.65rem; color: #a0a5b5; text-transform: uppercase; font-weight: 600; }
    .param-val { font-size: 1.15rem; font-weight: 900; font-family: monospace; margin-top: 2px; }
    .val-white { color: #ffffff !important; }
    .val-red { color: #f6465d !important; }
    .val-orange { color: #ff9f43 !important; }
    .section-header { background: #1f2231; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 1.1rem; color: #ff9f43; margin-top: 25px; margin-bottom: 15px; border-left: 4px solid #ff9f43; }
    .asset-title-banner { background: #141722; padding: 6px; border-radius: 4px; font-weight: bold; color: #fff; font-size: 1rem; border: 1px solid #222634; margin-bottom: 10px; text-align: center; font-family: monospace; }
    .pcr-box { background-color: #1a1e29; border: 1px solid #2d334a; padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; text-align: center; margin-bottom: 10px; color: #a0a5b5; }
    </style>
""", unsafe_allow_html=True)

st.title("🚨 Symmetrical Institutional Volatility Terminal")
st.caption("Advanced Real-Time Multi-Grid Matrix Terminal | Live Kotak Securities Feed Nodes")

DB_FILE = "terminal_history.db"

def load_ledger_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def render_instrument_block(asset_name, df_source):
    if df_source.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Connecting to data streams...</p>", unsafe_allow_html=True)
        return
        
    f_df = df_source[df_source['asset'] == asset_name].copy()
    if f_df.empty:
        st.markdown("<p style='color:#666;font-size:0.85rem;'>Awaiting footprint...</p>", unsafe_allow_html=True)
        return
        
    total_ce_vol = f_df[f_df['type'] == 'CE']['volume'].sum()
    total_pe_vol = f_df[f_df['type'] == 'PE']['volume'].sum()
    pcr_val = round(total_pe_vol / max(1, total_ce_vol), 2)
    st.markdown(f"<div class='pcr-box'>Volume PCR: {pcr_val}</div>", unsafe_allow_html=True)
        
    latest_block = f_df.sort_values(by='id', ascending=False).head(2)
    if not latest_block.empty:
        target_strike_val = int(latest_block['strike'].iloc[0])
        opt_ltp = float(latest_block['ltp'].iloc[0])
        vwap_anchor = round(opt_ltp, 1)
        direction_str = str(latest_block['direction'].iloc[0]).upper()
        
        if "BULLISH" in direction_str or "PUMP" in direction_str:
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #2ebd85; background: rgba(46, 189, 133, 0.05); border-left: 5px solid #2ebd85;'>
                <p style='color: #2ebd85; margin: 0 0 4px 0; font-size:0.85rem; font-weight:700;'>🔥 ELITE LONG SETUP: STRIKE {target_strike_val}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box' style='border-color:#2ebd85;'><div class='param-lbl'>OB Entry</div><div class='param-val val-white'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Stop Loss</div><div class='param-val val-red'>{round(vwap_anchor*0.84,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Target</div><div class='param-val val-orange'>{round(vwap_anchor*1.40,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='signal-card' style='border: 1px solid #f6465d; background: rgba(246, 70, 93, 0.05); border-left: 5px solid #f6465d;'>
                <p style='color: #f6465d; margin: 0 0 4px 0; font-size:0.85rem; font-weight:700;'>🔥 ELITE SHORT SETUP: STRIKE {target_strike_val}</p>
                <div class='row g-1'>
                    <div class='col-4'><div class='param-box' style='border-color:#f6465d;'><div class='param-lbl'>OB Entry</div><div class='param-val val-white'>{vwap_anchor}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Stop Loss</div><div class='param-val val-red'>{round(vwap_anchor*1.14,1)}</div></div></div>
                    <div class='col-4'><div class='param-box'><div class='param-lbl'>Target</div><div class='param-val val-orange'>{round(vwap_anchor*0.55,1)}</div></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    sorted_group = f_df.sort_values(by='id', ascending=False)
    sorted_group = sorted_group.drop_duplicates(subset=['timestamp', 'type', 'quadrant', 'volume']).head(3)
    rows_html = ""
    for _, r in sorted_group.iterrows():
        dir_sign = str(r.get('direction', '')).upper()
        cell_bg = "rgba(46, 189, 133, 0.1)" if ("BULLISH" in dir_sign or "PUMP" in dir_sign) else "rgba(246, 70, 93, 0.1)"
        text_color = "#2ebd85" if ("BULLISH" in dir_sign or "PUMP" in dir_sign) else "#f6465d"
        rows_html += f"""
        <tr style='background-color: {cell_bg} !important; border-bottom: 1px solid #222634;'>
            <td style='color:#a0a5b5;'>{r['timestamp']}</td>
            <td style='color:#fff; font-weight:bold;'>{int(r['strike'])}</td>
            <td style='color:#ff9f43;'>{r['type']}</td>
            <td style='color: {text_color}; font-weight:bold;'>{r['quadrant']}</td>
            <td style='color:#fff;'>{int(r['volume']):,}</td>
            <td style='color:#fff;'>{float(r['ltp']:.1f)}</td>
        </tr>"""
        
    if rows_html:
        table_html = f"""
        <html><head><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'></head>
        <body style='background-color: #0b0c10; padding:0; margin:0;'>
        <table class='table table-dark m-0' style='table-layout: fixed; width: 100%; font-size:0.68rem; text-align:center;'>
            <tbody>{rows_html}</tbody>
        </table></body></html>
        """
        components.html(table_html, height=115, scrolling=False)

@st.fragment(run_every=10)
def render_unified_dashboard_grid():
    all_df = load_ledger_from_db()
    
    st.markdown("<div class='section-header'>⚡ NATIONAL EXCHANGE EQUITY INDICES</div>", unsafe_allow_html=True)
    idx_col1, idx_col2 = st.columns(2)
    with idx_col1:
        st.markdown("<div class='asset-title-banner'>NIFTY 50 INDEX COUNTERS</div>", unsafe_allow_html=True)
        render_instrument_block("NIFTY", all_df)
    with idx_col2:
        st.markdown("<div class='asset-title-banner'>BANKNIFTY DERIVATIVES MATRIX</div>", unsafe_allow_html=True)
        render_instrument_block("BANKNIFTY", all_df)

    st.markdown("<div class='section-header'>🛢️ COMMODITY EXCHANGE (MCX FUTURE & OPTIONS)</div>", unsafe_allow_html=True)
    com_col1, com_col2, com_col3, com_col4 = st.columns(4)
    with com_col1:
        st.markdown("<div class='asset-title-banner'>CRUDEOIL</div>", unsafe_allow_html=True)
        render_instrument_block("CRUDEOIL", all_df)
    with com_col2:
        st.markdown("<div class='asset-title-banner'>NATURALGAS</div>", unsafe_allow_html=True)
        render_instrument_block("NATURALGAS", all_df)
    with com_col3:
        st.markdown("<div class='asset-title-banner'>GOLD (10G)</div>", unsafe_allow_html=True)
        render_instrument_block("GOLD", all_df)
    with com_col4:
        st.markdown("<div class='asset-title-banner'>SILVER (1KG)</div>", unsafe_allow_html=True)
        render_instrument_block("SILVER", all_df)

render_unified_dashboard_grid()
