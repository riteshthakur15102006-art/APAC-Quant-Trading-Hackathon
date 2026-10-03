#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import hashlib
import hmac
import time
import pandas as pd
import os
from datetime import datetime, timezone, timedelta

# PRODUCTION KEYS - Ensure these are your real Roostoo API keys for the Oct 4 launch
API_KEY = os.environ.get('API_KEY')
SECRET = os.environ.get('SECRET')
BASE_URL = "https://mock-api.roostoo.com"

# CORE STRATEGY PARAMETERS
RISK_PERCENTAGE = 0.50  # Risk 50% of available USD per buy
BUY_DEVIATION = 0.99    # Buy at 1% below the 60-min average
SELL_DEVIATION = 1.01   # Sell at 1% above the 60-min average

def generate_signature(params):
    query_string = '&'.join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
    us = SECRET.encode('utf-8')
    m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
    return m.hexdigest()

def get_ticker(pair=None):
    payload = {"timestamp": int(time.time())}
    if pair:
        payload["pair"] = pair
    r = requests.get(BASE_URL + "/v3/ticker", params=payload)
    return r.json()

def get_balance():
    payload = {"timestamp": int(time.time()) * 1000}
    r = requests.get(
        BASE_URL + "/v3/balance",
        params=payload,
        headers={"RST-API-KEY": API_KEY, "MSG-SIGNATURE": generate_signature(payload)}
    )
    return r.json()

def place_order(coin, side, qty, price=None):
    payload = {
        "timestamp": int(time.time()) * 1000,
        "pair": coin + "/USD",
        "side": side,
        "quantity": qty,
    }
    if not price:
        payload['type'] = "MARKET"
    else:
        payload['type'] = "LIMIT"
        payload['price'] = price

    r = requests.post(
        BASE_URL + "/v3/place_order",
        data=payload,
        headers={"RST-API-KEY": API_KEY, "MSG-SIGNATURE": generate_signature(payload)}
    )
    return r.status_code == 200

if __name__ == '__main__':
    price_history = []
    daily_trade_count = 0
    
    # Initialize HKT timezone (UTC+8) to perfectly match hackathon exchange rollover
    hkt_offset = timezone(timedelta(hours=8))
    last_trade_day = datetime.now(hkt_offset).day

    print("🚀 LIVE: Starting Production Execution Loop (60-Period MA | 50% Sizing)...")

    while True:
        try:
            # Poll every 60 seconds to build the 1-minute chart internally
            time.sleep(60)

            ticker_data = get_ticker("BNB/USD")
            current_price = float(ticker_data["Data"]["BNB/USD"]["LastPrice"])
            price_history.append(current_price)

            if len(price_history) > 60:
                price_history.pop(0)

            # Wait until the bot has 60 full minutes of data before executing
            if len(price_history) == 60:
                wallet = get_balance()
                usd_free = float(wallet["SpotWallet"]["USD"]["Free"])
                bnb_free = float(wallet["SpotWallet"]["BNB"]["Free"])
                
                now_hkt = datetime.now(hkt_offset)
                
                # Reset trade counter at midnight HKT
                if now_hkt.day != last_trade_day:
                    print(f"[{now_hkt.strftime('%H:%M:%S')} HKT] Midnight Rollover. Previous day trades: {daily_trade_count}")
                    daily_trade_count = 0
                    last_trade_day = now_hkt.day

                series = pd.Series(price_history)
                rolling_mean = series.mean()

                # --- DYNAMIC BUY LOGIC ---
                if current_price < (rolling_mean * BUY_DEVIATION) and usd_free > 10:
                    usd_to_spend = usd_free * RISK_PERCENTAGE
                    trade_qty = round(usd_to_spend / current_price, 4)
                    
                    if trade_qty > 0.01:
                        print(f"[{now_hkt.strftime('%H:%M:%S')} HKT] 🟢 Signal BUY. Investing ${usd_to_spend:.2f} for {trade_qty} BNB.")
                        if place_order("BNB", "BUY", trade_qty):
                            daily_trade_count += 1

                # --- DYNAMIC SELL LOGIC ---
                elif current_price > (rolling_mean * SELL_DEVIATION) and bnb_free >= 0.01:
                    trade_qty = round(bnb_free, 4)
                    print(f"[{now_hkt.strftime('%H:%M:%S')} HKT] 🔴 Signal SELL. Liquidating {trade_qty} BNB.")
                    if place_order("BNB", "SELL", trade_qty):
                        daily_trade_count += 1

        except Exception as e:
            print(f"[{datetime.now(hkt_offset).strftime('%H:%M:%S')} HKT] ⚠️ Critical Error: {e}. Sleeping 10s...")
            time.sleep(10)
