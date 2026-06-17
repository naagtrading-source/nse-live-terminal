import os
import time
import pyotp
from neo_api_client import NeoAPI

# Pull keys from your Render Environment Variables 
CONSUMER_KEY = os.getenv("KOTAK_CONSUMER_KEY")
UCC          = os.getenv("KOTAK_UCC")
MOBILE       = os.getenv("KOTAK_MOBILE")
MPIN         = os.getenv("KOTAK_MPIN")
TOTP_SECRET  = os.getenv("KOTAK_TOTP_SECRET")

# Hidden global memory container to hold the single active session
_client_instance = None

def get_kotak_client():
    """
    Singleton provider ensuring all pages share the exact same active login session.
    """
    global _client_instance
    
    # IF ALREADY LOGGED IN: Reuse the working session immediately
    if _client_instance is not None:
        return _client_instance
        
    # IF NOT LOGGED IN YET: Authenticate against Kotak servers
    print("📡 Establishing master connection to Kotak Neo core servers...")
    try:
        client = NeoAPI(environment='prod', consumer_key=CONSUMER_KEY, access_token=None, neo_fin_key=None)
        
        # 1. Generate the 6-digit TOTP security token
        clean_secret = TOTP_SECRET.replace(" ", "").strip()
        current_totp = pyotp.TOTP(clean_secret).now()
        
        # 2. Phase 1 Login
        client.totp_login(mobile_number=str(MOBILE), ucc=str(UCC), totp=str(current_totp))
        time.sleep(3)  # Sync time window
        
        # 3. Phase 2 MPIN Validation
        client.totp_validate(mpin=str(MPIN))
        time.sleep(2)  # Settle cookies
        
        # 4. Save connection globally
        _client_instance = client
        print("🎉 Kotak Session authenticated and loaded into global app memory!")
        
    except Exception as e:
        print(f"❌ Failed to initialize shared Kotak client: {e}")
        raise e
        
    return _client_instance
