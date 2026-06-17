# -----------------------------------------------------------------------------
# DIRECT LIVE BROKER INITIALIZATION (Wiped cache layers to prevent stuck states)
# -----------------------------------------------------------------------------
def initialized_live_broker():
    try:
        # Directly runs the authentication module without memory capture wrappers
        return get_kotak_client(), "SUCCESS"
    except Exception as e:
        return None, str(e)

client, login_status = initialized_live_broker()

# Display the real-time connection diagnostic banner right at the top
if login_status != "SUCCESS":
    st.error(f"❌ Kotak Auth Failed on Render Server: {login_status}")
    st.info("💡 Troubleshooting: Ensure your environment variables match exactly what works on your local Colab instance.")
else:
    st.success("🟢 Kotak Broker Session Successfully Initialized in the Web App Framework!")
