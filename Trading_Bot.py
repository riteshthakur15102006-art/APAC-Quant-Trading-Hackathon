#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import hashlib
import hmac
import time
import pandas as pd
import os
from datetime import datetime, timezone, timedelta

# MOCK KEYS HARDCODED FOR DEPLOYMENT STABILITY TONIGHT (PREP PERIOD)
API_KEY = os.environ.get('API_KEY')
SECRET = os.environ.get('SECRET')
BASE_URL = "https://mock-api.roostoo.com"

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
    # Return True only if the exchange executed the order successfully
    return r.status_code == 200


if __name__ == '__main__':
    price_history = []
    daily_trade_count = 0
    
    # Initialize HKT timezone (UTC+8)
    hkt_offset = timezone(timedelta(hours=8))
    last_trade_day = datetime.now(hkt_offset).day

    print("Starting Quantitative Execution Loop (HKT Sync - 60 Period MA)...")

    while True:
        try:
            # Poll every 60 seconds
            time.sleep(60)

            ticker_data = get_ticker("BNB/USD")
            current_price = float(ticker_data["Data"]["BNB/USD"]["LastPrice"])
            price_history.append(current_price)

            if len(price_history) > 60:
                price_history.pop(0)

            # Wait until we have 60 full minutes of data
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

                # 1% deviation logic with 0.1% Taker Fee factored in
                if current_price < (rolling_mean * 0.99) and usd_free > (current_price * 1.1):
                    print(f"[{now_hkt.strftime('%H:%M:%S')} HKT] Signal BUY. Price: {current_price}, MA: {rolling_mean:.2f}")
                    if place_order("BNB", "BUY", 1):
                        daily_trade_count += 1
                        print(f"Trade successful. Total trades today: {daily_trade_count}")

                elif current_price > (rolling_mean * 1.01) and bnb_free >= 1:
                    print(f"[{now_hkt.strftime('%H:%M:%S')} HKT] Signal SELL. Price: {current_price}, MA: {rolling_mean:.2f}")
                    if place_order("BNB", "SELL", 1):
                        daily_trade_count += 1
                        print(f"Trade successful. Total trades today: {daily_trade_count}")

        except Exception as e:
            print(f"[{datetime.now(hkt_offset).strftime('%H:%M:%S')} HKT] Critical Error: {e}. Sleeping 10s...")
            time.sleep(10)
