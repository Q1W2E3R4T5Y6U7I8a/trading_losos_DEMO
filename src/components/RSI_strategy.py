"""
RSI Mean Reversion Strategy - Signal generation for simulation
"""

import pandas as pd

RSI_PERIOD = 14
RSI_OVERSOLD = 15
RSI_OVERBOUGHT = 85


def get_signal(symbol, df):
    """Generate RSI signal from rates DataFrame"""
    if df is None or len(df) < RSI_PERIOD + 10:
        return None
    
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    if len(rsi) > 0:
        current_rsi = rsi.iloc[-1]
        if not pd.isna(current_rsi):
            if current_rsi < RSI_OVERSOLD:
                return "BUY"
            elif current_rsi > RSI_OVERBOUGHT:
                return "SELL"
    return None