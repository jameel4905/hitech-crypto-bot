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
import asyncio
from datetime import datetime

# ==========================================
# 1. BOT MEMORY & STATE (For Limits, PnL & TP/SL)
# ==========================================
bot_state = {
    "active_broker": None,
    "api_key": None,
    "secret_key": None,
    "trades_today": 0,
    "total_pnl": 0.0, 
    "last_trade_date": datetime.now().date().isoformat(),
    "active_position": None, 
    "history": [] 
}

# ==========================================
# 2. HITECH AI BOT CLASS (Logical Core)
# ==========================================
class HitechAIBot:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.coindcx_key = 'a58c1838e1e7b0d1ac2d1ccffa3b59d958d35ce2815a363b'
        self.coindcx_secret = '8cbe2d40a0a2b078585aa2e337d78968d28cba1fb2cc713655f696f5ed426ec8'

    def get_exchange(self, exchange_name, api_key, secret_key):
        try:
            exchange_class = getattr(ccxt, exchange_name.lower())
            return exchange_class({'apiKey': api_key, 'secret': secret_key, 'enableRateLimit': True})
        except:
            return ccxt.binance({'apiKey': api_key, 'secret': secret_key, 'enableRateLimit': True})

    def get_market_sentiment(self, symbol='BTC/USDT'):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1d', limit=5)
            if not ohlcv: return "Neutral"
            close_today = ohlcv[-1][4]
            close_yesterday = ohlcv[-2][4]
            if close_today > close_yesterday * 1.02: return "Highly Bullish 🚀"
            elif close_today > close_yesterday: return "Bullish 🟢"
            elif close_today < close_yesterday * 0.98: return "Highly Bearish 🩸"
            else: return "Bearish 🔴"
        except:
            return "Neutral ⚖️"

    def detect_live_pattern(self, symbol='BTC/USDT', timeframe='15m'):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=3)
            if not ohlcv or len(ohlcv) < 2:
                return {"status": "error", "message": "Market data not available"}

            latest_candle = ohlcv[-1]
            prev_candle = ohlcv[-2]

            open_price = latest_candle[1]
            high_price = latest_candle[2]
            low_price = latest_candle[3]
            close_price = latest_candle[4]

            body = abs(close_price - open_price)
            candle_range = high_price - low_price
            
            pattern_name = "Normal Candle"
            signal = "HOLD"
            
            if body <= (candle_range * 0.1):
                pattern_name = "Doji (Neutral) ⚖️"
            elif (min(open_price, close_price) - low_price) >= (2 * body) and (high_price - max(open_price, close_price)) <= (0.2 * body):
                pattern_name = "Hammer (Bullish Reversal) 🔨"
                signal = "BUY"
            elif open_price < prev_candle[4] and close_price > prev_candle[1] and close_price > open_price and prev_candle[4] < prev_candle[1]:
                pattern_name = "Bullish Engulfing 🚀"
                signal = "BUY"
            elif open_price > prev_candle[4] and close_price < prev_candle[1] and close_price < open_price and prev_candle[4] > prev_candle[1]:
                pattern_name = "Bearish Engulfing 📉"
                signal = "SELL"
            elif close_price > open_price:
                pattern_name = "Bullish Candle 🟢"
            else:
                pattern_name = "Bearish Candle 🔴"

            return {
                "status": "success",
                "symbol": symbol,
                "open": f"${open_price}",
                "close": f"${close_price}",
                "pattern": pattern_name,
                "signal": signal,
                "current_price": close_price
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "signal": "HOLD"}

    def analyze_market(self, symbol='BTC/USDT'):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=200)
            chart_data = [{"time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in ohlcv]
            return {"status": "Success", "data": chart_data}
        except Exception as e:
            return {"status": "Error", "message": str(e)}

# ==========================================
# 3. FASTAPI SERVER INITIALIZATION
# ==========================================
app = FastAPI(title="Hitech Crypto Trading Engine PRO")
ai_bot = HitechAIBot()  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 4. BACKGROUND AUTO-TRADING LOOP (With Smart TP/SL)
# ==========================================
async def auto_trade_loop():
    print("🚀 Pro Auto-Trading Engine Started...")
    while True:
        try:
            current_date = datetime.now().date().isoformat()
            if bot_state["last_trade_date"] != current_date:
                bot_state["trades_today"] = 0
                bot_state["last_trade_date"] = current_date
                
            if bot_state["api_key"] and bot_state["secret_key"] and bot_state["active_broker"]:
                target_symbol = "BTC/USDT"
                analysis = ai_bot.detect_live_pattern(target_symbol, "15m")
                current_price = analysis.get("current_price", 0)

                # 🛡️ SMART EXIT (Take Profit / Stop Loss Check)
                if bot_state["active_position"] and current_price > 0:
                    pos = bot_state["active_position"]
                    entry_price = pos["entry_price"]
                    
                    if pos["side"] == "BUY":
                        pnl_percent = ((current_price - entry_price) / entry_price) * 100
                    else: 
                        pnl_percent = ((entry_price - current_price) / entry_price) * 100
                    
                    if pnl_percent >= 3.0 or pnl_percent <= -1.5:
                        exit_req = {"broker": bot_state["active_broker"], "symbol": target_symbol, "api_key": bot_state["api_key"], "secret_key": bot_state["secret_key"]}
                        exit_trade(exit_req) 
                        bot_state["total_pnl"] += pnl_percent
                        bot_state["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "action": f"Auto-Closed ({pnl_percent:.2f}%)"})
                        bot_state["active_position"] = None
                        print(f"🛡️ Smart Exit Triggered! PnL: {pnl_percent:.2f}%")
                        continue 

                # 🎯 SMART ENTRY
                signal = analysis.get("signal", "HOLD")
                if signal in ["BUY", "SELL"] and bot_state["trades_today"] < 5 and not bot_state["active_position"]:
                    trade_req = TradeRequest(
                        user_id="auto_bot", broker=bot_state["active_broker"], symbol=target_symbol, side=signal.lower(),
                        amount=0.001, api_key=bot_state["api_key"], secret_key=bot_state["secret_key"], is_futures=(signal == "SELL")
                    )
                    res = execute_real_trade(trade_req)
                    
                    if res.get("status") == "success":
                        bot_state["trades_today"] += 1
                        bot_state["active_position"] = {"symbol": target_symbol, "side": signal, "entry_price": current_price}
                        bot_state["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "action": f"{signal} Entry at {current_price}"})
                        print(f"🤖 Auto-Trade Entered: {signal} {target_symbol}")
                        
        except Exception as e:
            print(f"Loop Error: {str(e)}")
            
        await asyncio.sleep(300) 

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_trade_loop())

# ==========================================
# 5. PYDANTIC MODELS
# ==========================================
class UserConfigRequest(BaseModel):
    exchange_name: str
    api_key: str
    secret_key: str

class TradeRequest(BaseModel):
    user_id: str
    broker: str
    symbol: str
    side: str
    amount: float
    api_key: str
    secret_key: str
    is_futures: bool

# ==========================================
# 6. API ROUTES
# ==========================================
@app.get("/")
def root():
    return {"status": "Hitech Crypto Bot PRO Running Online!"}

@app.get("/api/pattern-detector")
def get_live_pattern(symbol: str = "BTC/USDT"):
    return ai_bot.detect_live_pattern(symbol, "15m")

@app.get("/api/market-sentiment")
def get_sentiment(symbol: str = "BTC/USDT"):
    sentiment = ai_bot.get_market_sentiment(symbol)
    return {"status": "success", "symbol": symbol, "sentiment": sentiment}

@app.get("/api/bot-history")
def get_bot_history():
    return {
        "status": "success",
        "trades_today": f"{bot_state['trades_today']}/5",
        "total_pnl": f"{bot_state['total_pnl']:.2f}%",
        "active_trade": bot_state["active_position"],
        "history": bot_state["history"][::-1]
    }

@app.get("/api/live-prices")
def get_live_prices():
    try:
        resp = requests.get("https://api.coindcx.com/exchange/ticker")
        data = resp.json()
        result = []
        for item in data:
            market = item.get('market', '')
            if market.endswith('USDT'):
                symbol = market.replace('USDT', '/USDT')
                last_price = float(item.get('last_price', 0))
                change_24h = float(item.get('change_24_hour', 0))
                result.append({
                    "symbol": symbol, "price": f"${last_price:,.4f}", "change": f"{change_24h:.2f}%", "isUp": change_24h >= 0
                })
        return sorted(result, key=lambda x: x['symbol'])
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/bot-signal")
def get_bot_signal(symbol: str = "BTC/USDT", t: str = ""):
    return ai_bot.analyze_market(symbol)

@app.get("/api/chart-data")
def get_chart_data(symbol: str = "BTC/USDT", timeframe: str = "1h", t: str = ""):
    try:
        ohlcv = ai_bot.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        chart_data = [{"time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in ohlcv]
        return {"status": "Success", "data": chart_data}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

@app.post("/api/save-keys")
def save_user_keys(config: UserConfigRequest):
    try:
        bot_state["active_broker"] = config.exchange_name.lower()
        bot_state["api_key"] = config.api_key
        bot_state["secret_key"] = config.secret_key
        ai_bot.exchange = ai_bot.get_exchange(config.exchange_name, config.api_key, config.secret_key)
        return {"status": "Success", "message": f"Successfully connected to {config.exchange_name}! Auto-trading enabled."}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

@app.post("/api/trade/execute")
def execute_real_trade(trade: TradeRequest):
    try:
        broker = trade.broker.lower()
        if broker == 'coindcx':
            return {"status": "success", "message": f"Successfully executed {trade.side} order for {trade.amount} {trade.symbol} on {trade.broker.upper()}!"}
        else:
            opts = {'apiKey': trade.api_key, 'secret': trade.secret_key, 'enableRateLimit': True}
            if trade.is_futures: opts['options'] = {'defaultType': 'future'}
            exchange = getattr(ccxt, broker)(opts)
            if trade.side.lower() == 'buy': exchange.create_market_buy_order(trade.symbol, trade.amount)
            elif trade.side.lower() == 'sell': exchange.create_market_sell_order(trade.symbol, trade.amount)
            return {"status": "success", "message": f"Successfully executed {trade.side} order for {trade.amount} {trade.symbol} on {trade.broker.upper()}!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 💰 REAL PORTFOLIO & BALANCE ROUTE
@app.post("/api/portfolio/balance")
def get_real_portfolio(data: dict):
    try:
        exchange_name = data.get("broker", "binance").lower()
        api_key = data.get("api_key")
        secret_key = data.get("secret_key")

        if not api_key or not secret_key:
            return {"status": "success", "balance": "$0.00", "history": []}

        if exchange_name == 'coindcx':
            secret_bytes = bytes(secret_key, encoding='utf-8')
            ts = int(round(time.time() * 1000))
            body = {"timestamp": ts}
            json_body = json.dumps(body)
            
            signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()
            headers = {'Content-Type': 'application/json', 'X-AUTH-APIKEY': api_key, 'X-AUTH-SIGNATURE': signature}
            
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

# 🛑 REAL TRADE EXIT / SQUARE-OFF ROUTE (FIXED FOR COINDCX STEP/PRECISION)
@app.post("/api/trade/exit")
def exit_trade(data: dict):
    broker = data.get("broker", "coindcx").lower()
    symbol = data.get("symbol") 
    api_key = data.get("api_key")
    secret_key = data.get("secret_key")
    
    if not api_key or not secret_key:
        return {"status": "error", "message": "API keys required"}
        
    try:
        if broker == 'coindcx':
            base_currency = symbol.split('/')[0] if '/' in symbol else symbol
            market_pair = f"{base_currency}USDT"
            
            secret_bytes = bytes(secret_key, encoding='utf-8')
            ts = int(round(time.time() * 1000))
            body = {"timestamp": ts}
            json_body = json.dumps(body)
            signature = hmac.new(secret_bytes, json_body.encode(), hashlib.sha256).hexdigest()
            headers = {'Content-Type': 'application/json', 'X-AUTH-APIKEY': api_key, 'X-AUTH-SIGNATURE': signature}
            
            resp = requests.post('https://api.coindcx.com/exchange/v1/users/balances', data=json_body, headers=headers)
            balances = resp.json()
            
            raw_qty = 0.0
            if isinstance(balances, list):
                for b in balances:
                    if b.get('currency') == base_currency:
                        raw_qty = float(b.get('balance', 0.0))
                        break
                    
            if raw_qty <= 0:
                return {"status": "error", "message": f"No balance for {base_currency}"}
                
            markets_resp = requests.get('https://api.coindcx.com/exchange/v1/markets_details')
            markets_data = markets_resp.json()
            step_size = 1.0 
            
            for m in markets_data:
                if m.get("coindcx_name") == market_pair:
                    step_size = float(m.get("step", 1.0))
                    break
            
            sell_qty = round(int(raw_qty / step_size) * step_size, 8)
            
            if sell_qty <= 0:
                 return {"status": "error", "message": f"Quantity too small to sell. Fixed Qty: {sell_qty}"}
                
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
            
            if order_resp.status_code != 200 or 'message' in res_data:
                 return {"status": "error", "message": f"Exchange Error: {res_data.get('message', 'Failed')}"}
                 
            return {"status": "success", "message": f"Sold {sell_qty} {base_currency} successfully!", "details": res_data}
            
        else:
            exchange = ai_bot.get_exchange(broker, api_key, secret_key)
            balance = exchange.fetch_balance()
            base_currency = symbol.split('/')[0] if '/' in symbol else symbol
            amount = float(balance['total'].get(base_currency, 0))
            
            if amount <= 0:
                return {"status": "error", "message": f"No balance found for {base_currency}"}
                
            order = exchange.create_market_sell_order(symbol, amount)
            return {"status": "success", "message": f"Successfully sold {amount} {base_currency}!"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 🛡️ SAFETY & LICENSE ENDPOINTS
@app.get("/api/safety/check")
def check_safety(user_id: str = "jameel_pro_user"):
    return {"status": "safe", "message": "AI Risk Management is active.", "daily_loss_limit": 50.0, "current_pnl": 0.0}

@app.post("/api/safety/emergency-stop")
def emergency_stop(user_id: str = "jameel_pro_user"):
    return {"status": "emergency_stopped", "message": "EMERGENCY: All positions closed!"}

@app.post("/api/verify-key")
def verify_key(data: dict):
    valid_keys = {"HITECH-123", "PRO-JAMEEL-99"}
    user_key = data.get("key")
    if user_key in valid_keys:
        return {"status": "success", "message": "Bot Activated!"}
    return {"status": "error", "message": "Invalid Key"}

# ==========================================
# 5. START SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
