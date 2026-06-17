import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components
from kotak_auth import get_kotak_client

# -----------------------------------------------------------------------------
# DIRECT LIVE BROKER INITIALIZATION (Wiped cache layers to prevent stuck states)
# -----------------------------------------------------------------------------
def initialized_live_broker():
    try:
        return get_kotak_client(), "SUCCESS"
    except Exception as e:
        return None, str(e)

client, login_status = initialized_live_broker()
