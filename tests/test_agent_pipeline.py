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
        self.assertIn(raw_signal.payload["summary"], event.normalized_text)

    def test_ingestion_rejects_missing_or_nonfinite_ohlcv(self):
        bad = RawSignal(
            raw_id="bad", signal_type=SignalType.PRICE_TICK, source="test",
            payload={"asset": "INFY", "open": 1, "high": 2, "low": 0, "close": float("nan")},
            received_at=datetime.now(timezone.utc),
        )
        state = create_initial_state()
        state["raw_signal"] = bad
        with self.assertRaises(ValueError):
            ingestion_node(state)

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

    def test_query_building_for_ticks(self):
        # Verify that _build_query outputs a semantic query for TICK signals
        from agents.retrieval import _build_query
        from core.state import PriceData, NormalizedEvent
        event = NormalizedEvent(
            event_id="evt_001",
            event_type=SignalType.PRICE_TICK,
            asset="TCS",
            source="yfinance",
            timestamp=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            normalized_text="TICK for TCS: close=4198.0, volume=312000.0, MA(20)=3980.0, RSI(14)=78.4",
            price_data=PriceData(
                open=4150.0, high=4210.0, low=4140.0, close=4198.0, volume=312000,
                moving_average=3980.0, rsi=78.4
            )
        )
        state = create_initial_state()
        state["normalized_event"] = event
        
        query = _build_query(state)
        self.assertEqual(query.asset, "TCS")
        self.assertIn("TCS financial performance", query.semantic_query)
        self.assertIn("RSI", query.keyword_query)

    def test_rerank_score_sigmoid_normalization(self):
        # Verify that cross-encoder logit scores are normalized to [0, 1] similarities
        from langchain_core.documents import Document
        from rag.vector_store import FinAgentVectorStore
        
        store = object.__new__(FinAgentVectorStore)
        # Mock cross encoder
        mock_ce = MagicMock()
        mock_ce.score.return_value = [-4.4548, 2.197] # -4.4548 (should map to ~0.011), 2.197 (should map to ~0.90)
        store._cross_encoder = mock_ce
        
        # Call _rerank
        from core.state import ScoreBundle
        docs = [
            (Document(page_content="doc1"), ScoreBundle()),
            (Document(page_content="doc2"), ScoreBundle())
        ]
        
        reranked = store._rerank("query", docs)
        
        self.assertEqual(len(reranked), 2)
        # doc2 should be ranked first because its score is higher
        self.assertEqual(reranked[0][0].page_content, "doc2")
        self.assertAlmostEqual(reranked[0][1].rerank_confidence, 1.0 / (1.0 + 2.718281828459045 ** -2.197), places=3)
        
        self.assertEqual(reranked[1][0].page_content, "doc1")
        self.assertAlmostEqual(reranked[1][1].rerank_confidence, 1.0 / (1.0 + 2.718281828459045 ** 4.4548), places=3)

    def test_retrieved_scores_are_bounded_and_rerank_wins(self):
        from langchain_core.documents import Document
        from core.state import ScoreBundle
        from rag.vector_store import FinAgentVectorStore, _sigmoid
        doc = Document(page_content="evidence", metadata={"doc_name": "a.pdf", "section": "S", "asset": "TCS"})
        reranked = FinAgentVectorStore._to_retrieved_passage(doc, ScoreBundle(sparse_score=500.0, rerank_logit=2.0, rerank_confidence=_sigmoid(2.0)))
        fallback = FinAgentVectorStore._to_retrieved_passage(doc, ScoreBundle(sparse_score=500.0, recency_weighted_score=0.01))
        self.assertAlmostEqual(reranked.similarity_score, round(_sigmoid(2.0), 4))
        self.assertTrue(0.0 <= reranked.similarity_score <= 1.0)
        self.assertTrue(0.0 <= fallback.similarity_score <= 1.0)

    def test_asset_filter_is_exact_metadata_match(self):
        from rag.vector_store import FinAgentVectorStore
        predicate = FinAgentVectorStore._make_asset_filter("TCS")
        self.assertTrue(predicate({"asset": "TCS", "doc_name": "generic.pdf"}))
        self.assertFalse(predicate({"asset": "INFY", "doc_name": "tcs-mentioned.pdf", "section": "TCS comparison"}))

    @patch("agents.retrieval._vector_search", side_effect=RuntimeError("empty index"))
    def test_retrieval_failure_is_explicitly_ungrounded(self, _search):
        from agents.retrieval import retrieval_node
        from core.state import NormalizedEvent
        event = NormalizedEvent(
            event_id="e", event_type=SignalType.NEWS_TEXT, asset="TCS", source="test",
            timestamp=datetime.now(timezone.utc), ingested_at=datetime.now(timezone.utc), normalized_text="TCS outlook"
        )
        state = create_initial_state()
        state["normalized_event"] = event
        result = retrieval_node(state)
        self.assertFalse(result["retrieval_grounded"])
        self.assertTrue(all(not p.grounded for p in result["retrieved_passages"]))
        self.assertTrue(result["errors"])

    def test_decision_aggregates_hypotheses_and_all_actions_reachable(self):
        from agents.decision import _action_from_hypotheses, _synthesize_artefact
        from core.state import Hypothesis, Action
        def hypothesis(kind, confidence, evidence):
            return Hypothesis(
                hypothesis_id=f"{kind.value}-{confidence}", asset="TCS", classification=kind,
                rationale="r", statement="s", supporting_evidence=[evidence],
                time_horizon=TimeHorizon.SHORT_TERM, confidence_score=confidence,
                grounding_passage_ids=[], created_at=datetime.now(timezone.utc),
            )
        bullish = hypothesis(Classification.BULLISH, 80, "growth")
        bearish = hypothesis(Classification.BEARISH, 75, "margin risk")
        neutral = hypothesis(Classification.NEUTRAL, 55, "no catalyst")
        self.assertEqual(_action_from_hypotheses([bullish]), Action.BUY)
        self.assertEqual(_action_from_hypotheses([bearish]), Action.SELL)
        self.assertEqual(_action_from_hypotheses([neutral]), Action.HOLD)
        self.assertEqual(_action_from_hypotheses([hypothesis(Classification.BULLISH, 45, "weak")]), Action.WATCH)
        state = create_initial_state()
        state["hypothesis"] = bullish
        state["hypotheses"] = [bullish, bearish]
        artefact = _synthesize_artefact(state, None)
        self.assertIn("growth", artefact.evidence_bullets)
        self.assertIn("margin risk", artefact.evidence_bullets)
        self.assertTrue(any("Contradictory" in flag for flag in artefact.risk_flags))
        self.assertEqual(artefact.action, Action.HOLD)

    @patch("agents.analysis._get_analysis_safe")
    def test_fallback_evidence_cannot_inflate_decision_confidence(self, mock_analysis):
        from agents.decision import _synthesize_artefact
        from core.state import NormalizedEvent, RetrievedPassage
        mock_analysis.return_value = (_AnalysisOutput(
            classification=Classification.BULLISH, rationale="generic", statement="generic",
            supporting_evidence=["generic"], time_horizon=TimeHorizon.SHORT_TERM, confidence_score=90,
        ), "ok", None)
        event = NormalizedEvent(
            event_id="e", event_type=SignalType.NEWS_TEXT, asset="TCS", source="test",
            timestamp=datetime.now(timezone.utc), ingested_at=datetime.now(timezone.utc), normalized_text="TCS news"
        )
        fallback = RetrievedPassage(
            passage_id="p", text="generic", source_document="framework", similarity_score=.9,
            retrieved_at=datetime.now(timezone.utc), source_type="fallback_generic", grounded=False,
        )
        state = create_initial_state()
        state.update(normalized_event=event, retrieved_passages=[fallback], retrieval_grounded=False)
        analyzed = analysis_node(state)
        state.update(analyzed)
        artefact = _synthesize_artefact(state, None)
        self.assertLessEqual(analyzed["hypothesis"].confidence_score, 39)
        self.assertLessEqual(artefact.confidence_score, 39)

    def test_frontend_api_contract_uses_backend_canonical_field_names(self):
        """Guard the dashboard/KB DTO contract without duplicating aliases."""
        from pathlib import Path
        from core.state import DecisionArtefact, RetrievedPassage
        types = Path("frontend/src/types/api.ts").read_text(encoding="utf-8")
        for field in ("artefact_id", "created_at", "confidence_score", "alert_triggered", "evidence_bullets"):
            self.assertIn(field, DecisionArtefact.model_fields)
            self.assertIn(field, types)
        for field in ("text", "source_document", "similarity_score"):
            self.assertIn(field, RetrievedPassage.model_fields)
            self.assertIn(field, types)

    def test_yfinance_live_fetcher(self):
        # Mock yfinance to prevent actual network calls during testing
        from core.ingestion_manager import fetch_live_yfinance_tick
        import pandas as pd
        
        mock_data = pd.DataFrame([{
            "Open": 4150.0, "High": 4200.0, "Low": 4140.0, "Close": 4195.0, "Volume": 150000.0
        }])
        
        with patch('yfinance.Ticker') as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_data
            mock_ticker_cls.return_value = mock_ticker
            
            # Fetch tick for TCS
            signal = fetch_live_yfinance_tick("TCS")
            
            # Verify ticker was instantiated with mapped symbol
            mock_ticker_cls.assert_called_once_with("TCS.NS")
            
            # Verify resulting signal payload
            self.assertIsNotNone(signal)
            self.assertEqual(signal.payload["asset"], "TCS")
            self.assertEqual(signal.payload["close"], 4195.0)
            self.assertEqual(signal.payload["volume"], 150000.0)

    def test_csv_streaming(self):
        # Test loading from a temporary CSV file with messy column names
        from core.ingestion_manager import stream_from_csv
        import tempfile
        
        csv_content = (
            "Timestamp, Open Price, High, Low, Close Price, Volume Traded\n"
            "2026-07-14 10:00:00, 100.0, 105.0, 99.0, 104.0, 1000\n"
            "2026-07-14 10:01:00, 104.0, 106.0, 103.0, 105.0, 1200\n"
        )
        
        # Create a temporary file and write the mock CSV data
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv") as temp_csv:
            temp_csv.write(csv_content)
            temp_csv_path = temp_csv.name
            
        try:
            # Consume the CSV stream generator
            signals = list(stream_from_csv(temp_csv_path, "INFY"))
            
            self.assertEqual(len(signals), 2)
            
            # Verify row 1 mappings
            self.assertEqual(signals[0].payload["asset"], "INFY")
            self.assertEqual(signals[0].payload["open"], 100.0)
            self.assertEqual(signals[0].payload["close"], 104.0)
            self.assertEqual(signals[0].payload["volume"], 1000.0)
            
            # Verify row 2 mappings
            self.assertEqual(signals[1].payload["close"], 105.0)
            self.assertEqual(signals[1].payload["volume"], 1200.0)
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)


if __name__ == "__main__":
    unittest.main()
