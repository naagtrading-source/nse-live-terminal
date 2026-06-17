import os
import sys
import time
from datetime import datetime
import pandas as pd
import pyotp
import requests
from neo_api_client import NeoAPI

# --- CREDENTIAL MATRIX ---
# On Render, never hardcode keys. Store them securely in "Environment Variables"
CONSUMER_KEY = os.getenv("KOTAK_CONSUMER_KEY")
UCC          = os.getenv("KOTAK_UCC")
MOBILE       = os.getenv("KOTAK_MOBILE")
MPIN         = os.getenv("KOTAK_MPIN")
TOTP_SECRET  = os.getenv("KOTAK_TOTP_SECRET")

# --- MEMORY REPOSITORIES ---
last_seen_volumes = {}
radar_tokens = []
contract_mappings = {}

def init_kotak_client():
    print("🚀 Initializing Authenticated Kotak Neo Client Session...")
    client = NeoAPI(environment='prod', consumer_key=CONSUMER_KEY, access_token=None, neo_fin_key=None)
    
    # Programmatic 2FA generation to prevent login prompt timeouts
    clean_secret = TOTP_SECRET.replace(" ", "").strip()
    current_totp = pyotp.TOTP(clean_secret).now()
    
    client.totp_login(mobile_number=str(MOBILE), ucc=str(UCC), totp=str(current_totp))
    time.sleep(3) # Structural rest window to settle session flags
    client.totp_validate(mpin=str(MPIN))
    time.sleep(2)
    return client

def build_expanded_target_list(client):
    global radar_tokens, contract_mappings
    print("📥 Syncing master instrument tokens...")
    
    # Download master list authentically via active session
    master_paths = client.scrip_master()
    nse_fo_url = next((url for url in master_paths.get('filesPaths', []) if "nse_fo" in url), None)
    
    if nse_fo_url:
        res = requests.get(nse_fo_url)
        with open("nse_fo.csv", "wb") as f:
            f.write(res.content)
            
        print("🔍 Parsing expanded watch targets...")
        # Broad targets: Major Indexes + Selected High-Beta Market Movers
        tracked_underlyings = {"NIFTY", "BANKNIFTY", "FINNIFTY", "RELIANCE", "HDFCBANK", "INFY"}
        
        with open("nse_fo.csv", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.replace(';', ',').split(',')
                if len(parts) > 6:
                    token_id   = parts[0].strip()
                    underlying = parts[4].strip().upper()
                    contract   = parts[5].strip()
                    opt_type   = parts[6].strip()
                    
                    if underlying in tracked_underlyings and opt_type in ["CE", "PE"]:
                        radar_tokens.append(token_id)
                        contract_mappings[token_id] = contract
        print(f"✅ Scanning Network Configured! Watching {len(radar_tokens):,} option contracts.")

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
            
            for item in data_list:
                t_id = str(item.get('exchange_token', item.get('token', item.get('instrument_token'))))
                live_vol = int(item.get('last_volume', item.get('volume', item.get('tot_trd_qty', 0))))
                
                if live_vol == 0: continue
                
                # Dynamic Threshold: Index options use 5k lots baseline; equities use 2k lots
                contract_name = item.get('display_symbol', contract_mappings.get(t_id, f"Token-{t_id}"))
                baseline = 5000 if any(idx in contract_name for idx in ["NIFTY", "BANK", "FIN"]) else 2000
                
                if live_vol >= (baseline * 3.0):
                    if t_id in last_seen_volumes and live_vol == last_seen_volumes[t_id]:
                        continue
                    
                    last_seen_volumes[t_id] = live_vol
                    surge = round(((live_vol - baseline) / baseline) * 100, 1)
                    
                    # Store alert state locally or push directly to web dashboard log file
                    alert_log = f"🚨 {ts} | {contract_name} | Volume: {live_vol:,} (+{surge}% Spike)\n"
                    print(alert_log.strip())
                    with open("live_alerts.log", "a") as log_file:
                        log_file.write(alert_log)
                        
        except Exception as e:
            pass

if __name__ == "__main__":
    try:
        session = init_kotak_client()
        build_expanded_target_list(session)
        while True:
            monitor_stream_cycle(session)
            time.sleep(10)
    except KeyboardInterrupt:
        print("Loop stopped.")
