def init_db():
    """Ensures the shared SQLite database table exists with the correct column schema."""
    import sqlite3
    conn = sqlite3.connect("terminal_history.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            asset TEXT,
            strike INTEGER,
            type TEXT,
            quadrant TEXT,
            volume INTEGER,
            ltp REAL,
            direction TEXT,
            market_type TEXT
        )
    """)
    conn.commit()
    conn.close()

def monitor_stream_cycle(client):
    global last_seen_volumes
    ts = datetime.now().strftime("%H:%M:%S")
    
    # Break targets into chunks of 50 to optimize server processing speed limits
    chunk_size = 50
    for i in range(0, len(radar_tokens), chunk_size):
        token_chunk = radar_tokens[i:i+chunk_size]
        params = [{"instrument_token": str(t), "exchange_segment": "nse_fo"} for t in token_chunk]
        
        try:
            response = client.quotes(instrument_tokens=params)
            data_list = response if isinstance(response, list) else response.get('data', [])
            
            # Ensure the local database file and ledger table are ready
            init_db()
            
            for item in data_list:
                t_id = str(item.get('exchange_token', item.get('token', item.get('instrument_token'))))
                live_vol = int(item.get('last_volume', item.get('volume', item.get('tot_trd_qty', 0))))
                
                if live_vol == 0: 
                    continue
                
                # Dynamic Threshold: Index options use 5k lots baseline; equities use 2k lots
                contract_name = item.get('display_symbol', contract_mappings.get(t_id, f"Token-{t_id}"))
                baseline = 5000 if any(idx in contract_name for idx in ["NIFTY", "BANK", "FIN"]) else 2000
                
                if live_vol >= (baseline * 3.0):
                    if t_id in last_seen_volumes and live_vol == last_seen_volumes[t_id]:
                        continue
                    
                    last_seen_volumes[t_id] = live_vol
                    surge = round(((live_vol - baseline) / baseline) * 100, 1)
                    
                    # --- DETERMINE OPTIONS METRIC DETAILS ---
                    # Safely parses option type details out of Kotak's text strings
                    opt_type = "CE" if "CE" in contract_name.upper() else "PE"
                    
                    # Isolate asset name from option contract naming standard (e.g., NIFTY26DEC30000CE -> NIFTY)
                    asset_label = "NIFTY" if "NIFTY" in contract_name.upper() else "BANKNIFTY"
                    if "FINNIFTY" in contract_name.upper(): asset_label = "FINNIFTY"
                    
                    # Extract numeric strike safely using fallback anchors
                    try:
                        import re
                        strike_matches = re.findall(r'\d+', contract_name)
                        # Pick the strike pricing number out of the expiration date sequences
                        strike_val = int(strike_matches[-1]) if len(strike_matches) > 1 else 30000
                    except:
                        strike_val = 30000
                        
                    live_ltp = float(item.get('ltp', 0.0))
                    quadrant_lbl = "Call Buying" if opt_type == "CE" else "Put Buying"
                    direction_lbl = "BULLISH" if opt_type == "CE" else "BEARISH"
                    
                    print(f"🚨 NEW SPIKE | {contract_name} | Vol: {live_vol:,} | Surge: +{surge}%")
                    
                    # --- WRITE DIRECTLY TO SHAREABLE SQLITE LEDGER ---
                    import sqlite3
                    conn = sqlite3.connect("terminal_history.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO ledger (timestamp, asset, strike, type, quadrant, volume, ltp, direction, market_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (ts, asset_label, strike_val, opt_type, quadrant_lbl, live_vol, live_ltp, direction_lbl, "EQUITY_DERIVATIVE"))
                    conn.commit()
                    conn.close()
                        
        except Exception as e:
            print(f"⚠️ SQL Pipeline Error: {e}")
