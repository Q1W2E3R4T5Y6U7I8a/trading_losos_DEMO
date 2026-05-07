"""
MA Crossover Strategy - Historical Simulation Mode
Reads MT5 data but executes NO real trades - purely simulation
"""

import os
import time
import json
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

LOGIN    = int(os.getenv("LOGIN"))
PASSWORD = os.getenv("PASSWORD")
SERVER   = os.getenv("SERVER")

SYMBOLS = [
    "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD",
    "EURGBP","EURJPY","EURCHF","EURAUD","EURCAD","EURNZD",
    "GBPJPY","GBPCHF","GBPAUD","GBPCAD","GBPNZD",
    "AUDJPY","AUDCHF","AUDCAD","AUDNZD",
    "CADJPY","CADCHF","CHFJPY","NZDJPY","NZDCAD",
]

FAST_MA     = 10
SLOW_MA     = 30
VOLUME      = 0.01
CLOSE_HOURS = 4
TIMEFRAME   = mt5.TIMEFRAME_M5
STEP        = timedelta(minutes=5)

# Use simulation data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "live_data.json")


class HistoricalDataCache:
    """Cache historical data from MT5 for simulation"""
    def __init__(self):
        self.cache = {}
        self.loaded = False
    
    def load_all_data(self, hours_back=72):
        """Pre-load all historical data"""
        if self.loaded:
            return
        
        print("  📥 Loading historical data from MT5...")
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        for symbol in SYMBOLS:
            rates = mt5.copy_rates_range(symbol, TIMEFRAME, start_time, end_time)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                self.cache[symbol] = df
                print(f"    {symbol}: {len(df)} candles")
            else:
                self.cache[symbol] = pd.DataFrame()
        
        self.loaded = True
    
    def get_rates_at_time(self, symbol, sim_time, count=100):
        """Get rates up to simulated time"""
        if symbol not in self.cache or self.cache[symbol].empty:
            return None
        df = self.cache[symbol]
        mask = df['time'] <= sim_time
        available = df[mask]
        if len(available) < count:
            return None
        return available.tail(count)
    
    def get_price_at_time(self, symbol, sim_time):
        """Get price at simulated time"""
        df = self.get_rates_at_time(symbol, sim_time, 1)
        if df is not None and len(df) > 0:
            return float(df['close'].iloc[-1])
        return None
    
    def get_candle_time(self, symbol, sim_time):
        """Get latest candle time at simulation time"""
        df = self.get_rates_at_time(symbol, sim_time, 1)
        if df is not None and len(df) > 0:
            return df['time'].iloc[-1]
        return None


data_cache = HistoricalDataCache()


def get_signal(symbol, sim_time):
    """Get MA signal from cached historical data"""
    df = data_cache.get_rates_at_time(symbol, sim_time, 100)
    if df is None or len(df) < SLOW_MA + 1:
        return None
    
    fast = df["close"].rolling(FAST_MA).mean()
    slow = df["close"].rolling(SLOW_MA).mean()
    
    if len(fast) < 2 or len(slow) < 2:
        return None
    
    crossed_up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
    crossed_down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
    
    return "BUY" if crossed_up else "SELL" if crossed_down else None


def get_close_price(symbol, sim_time):
    return data_cache.get_price_at_time(symbol, sim_time)


def calc_pnl(symbol, order_type, open_price, close_price):
    """P&L in USD for 0.01 lot simulation"""
    delta = close_price - open_price if order_type == "BUY" else open_price - close_price
    
    if "JPY" in symbol:
        pips = delta * 100
    else:
        pips = delta * 10_000
    
    pip_value = 0.10  # Standard for 0.01 lot
    return round(pips * pip_value, 4)


def save_data(sim_time, profits, history, trades, open_positions, progress):
    payload = {
        "timestamp": sim_time.timestamp(),
        "profits": profits,
        "history": history,
        "trades": trades,
        "open_positions": open_positions,
        "symbols": SYMBOLS,
        "progress": progress,
    }
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, DATA_FILE)


