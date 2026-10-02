#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import hashlib
import hmac
import time
import pandas as pd
import os


API_KEY = os.environ.get('API_KEY')
SECRET = os.environ.get('SECRET')

BASE_URL = "https://mock-api.roostoo.com"


def generate_signature(params):
    query_string = '&'.join(["{}={}".format(k, params[k])
                             for k in sorted(params.keys())])
    us = SECRET.encode('utf-8')
    m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
    return m.hexdigest()


def get_server_time():
    r = requests.get(
        BASE_URL + "/v3/serverTime",
    )
    print (r.status_code, r.text)
    return r.json()


def get_ex_info():
    r = requests.get(
        BASE_URL + "/v3/exchangeInfo",
    )
    print (r.status_code, r.text)
    return r.json()


def get_ticker(pair=None):
    payload = {
        "timestamp": int(time.time()),
    }
    if pair:
        payload["pair"] = pair

    r = requests.get(
        BASE_URL + "/v3/ticker",
        params=payload,
    )
    print (r.status_code, r.text)
    return r.json()


def get_balance():
    payload = {
        "timestamp": int(time.time()) * 1000,
    }

    r = requests.get(
        BASE_URL + "/v3/balance",
        params=payload,
        headers={"RST-API-KEY": API_KEY,
                 "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)
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
        headers={"RST-API-KEY": API_KEY,
                 "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)


def cancel_order():
    payload = {
        "timestamp": int(time.time()) * 1000,
        # "order_id": 77,
        "pair": "BTC/USD",
    }

    r = requests.post(
        BASE_URL + "/v3/cancel_order",
        data=payload,
        headers={"RST-API-KEY": API_KEY,
                 "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)


def query_order():
    payload = {
        "timestamp": int(time.time())*1000,
        # "order_id": 77,
        # "pair": "DASH/USD",
        # "pending_only": True,
    }

    r = requests.post(
        BASE_URL + "/v3/query_order",
        data=payload,
        headers={"RST-API-KEY": API_KEY,
                 "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)


def pending_count():
    payload = {
        "timestamp": int(time.time()) * 1000,
    }

    r = requests.get(
        BASE_URL + "/v3/pending_count",
        params=payload,
        headers={"RST-API-KEY": API_KEY,
                 "MSG-SIGNATURE": generate_signature(payload)}
    )
    print (r.status_code, r.text)
    return r.json()




if __name__ == '__main__':
    # get_server_time()
    # get_ex_info()
    #  get_ticker()
    # get_balance()
    # place_order("BNB", "BUY", 2)
    # get_balance()    
    # cancel_order()
    #query_order()
    #pending_count()



# 1. Initialize memory OUTSIDE the loop so it persists
    price_history = []

    while True:
        try:
            # 2. Wait to respect API rate limits
            time.sleep(60)

            # 3. Fetch data and extract the exact price 
            # (You MUST check the actual JSON response of get_ticker to find the right key for price)
            ticker_data = get_ticker("BNB/USD")
            # current_price = float(ticker_data["Price"]) # Change "Price" to whatever the Roostoo API actually uses
            current_price = float(ticker_data["Data"]["BNB/USD"]["LastPrice"])
            price_history.append(current_price)

            # 4. Cap the memory size to prevent memory leaks
            if len(price_history) > 60:
                price_history.pop(0)

            # 5. We need at least 60 data points before calculating a 60-period MA
            if len(price_history) == 60:
                # Convert to pandas to do math, but DO NOT overwrite the original price_history list
                series = pd.Series(price_history)
                
                # Since the list is exactly 60 items, the mean of the series IS the 60-period MA
                rolling_mean = series.mean() 

                # 6. Fetch balance using the CORRECT keys from your terminal output
                wallet = get_balance()
                usd_free = float(wallet["SpotWallet"]["USD"]["Free"])
                bnb_free = float(wallet["SpotWallet"]["BNB"]["Free"])

                # 7. Execution Logic (e.g., 1% threshold to avoid overtrading)
                if current_price < (rolling_mean * 0.99) and usd_free > (current_price * 1.1):
                    print(f"Signal BUY. Price: {current_price}, MA: {rolling_mean}")
                    # Buy 1 BNB. Do not dump your entire USD balance into one market order.
                    place_order("BNB", "BUY", 1) 

                elif current_price > (rolling_mean * 1.01) and bnb_free >= 1:
                    print(f"Signal SELL. Price: {current_price}, MA: {rolling_mean}")
                    place_order("BNB", "SELL", 1)

        except Exception as e:
            # If ANYTHING fails above (network error, bad JSON key), the bot jumps here instead of dying.
            print(f"Critical Error encountered: {e}. Sleeping before retry...")
            time.sleep(10) 
