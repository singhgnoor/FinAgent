import os
import sys
import re
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Force Hugging Face to run in offline mode using local cache to prevent network timeouts
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Ensure path is set
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def mock_get_llm():
    """Mock the LLM wrapper so it runs end-to-end offline with dynamic price reasoning."""
    from agents.analysis import _AnalysisOutput
    from core.state import Classification, TimeHorizon

    mock_llm = MagicMock()
    
    def mock_with_structured_output(schema_cls, *args, **kwargs):
        mock_chain = MagicMock()
        
        def mock_invoke(input_dict, *args, **kwargs):
            # 1. Handle Analysis Agent Output
            if schema_cls.__name__ == "_AnalysisOutput":
                # Convert prompt input to text
                if hasattr(input_dict, "to_string"):
                    text = input_dict.to_string()
                else:
                    text = str(input_dict)
                
                # Use regex to find close price in the text
                match = re.search(r"(?:close\):|close=)\s*([\d.]+)", text, re.IGNORECASE)
                
                classification = Classification.NEUTRAL
                confidence = 65
                rationale = "TCS is trading inside its normal daily range. Technical indicators are neutral."
                
                if match:
                    close_price = float(match.group(1))
                    
                    # Simulated bullish breakout rule (BUY trigger)
                    if close_price > 2213.5:
                        classification = Classification.BULLISH
                        confidence = 85
                        rationale = f"TCS broke out above its moving average at Rs.{close_price:.2f}. RSI(14) shows strong upward momentum."
                        
                    # Simulated bearish breakdown rule (SELL trigger)
                    elif close_price < 2213.3:
                        classification = Classification.BEARISH
                        confidence = 80
                        rationale = f"TCS broke down below key support levels to Rs.{close_price:.2f}. Volatility is expanding downwards."
                
                return _AnalysisOutput(
                    classification=classification,
                    rationale=rationale,
                    statement="TCS indicates a clear trend direction.",
                    supporting_evidence=["Price action is active near technical bands."],
                    confidence_score=confidence,
                    time_horizon=TimeHorizon.SHORT_TERM
                )
            
            # 2. Handle Decision Agent Output
            elif schema_cls.__name__ == "_DecisionAdvice":
                from agents.decision import _DecisionAdvice
                return _DecisionAdvice(
                    risk_flags=["Volatility expansion", "Slippage risk"],
                    commentary="AI agent detects a trend phase. Advised to execute trade."
                )
                
            return MagicMock()

        # Wire up mock invocation and pipeline pipe operators
        mock_chain.invoke = mock_invoke
        mock_chain.side_effect = mock_invoke
        mock_chain.__or__ = MagicMock(return_value=mock_chain)
        return mock_chain

    mock_llm.with_structured_output = mock_with_structured_output
    return mock_llm

