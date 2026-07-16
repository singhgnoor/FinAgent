import os
import sys
import time
from datetime import datetime, timezone

from core.log import setup_logging, get_logger
from core.state import RawSignal, SignalType
from core.graph import run_once
from core.ingestion_manager import fetch_live_yfinance_tick, stream_from_csv

logger = get_logger(__name__)

def run_live_feed(asset: str):
    """Fetches a live tick from yfinance and runs the pipeline once."""
    raw_signal = fetch_live_yfinance_tick(asset)
    if not raw_signal:
        print(f"[Main] Error: Could not fetch live data for {asset}.")
        return
        
    print(f"\n[Main] Live Tick Ingested: {raw_signal.payload['asset']} | Close: {raw_signal.payload['close']:.2f}")
    
    # Run the pipeline
    final_state = run_once(raw_signal)
    
    # Print the synthesized trade recommendation
    decision = final_state.get("artefact")
    if decision:
        print(f"\n=== TRADE DECISION FOR {asset} ===")
        print(f"Action: {decision.action.value}")
        print(f"Confidence: {decision.confidence_score}% ({decision.confidence_level.value})")
        print("Evidence:")
        for b in decision.evidence_bullets:
            print(f"  - {b}")
    else:
        print("[Main] No trade decision generated.")

def run_simulated_feed(file_path: str, asset: str, delay: float = 2.0):
    """Streams ticks from a CSV file row-by-row and runs the pipeline."""
    try:
        signal_generator = stream_from_csv(file_path, asset)
        print(f"\n[Main] Starting historical simulation for {asset} from {file_path}...")
        
        for idx, raw_signal in enumerate(signal_generator):
            print(f"\n[Sim] Processing Tick #{idx+1}: Close: {raw_signal.payload['close']:.2f} | Volume: {raw_signal.payload['volume']}")
            
            # Run the pipeline for this tick
            final_state = run_once(raw_signal)
            
            # Print the decision
            decision = final_state.get("artefact")
            if decision:
                print(f"  [Decision] Action: {decision.action.value} | Confidence: {decision.confidence_score}%")
            else:
                print("  [Decision] No action triggered.")
                
            # Pause to simulate a real-time streaming feed
            time.sleep(delay)
            
    except Exception as e:
        print(f"[Main] Error during simulation: {e}")

def main():
    # Initialize logging FIRST (mandated by Gurnoor's setup)
    setup_logging(run_id="finagent_live")
    logger.info("[main] FinAgent pipeline starting")
    
    print("=" * 60)
    print("           FINAGENT INGESTION CONSOLE          ")
    print("=" * 60)
    print("Select Ingestion Modality:")
    print("1. Live Market Feed (via yfinance)")
    print("2. Simulated Market Feed (via CSV file)")
    
    try:
        choice = input("\nEnter choice (1-2): ").strip()
        
        if choice == "1":
            asset = input("Enter asset symbol (e.g. TCS, INFY, RELIANCE): ").strip()
            if not asset:
                print("Asset symbol cannot be empty.")
                return
            run_live_feed(asset)
            
        elif choice == "2":
            file_path = input("Enter path to historical CSV: ").strip()
            asset = input("Enter asset symbol for these candles (e.g. INFY): ").strip()
            
            if not file_path or not asset:
                print("CSV path and Asset symbol are required.")
                return
            run_simulated_feed(file_path, asset)
            
        else:
            print("Invalid choice.")
            
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        
    logger.info("[main] FinAgent pipeline complete")

if __name__ == "__main__":
    main()
