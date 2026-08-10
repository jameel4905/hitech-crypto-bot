from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import ccxt
from datetime import datetime, timedelta

app = FastAPI()

# App CORS policy (Flutter connectivity ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trade History aur Daily Limit Store karne ke liye Database List
trade_logs = [] 

# -------------------------------------------------------------
# 1. LIVE PRICES ENDPOINT (Jo app mein abhi chal raha hai)
# -------------------------------------------------------------
@app.get("/api/live-prices")
def get_live_prices():
    try:
        url = "https://api.coincap.io/v2/assets?limit=50"
        headers = {'Accept-Encoding': 'gzip'}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json().get('data', [])

        result = []
        for item in data:
            symbol = item.get('symbol', '').upper()
            price = float(item.get('priceUsd', 0))
            change = float(item.get('changePercent24Hr', 0))

            result.append({
                'symbol': f"{symbol}/USDT",
                'price': f"{price:.4f}" if price < 1 else f"{price:.2f}",
                'isUp': change >= 0
            })

        return {"markets": result}

    except Exception as e:
        return {
            "markets": [
                {"symbol": "BTC/USDT", "price": "64250.00", "isUp": True},
                {"symbol": "ETH/USDT", "price": "3450.50", "isUp": True}
            ],
            "error": str(e)
        }

# -------------------------------------------------------------
# 2. 24-HOUR TRADE LIMIT CHECK (Max 5 Trades)
# -------------------------------------------------------------
def check_trade_limit(user_id):
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    user_trades_24h = [t for t in trade_logs if t['user_id'] == user_id and t['timestamp'] > last_24h]
    
    if len(user_trades_24h) >= 5:
        return False
    return True

# -------------------------------------------------------------
# 3. MANUAL / BOT TRADE EXECUTION (Futures, Spot & Scalping)
# -------------------------------------------------------------
@app.post("/api/trade/execute")
def execute_trade(data: dict):
    user_id = data.get("user_id", "default_user")
    broker = data.get("broker", "binance").lower()
    symbol = data.get("symbol", "BTC/USDT")
    side = data.get("side", "buy").lower()
    amount = float(data.get("amount", 0.001))
    is_futures = data.get("is_futures", False)
    leverage = int(data.get("leverage", 1))

    # Guard: 5 Trades check
    if not check_trade_limit(user_id):
        return {"status": "error", "message": "24 ghante ki 5 trades ki limit poori ho chuki hai!"}

    try:
        # Dynamic CCXT Exchange Initialization
        exchange_class = getattr(ccxt, broker)
        exchange = exchange_class({
            'apiKey': data.get("api_key"),
            'secret': data.get("secret_key"),
            'options': {'defaultType': 'future' if is_futures else 'spot'}
        })

        if is_futures and hasattr(exchange, 'set_leverage'):
            try:
                exchange.set_leverage(leverage, symbol)
            except Exception as lev_err:
                pass

        # Order Execution
        order = exchange.create_order(symbol, 'market', side, amount)

        # Log History
        trade_record = {
            "trade_id": str(order.get('id', 'N/A')),
            "user_id": user_id,
            "symbol": symbol,
            "side": side.upper(),
            "amount": amount,
            "price": order.get('price', 0),
            "type": f"Futures {leverage}x" if is_futures else "Spot",
            "timestamp": datetime.utcnow()
        }
        trade_logs.append(trade_record)

        return {"status": "success", "order": order, "trades_left": 5 - len([t for t in trade_logs if t['user_id'] == user_id])}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 4. TRADE HISTORY ENDPOINT
# -------------------------------------------------------------
@app.get("/api/trade/history/{user_id}")
def get_trade_history(user_id: str):
    user_history = [t for t in trade_logs if t['user_id'] == user_id]
    return {"history": user_history, "total_trades_today": len(user_history)}