def check_setup():
    """Verify and initialize mock RAG database and mock CSV for backtesting."""
    import config
    from rag.vector_store import get_vector_store
    from langchain_core.documents import Document
    
    # 1. Initialize RAG
    store = get_vector_store()
    if store.is_empty:
        print("\n[RAG] Local FAISS index is empty. Initializing mock RAG entries for TCS...")
        os.makedirs(config.KB_DOCS_DIR, exist_ok=True)
        
        sample_doc_path = config.KB_DOCS_DIR / "tcs_outlook_report.txt"
        sample_content = """
        TATA CONSULTANCY SERVICES (TCS) - OUTLOOK REPORT
        TCS reported strong quarterly revenue growth, driven by key wins in cloud migration and digital transformation services.
        The management has outlined a robust pipeline for the rest of FY27, specifically highlighting a multi-year $1B cloud migration deal with a European financial institution.
        The company's expansion into Conversational AI and generative workflows is expected to increase average revenue per user (ARPU) across enterprise contracts by 12% over the next two quarters.
        While TCS's growth trajectory remains bullish, key valuation risks include salary inflation in high-skill software roles, potential currency headwinds, and competitor pricing on medium-scale contracts.
        """
        with open(sample_doc_path, "w", encoding="utf-8") as f:
            f.write(sample_content)
            
        metadata = {
            "doc_name": "tcs_outlook_report.txt",
            "section": "Financial Outlook",
            "page": 1,
            "chunk_type": "narrative",
            "doc_date": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat()
        }
        
        chunks = [
            Document(page_content=f"[tcs_outlook_report.txt | Section: {metadata['section']}]\n{sample_content}", metadata=metadata)
        ]
        
        store.add_documents(chunks)
        store.save()
        print("[RAG] Successfully built local FAISS index with TCS outlook records!")

    # 2. Write a mock CSV file for backtesting simulation
    os.makedirs(config.DATA_DIR, exist_ok=True)
    backtest_csv_path = config.DATA_DIR / "backtest_candles.csv"
    if not os.path.exists(backtest_csv_path):
        print("[Backtest] Creating sample historical CSV candles at data/backtest_candles.csv...")
        csv_data = (
            "Timestamp,Open,High,Low,Close,Volume\n"
            "2026-07-01 10:00:00, 2213.0, 2213.5, 2212.8, 2213.0, 5000\n" # Hold
            "2026-07-01 10:01:00, 2213.0, 2213.4, 2213.0, 2213.2, 4500\n" # Hold
            "2026-07-01 10:02:00, 2213.2, 2214.2, 2213.2, 2214.0, 7000\n" # BUY (> 2213.5)
            "2026-07-01 10:03:00, 2214.0, 2214.1, 2213.7, 2213.8, 4800\n" # Hold
            "2026-07-01 10:04:00, 2213.8, 2213.9, 2213.0, 2213.1, 8500\n" # SELL (< 2213.3)
            "2026-07-01 10:05:00, 2213.1, 2213.2, 2212.9, 2213.0, 4200\n" # Hold
            "2026-07-01 10:06:00, 2213.0, 2213.8, 2213.0, 2213.6, 9000\n" # BUY (> 2213.5)
            "2026-07-01 10:07:00, 2213.6, 2214.5, 2213.6, 2214.2, 6200\n" # Final day (liquidates at final price)
        )
        with open(backtest_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_data)

@patch('core.llm.get_llm', side_effect=mock_get_llm)
def run_dry_run(mock_llm_fn):
    """Bypasses API key checks and launches the main offline simulator."""
    print("=" * 80)
    print("                 FINAGENT OFFLINE DRY-RUN SIMULATOR             ")
    print("=" * 80)
    print("This mode mocks the LLM responses so you can test the entire pipeline")
    print("without needing an OpenAI API key or internet connection.")
    print("=" * 80)
    
    # Bypass API key check inside check_setup if run from playground/main
    os.environ["OPENAI_API_KEY"] = "mock_key_for_testing_purposes"
    
    # Pre-populate RAG store and backtesting files
    check_setup()
    
    print("\nSelect Simulation Modality:")
    print("1. Run main.py Interactive Ingestion Console")
    print("2. Run core/backtester.py Portfolio Trading Simulation")
    
    try:
        choice = input("\nEnter choice (1-2): ").strip()
        
        if choice == "1":
            import main
            main.main()
            
        elif choice == "2":
            from core.backtester import BacktestEngine
            import config
            
            engine = BacktestEngine(initial_capital=100000.0)
            csv_path = config.DATA_DIR / "backtest_candles.csv"
            
            results = engine.run(str(csv_path), "TCS", delay=1.0)
            
            # Print Final Report
            print("\n" + "=" * 60)
            print("                 BACKTEST PERFORMANCE REPORT                ")
            print("=" * 60)
            print(f"Initial Portfolio Value : Rs. {results['initial_capital']:,.2f}")
            print(f"Ending Portfolio Value  : Rs. {results['final_value']:,.2f}")
            
            pnl_color = "\033[92m" if results['total_return_pct'] >= 0 else "\033[91m"
            reset_color = "\033[0m"
            print(f"Total Return            : {pnl_color}{results['total_return_pct']:+.2f}%{reset_color}")
            print(f"Buy & Hold Return       : {results['buy_and_hold_return_pct']:+.2f}%")
            print(f"Total Executed Trades   : {results['total_trades']}")
            print(f"Trade Win Rate          : {results['win_rate_pct']:.1f}%")
            print("=" * 60)
            
        else:
            print("Invalid choice.")
            
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")

if __name__ == "__main__":
    run_dry_run()
