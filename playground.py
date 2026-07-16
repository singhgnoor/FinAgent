import os
import sys
import time
from datetime import datetime, timezone

# Ensure main/FinAgent is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load dotenv if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config
from core.state import RawSignal, SignalType, Action, Classification
from core.graph import run_once
from rag.vector_store import get_vector_store
from rag.ingest import load_and_chunk_document
from langchain_core.documents import Document

# Safe print helper for color formatting
def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)

def print_section(title, content):
    print(f"\n[▶] {title.upper()}:")
    print(content)

def check_setup():
    """Verify API keys and index mock data if the database is empty."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print_header("API Key Missing")
        print("To run the real LLM pipeline, please set your OpenAI API key.")
        print("In PowerShell, run:")
        print('  $env:OPENAI_API_KEY="your-key-here"')
        print("\nOr create a file named '.env' in this directory containing:")
        print('  OPENAI_API_KEY="your-key-here"')
        print("=" * 80)
        sys.exit(1)

    # Auto-initialize mock reference documents if RAG is empty
    store = get_vector_store()
    if store.is_empty:
        print("\n[RAG] Vector store is empty. Setting up sample knowledge base...")
        os.makedirs(config.KB_DOCS_DIR, exist_ok=True)
        
        # Write a sample financial reference document
        sample_doc_path = config.KB_DOCS_DIR / "tcs_outlook_report.txt"
        if not os.path.exists(sample_doc_path):
            sample_content = """
            TATA CONSULTANCY SERVICES (TCS) - RESEARCH AND OUTLOOK REPORT
            Document Date: 2026-07-01
            
            1. Business Performance & Financial Health:
            TCS reported strong quarterly revenue growth, driven by key wins in cloud migration and digital transformation services. Operating margins remained resilient at 24.5% due to effective sub-contractor cost management and automated workforce utilization. 
            
            2. Outlook and Growth Drivers:
            The management has outlined a robust pipeline for the rest of FY27, specifically highlighting a multi-year $1B cloud migration deal with a major European financial institution. The company's expansion into Conversational AI and generative workflows is expected to increase average revenue per user (ARPU) across enterprise contracts by 12% over the next two quarters.
            
            3. Valuation and Key Risks:
            While TCS's growth trajectory remains bullish, key valuation risks include salary inflation in high-skill software roles, potential currency headwinds from the fluctuating Euro/INR exchange rates, and aggressive competitor pricing from Infosys (INFY) and Wipro on medium-scale legacy contracts.
            """
            with open(sample_doc_path, "w", encoding="utf-8") as f:
                f.write(sample_content)
            print(f"[RAG] Created sample reference document at {sample_doc_path}")

        # Chunk and embed the document
        print("[RAG] Chunking and embedding sample document...")
        # Since load_and_chunk_document expects a PDF (uses pdfplumber), 
        # we will chunk our txt file using a fallback Text loader for testing convenience
        metadata = {
            "doc_name": "tcs_outlook_report.txt",
            "section": "Financial Outlook",
            "page": 1,
            "chunk_type": "narrative",
            "doc_date": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat()
        }
        with open(sample_doc_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        # Simple character splitting for text fallback in playground
        chunks = [
            Document(page_content=f"[tcs_outlook_report.txt | Section: {metadata['section']}]\n{text[i:i+600]}", metadata=metadata)
            for i in range(0, len(text), 500)
        ]
        
        store.add_documents(chunks)
        store.save()
        print(f"[RAG] Successfully indexed {len(chunks)} chunks in local FAISS vector store!")

def run_playground():
    check_setup()
    
    print_header("FinAgent Terminal Playground")
    print("Select a raw signal type to run through the multi-agent pipeline:")
    print("1. PRICE TICK (TCS Price breakout with high RSI)")
    print("2. NEWS TEXT  (TCS wins $1B European cloud migration contract)")
    print("3. CUSTOM NEWS TEXT (Type your own headline)")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting playground.")
        return

    now = datetime.now(timezone.utc)
    raw_signal = None

    if choice == "1":
        # Simulate a price tick breakout
        raw_signal = RawSignal(
            raw_id="tick_999",
            signal_type=SignalType.PRICE_TICK,
            source="yfinance",
            payload={
                "asset": "TCS",
                "open": 4150.0,
                "high": 4210.0,
                "low": 4140.0,
                "close": 4198.0,
                "volume": 312000.0,
                # Ingestion agent will compute the stateful SMA and RSI
            },
            received_at=now
        )
    elif choice == "2":
        # Simulate an unstructured news headline
        raw_signal = RawSignal(
            raw_id="news_999",
            signal_type=SignalType.NEWS_TEXT,
            source="rss_feed",
            payload={
                "headline": "TCS wins landmark $1B cloud migration deal with European Bank",
                "summary": "TCS management reports Q3 outlook is highly positive following major deal signature.",
            },
            received_at=now
        )
    elif choice == "3":
        headline = input("\nEnter your custom news headline: ").strip()
        if not headline:
            print("Headline cannot be empty.")
            return
        raw_signal = RawSignal(
            raw_id="news_custom",
            signal_type=SignalType.NEWS_TEXT,
            source="user_input",
            payload={
                "headline": headline,
                "summary": "User-triggered custom market event."
            },
            received_at=now
        )
    else:
        print("Invalid choice.")
        return

    print("\n[System] Ingesting raw signal and executing LangGraph pipeline...")
    start_time = time.perf_counter()
    
    # Run the pipeline!
    final_state = run_once(raw_signal, alert_threshold=70)
    
    elapsed = time.perf_counter() - start_time
    print(f"[System] Pipeline completed execution in {elapsed:.2f} seconds.")

    # 1. Ingestion Output
    event = final_state.get("normalized_event")
    if event:
        print_header("1. Ingestion Agent Output")
        print(f"Event ID   : {event.event_id}")
        print(f"Asset Name : {event.asset}")
        print(f"Normalized : {event.normalized_text}")
        if event.price_data:
            pd = event.price_data
            print(f"Indicators : SMA(20)={pd.moving_average:.2f}, RSI(14)={pd.rsi:.2f}")

    # 2. Retrieval Output
    passages = final_state.get("retrieved_passages", [])
    print_header(f"2. Retrieval Agent Output ({len(passages)} passages found)")
    if passages:
        for idx, p in enumerate(passages):
            print(f"\nPassage #{idx+1} [Similarity: {p.similarity_score:.4f}]")
            print(f"Source Document: {p.source_document} ({p.section_reference})")
            print(f"Excerpt: {p.text.strip()}")
    else:
        print("No passages retrieved (either skipped or nothing relevant found).")

    # 3. Analysis Output
    hypothesis = final_state.get("hypothesis")
    print_header("3. Analysis Agent Output")
    if hypothesis:
        print(f"Sentiment Classification : {hypothesis.classification.value.upper()}")
        print(f"Confidence Score (0-100) : {hypothesis.confidence_score}")
        print(f"Time Horizon             : {hypothesis.time_horizon.value.upper()}")
        print(f"Rationale                : {hypothesis.rationale}")
        print(f"Hypothesis Statement     : {hypothesis.statement}")
        print("Supporting Evidence:")
        for bullet in hypothesis.supporting_evidence:
            print(f"  - {bullet}")
    else:
        print("Analysis Agent did not generate a hypothesis (confidence too low or LLM skipped).")

    # 4. Decision Output
    artefact = final_state.get("artefact")
    print_header("4. Decision Agent Output")
    if artefact:
        # Highlight trade recommendation
        action = artefact.action.value
        color_start = "\033[92m" if action == "BUY" else "\033[91m" if action == "SELL" else "\033[93m" if action == "HOLD" else "\033[94m"
        color_end = "\033[0m"
        
        print(f"RECOMMENDED TRADE ACTION : {color_start}*** {action} ***{color_end}")
        print(f"Confidence Level         : {artefact.confidence_level.value} ({artefact.confidence_score}%)")
        print(f"Alert Triggered          : {artefact.alert_triggered}")
        print("Key Supporting Evidence:")
        for idx, bullet in enumerate(artefact.evidence_bullets):
            print(f"  {idx+1}. {bullet}")
        print("Risk Flags / Gaps:")
        for flag in artefact.risk_flags:
            print(f"  [!] {flag}")
        if artefact.llm_commentary:
            print(f"Expert Commentary        : {artefact.llm_commentary}")
    else:
        print("No decision artefact synthesized (pipeline ended early or confidence was below minimum threshold).")

    # 5. Agent Trace Log
    print_header("5. Agent Trace Log (Observability)")
    trace_log = final_state.get("trace_log", [])
    for idx, t in enumerate(trace_log):
        print(f"[{idx+1}] Agent: {t.agent.value.ljust(15)} | Action: {t.action.ljust(30)} | Status: {t.status}")
        if t.output_summary:
            print(f"    Summary: {t.output_summary}")
        if t.error_message:
            print(f"    Error  : {t.error_message}")

if __name__ == "__main__":
    run_playground()
