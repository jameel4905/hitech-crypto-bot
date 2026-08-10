from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import requests
import ccxt
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Yahan in double quotes ke andar apna edit kiya hua link daalna hai
MONGO_URI = "mongodb+srv://jameelelctn:<JAmeel@#4905>@cluster0.jlfvi5y.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['hitech_trading_db']
trades_collection = db['trades']

# -------------------------------------------------------------
# 1. LIVE PRICES (CoinCap se 50 Coins)
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
        return {"markets": [], "error": str(e)}

# -------------------------------------------------------------
# 2. TRADE LIMIT CHECK & EXECUTE
# -------------------------------------------------------------
def check_trade_limit(user_id):
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    count = trades_collection.count_documents({
        "user_id": user_id,
        "timestamp": {"$gte": last_24h}
    })
    return count < 5

@app.post("/api/trade/execute")
def execute_trade(data: dict):
    user_id = data.get("user_id")
    broker = data.get("broker", "binance").lower()
    symbol = data.get("symbol")
    side = data.get("side")
    amount = float(data.get("amount"))
    is_futures = data.get("is_futures", False)

    if not check_trade_limit(user_id):
        return {"status": "error", "message": "24 ghante ki 5 trades ki limit poori ho chuki hai!"}

    try:
        exchange_class = getattr(ccxt, broker)
        exchange = exchange_class({
            'apiKey': data.get("api_key"),
            'secret': data.get("secret_key"),
            'options': {'defaultType': 'future' if is_futures else 'spot'}
        })

        order = exchange.create_order(symbol, 'market', side, amount)

        trade_record = {
            "trade_id": str(order.get('id', 'N/A')),
            "user_id": user_id,
            "symbol": symbol,
            "side": side.upper(),
            "amount": amount,
            "price": order.get('price', 0),
            "timestamp": datetime.utcnow()
        }
        trades_collection.insert_one(trade_record)

        return {"status": "success", "order": order}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 3. TRADE HISTORY
# -------------------------------------------------------------
@app.get("/api/trade/history/{user_id}")
def get_trade_history(user_id: str):
    history = list(trades_collection.find({"user_id": user_id}, {"_id": 0}))
    return {"history": history}
