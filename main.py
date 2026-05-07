"""
Main Launcher - Historical Simulation Mode
Runs both strategies on historical MT5 data - NO REAL TRADING
"""

import subprocess
import sys
import time
import os
import json
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "CADJPY", "CADCHF", "CHFJPY", "NZDJPY", "NZDCAD",
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


class HistoricalSimulator:
    """Simulates trading on historical data"""
    
    def __init__(self, strategy_name, get_signal_func):
        self.strategy_name = strategy_name
        self.get_signal = get_signal_func
        self.positions = {}
        self.cumulative_pnl = {s: 0.0 for s in SYMBOLS}
        self.trade_history = {s: [] for s in SYMBOLS}
        self.closed_trades = []
        self.data_cache = {}
        
    def load_historical_data(self, hours_back=72):
        """Load historical data from MT5"""
        print(f"  Loading {hours_back} hours of data for {self.strategy_name}...")
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        for symbol in SYMBOLS:
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, start_time, end_time)
            if rates is not None and len(rates) > 0:
                # Convert numpy array to list of dicts for JSON serialization
                rates_list = []
                for r in rates:
                    rates_list.append({
                        'time': r[0],  # timestamp
                        'open': float(r[1]),
                        'high': float(r[2]),
                        'low': float(r[3]),
                        'close': float(r[4]),
                        'tick_volume': int(r[5]),
                        'spread': int(r[6]),
                        'real_volume': int(r[7])
                    })
                self.data_cache[symbol] = rates_list
                print(f"    {symbol}: {len(rates_list)} candles")
            else:
                self.data_cache[symbol] = []
                print(f"    {symbol}: FAILED")
        
    def get_price_at_time(self, symbol, sim_time):
        """Get price at specific simulated time"""
        rates = self.data_cache.get(symbol, [])
        sim_timestamp = int(sim_time.timestamp())
        for rate in reversed(rates):
            if rate['time'] <= sim_timestamp:
                return rate['close']
        return None
    
    def get_rates_at_time(self, symbol, sim_time, count=100):
        """Get historical rates up to sim_time as DataFrame"""
        rates = self.data_cache.get(symbol, [])
        result = []
        sim_timestamp = int(sim_time.timestamp())
        for rate in reversed(rates):
            if rate['time'] <= sim_timestamp:
                result.insert(0, rate)
                if len(result) >= count:
                    break
        if len(result) >= count:
            # Return as DataFrame for compatibility with strategy signals
            df = pd.DataFrame(result)
            return df
        return None
    
    def calc_pnl(self, symbol, order_type, open_price, close_price):
        """Calculate P&L for 0.01 lot"""
        if order_type == "BUY":
            delta = close_price - open_price
        else:
            delta = open_price - close_price
        
        if "JPY" in symbol:
            pips = delta * 100
        else:
            pips = delta * 10000
        return round(pips * 0.10, 4)
    
    def save_progress(self, current_time, start_time, hours):
        """Save simulation data for viewer"""
        elapsed = (current_time - start_time).total_seconds() / 3600
        progress = min(1.0, elapsed / hours)
        
        live_profits = {}
        for symbol in SYMBOLS:
            if symbol in self.positions:
                pos = self.positions[symbol]
                current_price = self.get_price_at_time(symbol, current_time) or pos['open_price']
                unrealized = self.calc_pnl(symbol, pos['type'], pos['open_price'], current_price)
                live_profits[symbol] = round(self.cumulative_pnl[symbol] + unrealized, 4)
            else:
                live_profits[symbol] = round(self.cumulative_pnl[symbol], 4)
        
        # Update trade history for equity curve
        for symbol in SYMBOLS:
            self.trade_history[symbol].append(
                (current_time.timestamp(), live_profits[symbol])
            )
            # Keep only last 500 points
            if len(self.trade_history[symbol]) > 500:
                self.trade_history[symbol] = self.trade_history[symbol][-500:]
        
        open_positions = {}
        for symbol, pos in self.positions.items():
            current_price = self.get_price_at_time(symbol, current_time) or pos['open_price']
            unrealized = self.calc_pnl(symbol, pos['type'], pos['open_price'], current_price)
            open_positions[symbol] = {
                'type': pos['type'],
                'open_time': pos['open_time'].timestamp(),
                'close_time': pos['close_time'].timestamp(),
                'open_price': pos['open_price'],
                'unrealized_pnl': round(unrealized, 4)
            }
        
        data = {
            'timestamp': current_time.timestamp(),
            'profits': live_profits,
            'history': self.trade_history,
            'trades': self.closed_trades[-200:],
            'open_positions': open_positions,
            'symbols': SYMBOLS,
            'progress': progress,
            'strategy': self.strategy_name
        }
        
        filepath = os.path.join(DATA_DIR, f"{self.strategy_name.lower()}_sim_data.json")
        with open(filepath, 'w') as f:
            json.dump(data, f)
    
    def print_summary(self):
        """Print final summary"""
        print(f"\n\n{'='*70}")
        print(f"  {self.strategy_name} - SUMMARY")
        print(f"{'='*70}")
        total = sum(self.cumulative_pnl.values())
        wins = [t for t in self.closed_trades if t['pnl'] > 0]
        print(f"  Total Trades: {len(self.closed_trades)}")
        print(f"  Winning: {len(wins)}  Losing: {len(self.closed_trades)-len(wins)}")
        if self.closed_trades:
            print(f"  Win Rate: {len(wins)/len(self.closed_trades)*100:.1f}%")
            print(f"  Total P&L: ${total:+.2f}")
            print(f"  Best: ${max(t['pnl'] for t in self.closed_trades):+.2f}")
            print(f"  Worst: ${min(t['pnl'] for t in self.closed_trades):+.2f}")
        print(f"{'='*70}\n")
    
    def run_simulation(self, hours=24):
        """Run the simulation"""
        self.load_historical_data(hours + 48)
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        current_time = start_time
        
        last_candle = {}
        step = timedelta(minutes=1)
        
        print(f"\n{'='*70}")
        print(f"  {self.strategy_name} - Simulating {hours} hours")
        print(f"{'='*70}\n")
        
        while current_time <= end_time:
            for symbol in SYMBOLS:
                # Close expired positions (4 hour hold)
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    if current_time >= pos['close_time']:
                        close_price = self.get_price_at_time(symbol, current_time)
                        if close_price:
                            pnl = self.calc_pnl(symbol, pos['type'], pos['open_price'], close_price)
                            self.cumulative_pnl[symbol] += pnl
                            self.closed_trades.append({
                                'symbol': symbol, 'type': pos['type'],
                                'open_time': pos['open_time'].timestamp(),
                                'close_time': current_time.timestamp(),
                                'open_price': pos['open_price'],
                                'close_price': close_price, 'pnl': pnl
                            })
                            # Update trade history for equity curve
                            self.trade_history[symbol].append(
                                (current_time.timestamp(), self.cumulative_pnl[symbol])
                            )
                            print(f"  CLOSE {symbol:8s} {pos['type']:4s}  PnL: ${pnl:+.2f}")
                            del self.positions[symbol]
                
                # Check for new signals on candle boundaries
                if symbol not in self.positions:
                    df = self.get_rates_at_time(symbol, current_time, 100)
                    if df is not None:
                        last_time = df['time'].iloc[-1]
                        if last_candle.get(symbol) != last_time:
                            signal = self.get_signal(symbol, df)
                            if signal:
                                price = self.get_price_at_time(symbol, current_time)
                                if price:
                                    self.positions[symbol] = {
                                        'type': signal, 'open_price': price,
                                        'open_time': current_time,
                                        'close_time': current_time + timedelta(hours=4)
                                    }
                                    # Record open in trade history
                                    self.trade_history[symbol].append(
                                        (current_time.timestamp(), self.cumulative_pnl[symbol])
                                    )
                                    print(f"  OPEN  {symbol:8s} {signal:4s}  @ {price:.5f}  [{current_time.strftime('%H:%M')}]")
                            last_candle[symbol] = last_time
            
            # Save progress periodically
            self.save_progress(current_time, start_time, hours)
            
            # Progress display
            elapsed = (current_time - start_time).total_seconds() / 3600
            progress = min(1.0, elapsed / hours)
            total = sum(self.cumulative_pnl.values())
            print(f"\r  [{current_time.strftime('%H:%M:%S')}]  PnL: ${total:+8.2f}  |  Open: {len(self.positions):2}  |  Trades: {len(self.closed_trades):3}  |  {progress*100:.1f}%", end="", flush=True)
            
            current_time += step
            time.sleep(0.01)
        
        self.save_progress(end_time, start_time, hours)
        self.print_summary()


