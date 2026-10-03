#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import hashlib
import hmac
import time
import pandas as pd
import os

# MOCK KEYS HARDCODED FOR DEPLOYMENT STABILITY TONIGHT
# DO NOT USE THESE FOR LIVE TRADING ON OCT 4
API_KEY = os.environ.get('API_KEY')
SECRET = os.environ.get('SECRET')

BASE_URL = "https://mock-api.roostoo.com"

def generate_signature(params):
    query_string = '&'.join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
    us = SECRET.encode('utf-8')
    m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
    return m.hexdigest()

def get_server_time():
    r = requests.get(BASE_URL + "/v3/serverTime")
    return r.json()

def get_ex_info():
    r = requests.get(BASE_URL + "/v3/exchangeInfo")
    return r.json()

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
    print (r.status_code, r.text)

def cancel_order():
    payload = {
        "timestamp": int(time.time()) * 1000,
        "pair": "BTC/USD",
    }
    r = requests.post(
        BASE_URL + "/v3/cancel_order",
        data=payload,
        headers={"RST-API-KEY": API_KEY, "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)

def query_order():
    payload = {"timestamp": int(time.time())*1000}
    r = requests.post(
        BASE_URL + "/v3/query_order",
        data=payload,
        headers={"RST-API-KEY": API_KEY, "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)

def pending_count():
    payload = {"timestamp": int(time.time()) * 1000}
    r = requests.get(
        BASE_URL + "/v3/pending_count",
        params=payload,
        headers={"RST-API-KEY": API_KEY, "MSG-SIGNATURE": generate_signature(payload)}
    )
    return r.json()


if __name__ == '__main__':
    price_history = []
    window_size = 15 

    print("Starting hyper-sensitive quantitative execution loop...")

    while True:
        try:
            # Poll every 10 seconds to rapidly catch micro-fluctuations
            time.sleep(10)

            ticker_data = get_ticker("BNB/USD")
            current_price = float(ticker_data["Data"]["BNB/USD"]["LastPrice"])
            price_history.append(current_price)

            if len(price_history) > window_size:
                price_history.pop(0)

            if len(price_history) == window_size:
                series = pd.Series(price_history)
                rolling_mean = series.mean() 

                wallet = get_balance()
                usd_free = float(wallet["SpotWallet"]["USD"]["Free"])
                bnb_free = float(wallet["SpotWallet"]["BNB"]["Free"])

                # 0.1% threshold to force trades in a dead market
                if current_price < (rolling_mean * 0.999) and usd_free > (current_price * 1.1):
                    print(f"Signal BUY. Price: {current_price}, MA: {rolling_mean}")
                    place_order("BNB", "BUY", 1) 

                elif current_price > (rolling_mean * 1.001) and bnb_free >= 1:
                    print(f"Signal SELL. Price: {current_price}, MA: {rolling_mean}")
                    place_order("BNB", "SELL", 1)

        except Exception as e:
            print(f"Critical Error encountered: {e}. Sleeping before retry...")
            time.sleep(10)
