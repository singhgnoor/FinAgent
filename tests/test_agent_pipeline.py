import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import json
import os
import sys

# Ensure main/FinAgent is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["OPENAI_API_KEY"] = "mock-key"

import config
from core.state import (
    RawSignal,
    SignalType,
    FinAgentState,
    create_initial_state,
    Classification,
    TimeHorizon,
)
from agents.ingestion import ingestion_node, PRICE_HISTORY_FILE
from agents.analysis import analysis_node, _AnalysisOutput


class TestIngestionAndAnalysis(unittest.TestCase):

    def setUp(self):
        # Clear any existing price history cache
        if os.path.exists(PRICE_HISTORY_FILE):
            os.remove(PRICE_HISTORY_FILE)

    def tearDown(self):
        # Clean up price history cache
        if os.path.exists(PRICE_HISTORY_FILE):
            os.remove(PRICE_HISTORY_FILE)

    def test_ingestion_price_ticks_stateful_calculation(self):
        # We will feed 21 ticks and verify the SMA (20-period) and RSI (14-period) calculation
        # Prices: 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120
        # SMA of last 20 at tick 21 (101 to 120) should be sum(101..120)/20 = 110.5
        for i in range(21):
            close_price = 100.0 + i
            raw_signal = RawSignal(
                raw_id=f"tick_{i}",
                signal_type=SignalType.PRICE_TICK,
                source="yfinance",
                payload={
                    "asset": "INFY",
                    "open": 99.0 + i,
                    "high": 101.5 + i,
                    "low": 98.0 + i,
                    "close": close_price,
                    "volume": 5000 + i * 100,
                },
                received_at=datetime.now(timezone.utc),
            )

            state = create_initial_state()
            state["raw_signal"] = raw_signal
            result = ingestion_node(state)
            
            self.assertIn("normalized_event", result)
            event = result["normalized_event"]
            self.assertEqual(event.asset, "INFY")
            self.assertIsNotNone(event.price_data)
            
            # Check values at the last tick
            if i == 20:
                self.assertEqual(event.price_data.close, 120.0)
                # SMA(20) should be the average of prices 101 to 120
                expected_sma = sum(range(101, 121)) / 20.0
                self.assertAlmostEqual(event.price_data.moving_average, expected_sma)
                # RSI should be 100.0 because it's rising continuously
                self.assertAlmostEqual(event.price_data.rsi, 100.0)
                
                # Check log content
                self.assertTrue("MA(20)" in event.normalized_text)
                self.assertTrue("RSI(14)" in event.normalized_text)

    def test_ingestion_news_text_heuristic_extraction(self):
        # Headline mentioning Infosys
        raw_signal = RawSignal(
            raw_id="news_001",
            signal_type=SignalType.NEWS_TEXT,
            source="rss_feed",
            payload={
                "headline": "Infosys quarterly profits jump 15% amid digital transformation demand",
                "summary": "India's software giant INFY reported strong earnings.",
            },
            received_at=datetime.now(timezone.utc),
        )

        state = create_initial_state()
        state["raw_signal"] = raw_signal
        result = ingestion_node(state)

        self.assertIn("normalized_event", result)
        event = result["normalized_event"]
        self.assertEqual(event.asset, "INFY")  # Should detect INFY or INFOSYS
        self.assertEqual(event.event_type, SignalType.NEWS_TEXT)
        self.assertIsNotNone(event.text_data)
        self.assertEqual(event.text_data.headline, raw_signal.payload["headline"])

    @patch("agents.analysis.get_llm")
    def test_analysis_agent_runs_with_price_data(self, mock_get_llm):
        # Mock the LLM to return structured AnalysisOutput
        mock_llm = MagicMock()
        mock_structured_output = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured_output

        # Mock LLM structured invocation response
        mock_output = _AnalysisOutput(
            classification=Classification.BULLISH,
            rationale="Moving Average is trending up and RSI is strong but not yet overbought.",
            statement="INFY shows strong upward technical momentum.",
            supporting_evidence=["SMA(20) is at 110.5", "RSI(14) is at 60.5"],
            time_horizon=TimeHorizon.SHORT_TERM,
            confidence_score=80,
        )
        mock_structured_output.invoke.return_value = mock_output
        mock_structured_output.return_value = mock_output

        # Create a mock normalized event with price data
        from core.state import PriceData, NormalizedEvent, RetrievedPassage
        event = NormalizedEvent(
            event_id="evt_001",
            event_type=SignalType.PRICE_TICK,
            asset="INFY",
            source="yfinance",
            timestamp=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            normalized_text="INFY price tick close=120.0",
            price_data=PriceData(
                open=118.0,
                high=121.0,
                low=117.0,
                close=120.0,
                volume=10000,
                moving_average=110.5,
                rsi=60.5,
            )
        )

        # RAG needs to return at least one passage to run analysis (per Gurnoor's grounding check)
        passage = RetrievedPassage(
            passage_id="psg_001",
            text="INFY has strong structural growth in its cloud division.",
            source_document="infy_q3_report.pdf",
            similarity_score=0.85,
            retrieved_at=datetime.now(timezone.utc),
        )

        state = create_initial_state()
        state["normalized_event"] = event
        state["retrieved_passages"] = [passage]

        result = analysis_node(state)

        self.assertIn("hypothesis", result)
        hypothesis = result["hypothesis"]
        self.assertEqual(hypothesis.asset, "INFY")
        self.assertEqual(hypothesis.classification, Classification.BULLISH)
        self.assertEqual(hypothesis.confidence_score, 84) # 80 + 4 bonus (1 passage, avg similarity 0.85 -> count_bonus=0, similarity_bonus=4)
        
        # Verify that the LLM was called with the technical indicators formatted in normalized_text
        prompt_str = mock_structured_output.call_args[0][0].to_string()
        self.assertIn("Technical Metrics", prompt_str)
        self.assertIn("Current Price (Close): 120.0", prompt_str)
        self.assertIn("20-period Simple Moving Average (SMA): 110.50", prompt_str)
        self.assertIn("14-period Relative Strength Index (RSI): 60.50", prompt_str)


if __name__ == "__main__":
    unittest.main()