def ma_signal(symbol, df):
    """MA Crossover signal from DataFrame"""
    if df is None or len(df) < 35:
        return None
    
    fast_ma = df['close'].rolling(10).mean()
    slow_ma = df['close'].rolling(30).mean()
    
    if len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    
    if fast_ma.iloc[-2] <= slow_ma.iloc[-2] and fast_ma.iloc[-1] > slow_ma.iloc[-1]:
        return "BUY"
    elif fast_ma.iloc[-2] >= slow_ma.iloc[-2] and fast_ma.iloc[-1] < slow_ma.iloc[-1]:
        return "SELL"
    return None


def rsi_signal(symbol, df):
    """RSI signal from DataFrame"""
    if df is None or len(df) < 25:
        return None
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]):
        current_rsi = rsi.iloc[-1]
        if current_rsi < 15:
            return "BUY"
        elif current_rsi > 85:
            return "SELL"
    return None


def main():
    print("=" * 70)
    print("  HISTORICAL SIMULATION - NO REAL TRADING")
    print("=" * 70)
    
    hours_input = input("\n  Hours to simulate (default 24, max 168): ").strip()
    hours = int(hours_input) if hours_input else 24
    hours = max(1, min(168, hours))
    
    if not mt5.initialize():
        print("  ❌ MT5 initialization failed. Make sure MT5 is running.")
        return
    
    print(f"\n  Simulating {hours} hours of historical data...\n")
    
    # Run MA Simulation
    ma_sim = HistoricalSimulator("MA", ma_signal)
    ma_sim.run_simulation(hours)
    
    # Run RSI Simulation  
    rsi_sim = HistoricalSimulator("RSI", rsi_signal)
    rsi_sim.run_simulation(hours)
    
    mt5.shutdown()
    
    # Launch viewer
    print("\n  🚀 Launching 3D Viewer...")
    components_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "components")
    viewer_path = os.path.join(components_dir, "Viewer.py")
    
    if os.path.exists(viewer_path):
        viewer = subprocess.Popen([sys.executable, viewer_path])
        print("\n  ✅ Simulations complete!")
        print(f"  📊 Data saved to: {DATA_DIR}")
        print("  🌐 Viewer: http://localhost:8765")
        print("\n  Press Enter to stop viewer and exit...")
        input()
        viewer.terminate()
    else:
        print(f"\n  ⚠️ Viewer not found at: {viewer_path}")
        print("  Simulations complete! Check the data folder for results.")
    
    print("\n  Done!")


if __name__ == "__main__":
    main()