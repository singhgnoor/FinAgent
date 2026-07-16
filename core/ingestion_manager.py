import os
import time
import pandas as pd
from datetime import datetime, timezone
from typing import Generator, Optional
import yfinance as yf

from core.state import RawSignal, SignalType
from core.log import get_logger

logger = get_logger(__name__)

# Automated mapping from clean asset names -> Yahoo Finance symbols
TICKER_MAP = {
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "RELIANCE": "RELIANCE.NS",
    "HDFC": "HDFCBANK.NS",
    "WIPRO": "WIPRO.NS",
    "TATASTEEL": "TATASTEEL.NS",
}

def get_yfinance_symbol(asset: str) -> str:
    """Helper to convert clean asset name to yfinance ticker symbol."""
    upper_asset = asset.strip().upper()
    return TICKER_MAP.get(upper_asset, f"{upper_asset}.NS")

def fetch_live_yfinance_tick(asset: str) -> Optional[RawSignal]:
    """
    Downloads the latest 1-minute interval price tick from Yahoo Finance
    and packages it into a RawSignal.
    """
    symbol = get_yfinance_symbol(asset)
    logger.info(f"[ingestion_manager] Fetching live yfinance tick for asset={asset} (symbol={symbol})...")
    
    try:
        ticker = yf.Ticker(symbol)
        # Fetch 1 day of 1-minute interval bars
        history = ticker.history(period="1d", interval="1m")
        
        if history.empty:
            logger.warning(f"[ingestion_manager] No market data returned from yfinance for {symbol}")
            return None
        
        # Grab the latest complete 1-minute candle (the last row)
        latest_candle = history.iloc[-1]
        
        payload = {
            "asset": asset.upper(),
            "open": float(latest_candle["Open"]),
            "high": float(latest_candle["High"]),
            "low": float(latest_candle["Low"]),
            "close": float(latest_candle["Close"]),
            "volume": float(latest_candle["Volume"]),
        }
        
        return RawSignal(
            raw_id=f"yf_{asset.lower()}_{int(time.time())}",
            signal_type=SignalType.PRICE_TICK,
            source="yfinance",
            payload=payload,
            received_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.exception(f"[ingestion_manager] Failed to fetch yfinance data for {symbol}: {e}")
        return None

def stream_from_csv(file_path: str, asset: str) -> Generator[RawSignal, None, None]:
    """
    Reads a historical CSV file and yields RawSignal objects row-by-row
    to simulate a streaming market feed.
    """
    logger.info(f"[ingestion_manager] Initializing CSV stream from {file_path} for asset={asset}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")
        
    df = pd.read_csv(file_path)
    
    # Strip whitespace and convert columns to lowercase to make matching robust
    original_cols = list(df.columns)
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Find the correct columns dynamically
    col_mapping = {}
    for target in ["open", "high", "low", "close", "volume"]:
        matched = [c for c in df.columns if target in c]
        if not matched:
            # Fallback check for volume (sometimes written as 'vol')
            if target == "volume":
                matched = [c for c in df.columns if "vol" in c]
            
            if not matched:
                raise ValueError(
                    f"Could not find a column matching '{target}' in CSV file {file_path}. "
                    f"Available columns: {original_cols}"
                )
        col_mapping[target] = matched[0]
        
    # Stream the data row-by-row
    for idx, row in df.iterrows():
        payload = {
            "asset": asset.upper(),
            "open": float(row[col_mapping["open"]]),
            "high": float(row[col_mapping["high"]]),
            "low": float(row[col_mapping["low"]]),
            "close": float(row[col_mapping["close"]]),
            "volume": float(row[col_mapping["volume"]]),
        }
        
        yield RawSignal(
            raw_id=f"csv_{asset.lower()}_{idx}",
            signal_type=SignalType.PRICE_TICK,
            source="csv_stream",
            payload=payload,
            received_at=datetime.now(timezone.utc),
        )
