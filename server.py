import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import ccxt
import time
import hmac
import hashlib
import json
import uvicorn

app = FastAPI(title="Hitech Crypto Trading Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HitechAIBot:
    def get_exchange(self, exchange_name, api_key, secret_key):
        exchange_class = getattr(ccxt, exchange_name.lower())
        return exchange_class({'apiKey': api_key, 'secret': secret_key, 'enableRateLimit': True})

ai_bot = HitechAIBot()

# ---------------------------------------------------
# 1. REAL PORTFOLIO & BALANCE ROUTE (COINDCX + CCXT)
# ---------------------------------------------------
@app.post("/api/portfolio/balance")
def get_real_portfolio(data: dict):
    try:
        exchange_name = data.get("broker", "binance").lower()
        api_key = data.get("api_key")
        secret_key = data.get("secret_key")

        if not api_key or not secret_key:
            return {"status": "success", "balance": "$0.00", "history": []}

        # Agar CoinDCX hai toh custom signature logic
        if exchange_name == 'coindcx':
            secret_bytes = bytes(secret_key, encoding='utf-8')
            ts = int(round(time.time() * 1000))
            body = {"timestamp": ts}
            json_body = json.dumps(body)
            
            signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()
            
            headers = {
                'Content-Type': 'application/json',
                'X-AUTH-APIKEY': api_key,
                'X-AUTH-SIGNATURE': signature
            }
            
            response = requests.post('https://api.coindcx.com/exchange/v1/users/balances', data=json_body, headers=headers)
            balances = response.json()
            
            ticker_resp = requests.get('https://api.coindcx.com/exchange/ticker')
            tickers = ticker_resp.json()
            price_map = {}
            for t in tickers:
                market = t.get('market', '')
                price_map[market] = float(t.get('last_price', 0))

            total_portfolio_value_inr = 0.0
            active_assets = []

            if isinstance(balances, list):
                for b in balances:
                    currency = b.get('currency', '')
                    balance_qty = float(b.get('balance', 0.0))
                    locked_qty = float(b.get('locked', 0.0))
                    total_qty = balance_qty + locked_qty

                    if total_qty > 0:
                        if currency == 'INR':
                            total_portfolio_value_inr += total_qty
                            active_assets.append({"symbol": "INR", "side": "HOLD", "price": f"₹{total_qty:,.2f}"})
                        else:
                            market_usdt = f"{currency}USDT"
                            market_inr = f"{currency}INR"
                            
                            coin_price_inr = 0.0
                            if market_inr in price_map:
                                coin_price_inr = price_map[market_inr]
                            elif market_usdt in price_map and 'USDTINR' in price_map:
                                coin_price_inr = price_map[market_usdt] * price_map['USDTINR']

                            asset_value_inr = total_qty * coin_price_inr
                            total_portfolio_value_inr += asset_value_inr
                            
                            if asset_value_inr > 1 or total_qty > 0:
                                active_assets.append({
                                    "symbol": f"{currency}/USDT",
                                    "side": f"Qty: {total_qty:.4f}",
                                    "price": f"₹{asset_value_inr:,.2f}"
                                })

            total_portfolio_value_usd = total_portfolio_value_inr / 83.0

            return {
                "status": "success",
                "balance": f"${total_portfolio_value_usd:,.2f} (₹{total_portfolio_value_inr:,.2f})",
                "history": active_assets
            }
        else:
            exchange = ai_bot.get_exchange(exchange_name, api_key, secret_key)
            balance = exchange.fetch_balance()
            total_usdt = balance.get('total', {}).get('USDT', 0.0)
            return {
                "status": "success",
                "balance": f"${total_usdt:,.2f}",
                "history": []
            }
    except Exception as e:
        return {"status": "error", "message": str(e), "balance": "$0.00", "history": []}

# ---------------------------------------------------
# 2. REAL TRADE EXIT ROUTE (COINDCX / CCXT)
# ---------------------------------------------------
@app.post("/api/trade/exit")
def exit_trade(data: dict):
    broker = data.get("broker", "coindcx").lower()
    symbol = data.get("symbol") # e.g., "POL/USDT"
    api_key = data.get("api_key")
    secret_key = data.get("secret_key")
    
    if not api_key or not secret_key:
        return {"status": "error", "message": "API keys required"}
        
    try:
        if broker == 'coindcx':
            # CoinDCX Market Sell API integration
            base_currency = symbol.split('/')[0]
            market_pair = f"{base_currency}USDT"
            
            # Fetch balance first to get exact qty
            secret_bytes = bytes(secret_key, encoding='utf-8')
            ts = int(round(time.time() * 1000))
            body = {"timestamp": ts}
            json_body = json.dumps(body)
            signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()
            headers = {'Content-Type': 'application/json', 'X-AUTH-APIKEY': api_key, 'X-AUTH-SIGNATURE': signature}
            
            resp = requests.post('https://api.coindcx.com/exchange/v1/users/balances', data=json_body, headers=headers)
            balances = resp.json()
            
            sell_qty = 0.0
            for b in balances:
                if b.get('currency') == base_currency:
                    sell_qty = float(b.get('balance', 0.0)) + float(b.get('locked', 0.0))
                    break
                    
            if sell_qty <= 0:
                return {"status": "error", "message": f"No balance for {base_currency}"}
                
            # Place order on CoinDCX
            order_body = {
                "timestamp": ts,
                "order": {
                    "side": "sell",
                    "order_type": "market_order",
                    "market": market_pair,
                    "total_quantity": sell_qty
                }
            }
            order_json = json.dumps(order_body)
            order_sig = hmac.new(secret_bytes, order_json.encode(), hashlib.sha256).hexdigest()
            order_headers = {'Content-Type': 'application/json', 'X-AUTH-APIKEY': api_key, 'X-AUTH-SIGNATURE': order_sig}
            
            order_resp = requests.post('https://api.coindcx.com/exchange/v1/orders/create', data=order_json, headers=order_headers)
            res_data = order_resp.json()
            
            return {"status": "success", "message": f"Sold {sell_qty} {base_currency} successfully!", "details": res_data}
        else:
            exchange = ai_bot.get_exchange(broker, api_key, secret_key)
            balance = exchange.fetch_balance()
            base_currency = symbol.split('/')[0]
            amount = float(balance['total'].get(base_currency, 0))
            
            if amount <= 0:
                return {"status": "error", "message": f"No balance found for {base_currency}"}
                
            order = exchange.create_market_sell_order(symbol, amount)
            return {"status": "success", "message": f"Successfully sold {amount} {base_currency}!"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def root():
    return {"status": "Hitech Crypto Bot Backend Running!"}

@app.post("/api/verify-key")
def verify_key(data: dict):
    valid_keys = {"HITECH-123", "PRO-JAMEEL-99"}
    return {"status": "success" if data.get("key") in valid_keys else "error"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
