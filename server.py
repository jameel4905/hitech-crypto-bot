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
# REAL TRADE EXIT ROUTE (FIXED)
# ---------------------------------------------------
@app.post("/api/trade/exit")
def exit_trade(data: dict):
    broker = data.get("broker", "binance").lower()
    symbol = data.get("symbol")
    api_key = data.get("api_key")
    secret_key = data.get("secret_key")
    
    if not api_key or not secret_key:
        return {"status": "error", "message": "API keys required"}
        
    try:
        exchange = ai_bot.get_exchange(broker, api_key, secret_key)
        balance = exchange.fetch_balance()
        
        # Symbol se base currency nikalo (e.g., "POL/USDT" -> "POL")
        base_currency = symbol.split('/')[0]
        amount = float(balance['total'].get(base_currency, 0))
        
        if amount <= 0:
            return {"status": "error", "message": f"No balance found for {base_currency}"}
            
        # Market Sell Order
        order = exchange.create_market_sell_order(symbol, amount)
        return {
            "status": "success",
            "message": f"Successfully sold {amount} {base_currency}!",
            "order_id": order.get('id')
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------
# OTHER ROUTES (Keep them as they were in your code)
# ---------------------------------------------------
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