def main():
    print("=" * 70)
    print("  MA CROSSOVER STRATEGY - HISTORICAL SIMULATION")
    print("  NO REAL TRADING - Using cached MT5 data")
    print("=" * 70)
    
    if not mt5.initialize():
        print("  ❌ MT5 init failed")
        return
    if not mt5.login(LOGIN, password=PASSWORD, server=SERVER):
        print("  ❌ Login failed")
        mt5.shutdown()
        return
    print("  ✅ MT5 connected\n")
    
    # Load all historical data once
    data_cache.load_all_data(hours_back=72)
    
    # Simulation time: run from 24 hours ago to now
    sim_start = datetime.now() - timedelta(hours=24)
    current_sim = sim_start
    end_time = datetime.now()
    
    positions = {}
    cumulative_pnl = {s: 0.0 for s in SYMBOLS}
    trade_history = {s: [] for s in SYMBOLS}
    closed_trades = []
    last_candle = {}
    
    print(f"  📅 SIMULATION: {sim_start.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%H:%M')}")
    print(f"  📁 DATA: {DATA_FILE}\n")
    
    try:
        while current_sim <= end_time:
            for symbol in SYMBOLS:
                pos = positions.get(symbol)
                
                # Close expired positions
                if pos and current_sim >= pos["close_time"]:
                    close_price = get_close_price(symbol, pos["close_time"])
                    if close_price is None:
                        close_price = pos["open_price"]
                    
                    pnl = calc_pnl(symbol, pos["type"], pos["open_price"], close_price)
                    cumulative_pnl[symbol] += pnl
                    
                    trade_history[symbol].append(
                        (pos["close_time"].timestamp(), round(cumulative_pnl[symbol], 4))
                    )
                    
                    closed_trades.append({
                        "symbol": symbol,
                        "type": pos["type"],
                        "open_time": pos["open_time"].timestamp(),
                        "close_time": pos["close_time"].timestamp(),
                        "open_price": pos["open_price"],
                        "close_price": close_price,
                        "pnl": pnl,
                    })
                    
                    print(f"  CLOSE {symbol:8s} {pos['type']:4s}  PnL: ${pnl:+.2f}")
                    del positions[symbol]
                    pos = None
                
                # Open new positions on candle boundaries
                if pos is None:
                    candle_time = data_cache.get_candle_time(symbol, current_sim)
                    if candle_time and last_candle.get(symbol) != candle_time:
                        signal = get_signal(symbol, current_sim)
                        if signal:
                            price = get_close_price(symbol, current_sim)
                            if price:
                                positions[symbol] = {
                                    "type": signal,
                                    "open_price": price,
                                    "open_time": current_sim,
                                    "close_time": current_sim + timedelta(hours=CLOSE_HOURS),
                                }
                                last_candle[symbol] = candle_time
                                
                                trade_history[symbol].append(
                                    (current_sim.timestamp(), round(cumulative_pnl[symbol], 4))
                                )
                                print(f"  OPEN  {symbol:8s} {signal:4s}  @ {price:.5f}  [{current_sim.strftime('%H:%M')}]")
            
            # Build live profits with unrealized PnL
            live_profits = {}
            open_positions = {}
            for symbol in SYMBOLS:
                pos = positions.get(symbol)
                if pos:
                    cur = get_close_price(symbol, current_sim) or pos["open_price"]
                    unreal = calc_pnl(symbol, pos["type"], pos["open_price"], cur)
                    live_profits[symbol] = round(cumulative_pnl[symbol] + unreal, 4)
                    open_positions[symbol] = {
                        "type": pos["type"],
                        "open_time": pos["open_time"].timestamp(),
                        "close_time": pos["close_time"].timestamp(),
                        "open_price": pos["open_price"],
                        "unrealized_pnl": round(unreal, 4),
                    }
                else:
                    live_profits[symbol] = round(cumulative_pnl[symbol], 4)
            
            progress = (current_sim - sim_start).total_seconds() / 86400
            save_data(current_sim, live_profits, trade_history, closed_trades[-200:], open_positions, progress)
            
            total = sum(cumulative_pnl.values())
            print(f"\r  SIM {current_sim.strftime('%H:%M:%S')}  |  TOTAL: ${total:+8.2f}  |  OPEN: {len(positions):2}  |  TRADES: {len(closed_trades):3}  |  {progress*100:.1f}%", end="", flush=True)
            
            current_sim += STEP
            time.sleep(0.01)  # Smooth simulation
            
    except KeyboardInterrupt:
        print("\n\n  🛑 Simulation stopped")
    
    # Final summary
    print("\n\n" + "=" * 70)
    print("  MA STRATEGY - SIMULATION SUMMARY")
    print("=" * 70)
    total_pnl = sum(cumulative_pnl.values())
    wins = [t for t in closed_trades if t["pnl"] > 0]
    print(f"  Total closed trades: {len(closed_trades)}")
    print(f"  Winning trades: {len(wins)}")
    print(f"  Losing trades: {len(closed_trades) - len(wins)}")
    if closed_trades:
        print(f"  Win rate: {len(wins)/len(closed_trades)*100:.1f}%")
        print(f"  Total P&L: ${total_pnl:+.2f}")
        print(f"  Best trade: ${max(t['pnl'] for t in closed_trades):+.2f}")
        print(f"  Worst trade: ${min(t['pnl'] for t in closed_trades):+.2f}")
    print("=" * 70)
    
    mt5.shutdown()
    print(f"\n  ✅ Simulation complete! Data saved to {DATA_FILE}")


if __name__ == "__main__":
    main()