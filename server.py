from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
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

# Yahan apna Notepad wala edit kiya hua MongoDB link daalna!
MONGO_URI = "mongodb+srv://jameelelctn:<JAmeel4905>@cluster0.jlfvi5y.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['hitech_trading_db']
trades_collection = db['trades']

# -------------------------------------------------------------
# 1. LIVE PRICES (MEXC API - Fast & Crash-Proof)
# -------------------------------------------------------------
@app.get("/api/live-prices")
def get_live_prices():
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        resp = requests.get(url, timeout=10)
        data = resp.json()

        target_markets = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 
            'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'SHIBUSDT', 'DOTUSDT',
            'LINKUSDT', 'NEARUSDT', 'TRXUSDT', 'MATICUSDT', 'BCHUSDT',
            'LTCUSDT', 'PEPEUSDT', 'APTUSDT', 'SUIUSDT', 'FILUSDT',
            'RENDERUSDT', 'ARBUSDT', 'OPUSDT', 'INJUSDT', 'FTMUSDT',
            'SANDUSDT', 'MANAUSDT', 'GALAUSDT', 'WIFUSDT', 'BONKUSDT'
        ]

        data_dict = {item['symbol']: item for item in data if 'symbol' in item}

        result = []
        for sym in target_markets:
            if sym in data_dict:
                item = data_dict[sym]
                last_price = float(item.get('lastPrice', 0))
                change_val = float(item.get('priceChangePercent', 0))

                base = sym.replace('USDT', '')
                result.append({
                    'symbol': f"{base}/USDT",
                    'price': f"{last_price:.4f}" if last_price < 1 else f"{last_price:.2f}",
                    'isUp': change_val >= 0
                })
        return {"markets": result}
    except Exception as e:
        # Agar error aaye toh app crash na ho
        return {
            "markets": [
                {"symbol": "BTC/USDT", "price": "64250.00", "isUp": True},
                {"symbol": "ETH/USDT", "price": "3450.50", "isUp": True}
            ],
            "error": str(e)
        }

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
    user_id = data.get("user_id", "default_user")
    broker = data.get("broker", "binance").lower()
    symbol = data.get("symbol", "BTC/USDT")
    side = data.get("side", "buy").lower()
    amount = float(data.get("amount", 0.001))
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
