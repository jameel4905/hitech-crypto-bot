from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import motor.motor_asyncio
import os
import asyncio

app = FastAPI()

# CORS Middleware (CORS error ko hamesha ke liye hatane ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# MongoDB Connection (Tumhara Atlas URI)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jameelelctn:JameelBot123@cluster0.mongodb.net/?retryWrites=true&w=majority")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.hitech_trading_bot
trades_collection = db.trades

# Data Model for Trade Execution
class TradeRequest(BaseModel):
    user_id: str
    broker: str
    symbol: str
    side: str
    amount: float
    api_key: str
    secret_key: str
    is_futures: bool = True

# 1. Live Prices API (CoinCap se 28+ coins uthane ke liye)
@app.get("/api/live-prices")
async def get_live_prices():
    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.get("https://api.coincap.io/v2/assets?limit=50", timeout=10.0)
            data = response.json()
            
            markets = []
            for item in data.get("data", []):
                symbol = f"{item['symbol']}/USDT"
                price = float(item['priceUsd'])
                change = float(item['changePercent24Hr'] or 0)
                markets.append({
                    "symbol": symbol,
                    "price": f"{price:.2f}" if price > 1 else f"{price:.4f}",
                    "isUp": change >= 0
                })
            return {"status": "success", "markets": markets}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 2. Trade Execute API (10% SL, 20% Target & Trailing Logic ke sath)
@app.post("/api/trade/execute")
async def execute_trade(trade: TradeRequest):
    try:
        # Live price fetch karna current execution price ke liye
        async with httpx.AsyncClient() as client_http:
            res = await client_http.get("https://api.coincap.io/v2/assets?limit=50")
            coins = res.json().get("data", [])
            
            current_price = 100.0 # Default fallback
            coin_base = trade.symbol.split('/')[0].lower()
            for c in coins:
                if c['symbol'].lower() == coin_base:
                    current_price = float(c['priceUsd'])
                    break

        entry_price = current_price
        
        # SL (10%) aur Target (20%) calculation
        if trade.side.lower() == 'buy':
            stop_loss = entry_price * 0.90   # 10% Below
            take_profit = entry_price * 1.20 # 20% Above
        else:
            stop_loss = entry_price * 1.10   # 10% Above for Short
            take_profit = entry_price * 0.80 # 20% Below for Short

        trade_record = {
            "user_id": trade.user_id,
            "broker": trade.broker,
            "symbol": trade.symbol,
            "side": trade.side.upper(),
            "amount": trade.amount,
            "entry_price": entry_price,
            "price": f"{entry_price:.2f}",
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "trailing_active": False, # Trailing state tracker
            "is_futures": trade.is_futures,
            "trade_id": "HT-" + os.urandom(3).hex().upper(),
            "status": "OPEN"
        }

        # MongoDB mein save karna
        await trades_collection.insert_one(trade_record)
        
        return {
            "status": "success",
            "message": "Order placed with 10% SL and 20% Target!",
            "trade_id": trade_record["trade_id"],
            "entry_price": entry_price,
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 3. Trade History API
@app.get("/api/trade/history/{user_id}")
async def get_trade_history(user_id: str):
    try:
        cursor = trades_collection.find({"user_id": user_id}).sort("_id", -1).limit(50)
        history = []
        async for document in cursor:
            document["_id"] = str(document["_id"])
            history.append(document)
        return {"status": "success", "history": history}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Background Task: Trailing Stop Loss Monitor (Price move hote hi SL ko entry par laana)
async def trailing_sl_background_worker():
    while True:
        try:
            async with httpx.AsyncClient() as client_http:
                res = await client_http.get("https://api.coincap.io/v2/assets?limit=50")
                coins = res.json().get("data", [])
                price_map = {c['symbol'].lower(): float(c['priceUsd']) for c in coins}

            # Saari OPEN trades uthao
            open_trades = await trades_collection.find({"status": "OPEN"}).to_list(length=100)
            
            for t in open_trades:
                coin_base = t['symbol'].split('/')[0].lower()
                if coin_base in price_map:
                    curr_p = price_map[coin_base]
                    entry = t['entry_price']
                    
                    # Agar Buy/Long trade hai aur price thoda bhi upar gaya, SL ko entry par shift kar do (Risk-Free)
                    if t['side'] == 'BUY' and curr_p >= entry * 1.01: # 1% upar jaane par
                        if not t.get('trailing_active', False):
                            await trades_collection.update_one(
                                {"_id": t["_id"]},
                                {"$set": {"stop_loss": entry, "trailing_active": True}}
                            )
        except Exception as ex:
            print("Background Worker Error:", ex)
            
        await asyncio.sleep(10) # Har 10 second mein check karega

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trailing_sl_background_worker())
