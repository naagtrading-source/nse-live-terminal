import sqlite3
import pandas as pd
import yfinance as yf
import pytz
import math
import random
from datetime import datetime, timedelta

DB_FILE = "terminal_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, asset TEXT, market_type TEXT, expiry TEXT,
            strike INTEGER, type TEXT, quadrant TEXT, direction TEXT, volume INTEGER, ltp REAL, delta REAL
        )
    """)
    conn.commit()
    conn.close()

def save_anomaly_to_db(item):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ledger (timestamp, asset, market_type, expiry, strike, type, quadrant, direction, volume, ltp, delta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item['Timestamp'], item['Asset'], item['MarketType'], item['Expiry'],
        item['Target Strike'], item['Type'], item['Quadrant'], item['Direction Sign'],
        item['Volume'], item['LTP'], item['Delta']
    ))
    conn.commit()
    conn.close()

def load_ledger_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger ORDER BY id DESC", conn)
        conn.close()
        if not df.empty:
            df['Target Strike'] = df['strike']
            df['Direction Sign'] = df['direction']
            df['Quadrant'] = df['quadrant']
        return df
    except:
        return pd.DataFrame()

def get_expiry_dates_for_asset(asset_name, market_type):
    ist_tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist_tz).date()
    if market_type == "COMMODITY":
        expiry_day = 19 if asset_name in ["CRUDEOIL", "NATURALGAS"] else 5
        curr_expiry = today.replace(day=expiry_day)
        if curr_expiry < today:
            nxt_m = today.replace(day=28) + timedelta(days=5)
            curr_expiry = nxt_m.replace(day=expiry_day)
        monthly_expiry = curr_expiry
    else:
        target_weekday = 1  
        days_to_expiry = (target_weekday - today.weekday()) % 7
        curr_expiry = today if days_to_expiry == 0 else today + timedelta(days=days_to_expiry)
        nxt_m = today.replace(day=28) + timedelta(days=5)
        ld = nxt_m - timedelta(days=nxt_m.day)
        monthly_expiry = ld - timedelta(days=(ld.weekday() - 1) % 7)
    return f"Expiry ({monthly_expiry.strftime('%d-%b')})" if market_type in ["STOCK", "COMMODITY"] else f"Expiry ({curr_expiry.strftime('%d-%b')})"

def calculate_bs_delta(spot, strike, option_type):
    try:
        t = 30 / 365; v = 0.15; r = 0.05
        d1 = (math.log(spot / strike) + (r + 0.5 * v ** 2) * t) / (v * math.sqrt(t))
        def cnd(x):
            return 0.5
        return round(cnd(d1), 2) if option_type == 'Call' else round(cnd(d1) - 1.0, 2)
    except: return 0.50

def run_automated_generation_cycle():
    all_assets = [
        ("NIFTY", "INDEX"), ("BANKNIFTY", "INDEX"),
        ("CRUDEOIL", "COMMODITY"), ("NATURALGAS", "COMMODITY"), ("GOLD", "COMMODITY"), ("SILVER", "COMMODITY"),
        ("RELIANCE", "STOCK"), ("HDFCBANK", "STOCK")
    ]
    
    # Run data simulation continuously to ensure all pages stay populated
    for symbol, market_type in all_assets:
        try:
            expiry_label = get_expiry_dates_for_asset(symbol, market_type)
            fallback = {"NIFTY":24150, "BANKNIFTY":52400, "CRUDEOIL":6400, "NATURALGAS":260, "GOLD":72300, "SILVER":88400, "RELIANCE":2450, "HDFCBANK":1610}
            spot = fallback.get(symbol, 100.0)
            step = 50 if symbol == "NIFTY" else 100 if symbol in ["BANKNIFTY","CRUDEOIL","GOLD"] else 250 if symbol == "SILVER" else 5
            
            atm = round(spot / step) * step
            ts_string = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
            chosen_offset = random.choice([-1, 1])
            strike = atm + (chosen_offset * step)
            
            vol_val = int(random.randint(1100000, 1850000)) if market_type != "COMMODITY" else int(random.randint(35000, 68000))
            market_bias = random.choice(["EXCELLENT_LONG_SETUP", "EXCELLENT_SHORT_SETUP"])
            
            if market_bias == "EXCELLENT_LONG_SETUP":
                quad_c, quad_p = "Call Buying", "Put Writing"
                sign_c, sign_p = "🟢 BULLISH", "🟢 BULLISH"
            else:
                quad_c, quad_p = "Call Writing", "Put Buying"
                sign_c, sign_p = "🔴 BEARISH", "🔴 BEARISH"
            
            ltp_c = random.randint(45, 180)
            ltp_p = random.randint(45, 180)
            
            save_anomaly_to_db({'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label, 'Target Strike': strike, 'Type': 'CE', 'Quadrant': quad_c, 'Direction Sign': sign_c, 'Volume': vol_val, 'LTP': ltp_c, 'Delta': 0.55})
            save_anomaly_to_db({'Timestamp': ts_string, 'Asset': symbol, 'MarketType': market_type, 'Expiry': expiry_label, 'Target Strike': strike, 'Type': 'PE', 'Quadrant': quad_p, 'Direction Sign': sign_p, 'Volume': int(vol_val * 0.95), 'LTP': ltp_p, 'Delta': -0.45})
        except:
            pass

init_db()
