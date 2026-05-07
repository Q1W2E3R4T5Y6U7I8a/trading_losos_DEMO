"""
MA Crossover Strategy - Signal generation for simulation
"""

import pandas as pd

FAST_MA = 10
SLOW_MA = 30


def get_signal(symbol, df):
    """Generate MA crossover signal from rates DataFrame"""
    if df is None or len(df) < SLOW_MA + 5:
        return None
    
    fast_ma = df["close"].rolling(FAST_MA).mean()
    slow_ma = df["close"].rolling(SLOW_MA).mean()
    
    if len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    
    if fast_ma.iloc[-2] <= slow_ma.iloc[-2] and fast_ma.iloc[-1] > slow_ma.iloc[-1]:
        return "BUY"
    elif fast_ma.iloc[-2] >= slow_ma.iloc[-2] and fast_ma.iloc[-1] < slow_ma.iloc[-1]:
        return "SELL"
    return None