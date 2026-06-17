def capture_hybrid_market_state():
    ist_tz = pytz.timezone('Asia/Kolkata')
    ts_string = datetime.now(ist_tz).strftime("%H:%M:%S")
    current_snapshot = []
    live_data_fetched = False

    def safe_scrip_list(res):
        """Normalize Neo API search_scrip response to a flat list."""
        if isinstance(res, dict):
            return res.get('data', []) or res.get('result', [])
        elif isinstance(res, list):
            return res
        return []

    def safe_ltp(quote_item):
        """Extract LTP robustly from a Neo live quote dict."""
        for key in ('last_traded_price', 'ltp', 'lastPrice', 'c'):
            val = quote_item.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    def safe_volume(quote_item):
        """Extract volume robustly."""
        for key in ('volume', 'tradedQuantity', 'vol', 'totalTradedVolume'):
            val = quote_item.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    continue
        return 0

    def fetch_ltp(token_id, segment):
        """Fetch live quote and return (ltp, volume). Returns (0.0, 0) on failure."""
        try:
            q = api_client.get_live_quotes([{
                "instrument_token": str(token_id),
                "exchange_segment": segment
            }])
            if q and isinstance(q, list) and len(q) > 0:
                return safe_ltp(q[0]), safe_volume(q[0])
        except Exception:
            pass
        return 0.0, 0

    def normalize_opt_type(raw):
        """Return 'CE' or 'PE' or None from any Neo option type string."""
        raw = str(raw).strip().upper()
        if raw in ('CE', 'CALL', 'C'):
            return 'CE'
        if raw in ('PE', 'PUT', 'P'):
            return 'PE'
        return None

    def expiry_matches(trd_sym, exp_tag):
        """
        Check if a trading symbol contains the configured expiry string.
        exp_tag examples: '23JUN26', '30JUN26', '17JUL26'
        Normalise both sides to uppercase for comparison.
        """
        return exp_tag.upper() in str(trd_sym).upper()

    if hasattr(api_client, 'search_scrip'):
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = 0.0
            exp_tag = meta["exp"]

            # ── Step 1: Resolve underlying price ─────────────────────────
            try:
                if meta["is_fut"]:
                    res_fo = api_client.search_scrip(
                        exchange_segment=meta["fo_seg"], symbol=symbol
                    )
                    fo_records = safe_scrip_list(res_fo)

                    for item in fo_records:
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                        # Must be a future AND match our target expiry
                        if "FUT" in trd_sym and expiry_matches(trd_sym, exp_tag):
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["fo_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
                else:
                    # Equity: use the cash-market segment
                    res_cm = api_client.search_scrip(
                        exchange_segment=meta["cm_seg"], symbol=symbol
                    )
                    cm_records = safe_scrip_list(res_cm)

                    for item in cm_records:
                        trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()
                        if trd_sym == f"{symbol}-EQ" or trd_sym == symbol:
                            token = item.get("pSymbol", item.get("token"))
                            ltp_val, _ = fetch_ltp(token, meta["cm_seg"])
                            if ltp_val > 0:
                                underlying_price = ltp_val
                                break
            except Exception:
                pass

            if underlying_price <= 0.0:
                continue  # Can't build strikes without an anchor

            # ── Step 2: Build ATM strike ladder ──────────────────────────
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = {
                atm_strike - meta["step"],
                atm_strike,
                atm_strike + meta["step"]
            }

            # ── Step 3: Fetch F&O chain for this symbol ───────────────────
            try:
                res_fo2 = api_client.search_scrip(
                    exchange_segment=meta["fo_seg"], symbol=symbol
                )
                fo_records2 = safe_scrip_list(res_fo2)
            except Exception:
                continue

            for item in fo_records2:
                try:
                    trd_sym = str(item.get("pTrdSymbol", item.get("trdSym", ""))).upper()

                    # ── KEY FIX: filter by configured expiry ──────────────
                    if not expiry_matches(trd_sym, exp_tag):
                        continue

                    raw_opt = item.get("pOptionType", item.get("optTp", ""))
                    opt_type = normalize_opt_type(raw_opt)
                    if opt_type is None:
                        continue  # Skip futures rows in the same search result

                    # Strike price — try multiple field names
                    raw_strike = item.get("pStrikePrice", item.get("strkPrc", item.get("strikePrice", 0)))
                    try:
                        strike_val = int(float(raw_strike))
                    except (ValueError, TypeError):
                        continue

                    if strike_val not in target_strikes:
                        continue

                    token_id = item.get("pSymbol", item.get("token"))
                    ltp_val, vol = fetch_ltp(token_id, meta["fo_seg"])

                    if ltp_val <= 0.0:
                        continue

                    current_snapshot.append({
                        "timestamp": ts_string,
                        "asset": symbol,
                        "formatted_symbol": trd_sym,
                        "direction": "CALL ACCUMULATION" if opt_type == "CE" else "PUT DISTRIBUTION",
                        "volume": vol,
                        "ltp": ltp_val,
                        "underlying": underlying_price,
                        "status": "🟢 LIVE SPEED"
                    })
                    live_data_fetched = True

                except Exception:
                    continue

    # ── Off-hours synthetic fallback ──────────────────────────────────────
    if not live_data_fetched:
        for symbol, meta in ASSET_ROUTING.items():
            underlying_price = meta["base"] + round(random.uniform(-15, 15), 1)
            atm_strike = int(round(underlying_price / meta["step"]) * meta["step"])
            target_strikes = [atm_strike - meta["step"], atm_strike, atm_strike + meta["step"]]

            for strike in target_strikes:
                for opt in ["CE", "PE"]:
                    display_symbol = f"{symbol}{meta['exp']}{strike}{opt}"
                    ltp = (
                        round(random.uniform(40.0, 260.0), 1)
                        if symbol in ["NIFTY", "BANKNIFTY"]
                        else round(random.uniform(6.0, 65.0), 1)
                    )
                    vol = random.randint(15000, 125000)

                    current_snapshot.append({
                        "timestamp": ts_string,
                        "asset": symbol,
                        "formatted_symbol": display_symbol,
                        "direction": "CALL ACCUMULATION" if opt == "CE" else "PUT DISTRIBUTION",
                        "volume": vol,
                        "ltp": ltp,
                        "underlying": underlying_price,
                        "status": "🌙 OFF-HOURS FALLBACK"
                    })

    if current_snapshot:
        st.session_state["terminal_stream_buffer"] = current_snapshot
