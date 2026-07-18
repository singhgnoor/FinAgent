"""
Project-wide Central Configuration.
Resolves the project directories.

Single source of truth for tunable constants used across the pipeline.
"""

from pathlib import Path
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# DEBUG -
VERBOSE = False


## Dirs
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Logging
LOG_LEVEL = "DEBUG" if VERBOSE else "INFO"

## LLM Backbone — OpenAI, declared per PS 3.1
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_PROVIDER = "openai"
LLM_MODEL_NAME = "gpt-5.4-mini"
LLM_TEMPERATURE = 0.2

## Knowledge base source documents, for the KB build/test script
# User-uploaded PDFs are retained here and this directory is the source of
# truth used by the KB reindex operation.
KB_STORE_DIR = DATA_DIR / "kb_store"
KB_DOCS_DIR = KB_STORE_DIR


## Agent Specific configuration

DEFAULT_ALERT_THRESHOLD = 70  # Decision Agent

# RAG Agent
ASSET_ALIASES: Dict[str, List[str]] = {
    "HDFC": ["HDFC", "HDFC BANK", "HDFCBANK", "HDFC LTD", "HOUSING DEVELOPMENT FINANCE"],
    "TCS": ["TCS", "TATA CONSULTANCY", "TATA CONSULTANCY SERVICES"],
    "RELIANCE": ["RELIANCE", "RIL", "RELIANCE INDUSTRIES"],
    "INFY": ["INFY", "INFOSYS"],
    # ... add the rest of your evaluation universe here
}

TOP_K_DEFAULT = 3

# Embedding model (RAG)

# Finance-tuned sentence-transformers model — for financial terminology/lexicon than a generic embedding model.
# Swap to "sentence-transformers/all-MiniLM-L6-v2" for a faster/smaller generic fallback during early development
# or for offline processing.
EMBEDDING_MODEL_NAME = "FinLang/finance-embeddings-investopedia"
EMBEDDING_DEVICE = "cpu"  # set to "cuda" for GPU processing
EMBEDDING_DIMENSION = 384  # embedding vector dimension

# Vector store persistence

VECTOR_STORE_DIR =  DATA_DIR / "vector_store"  # FAISS index + doc pickle saved here

# Chunking (rag/ingest.py)

NARRATIVE_CHUNK_TOKENS = 350            # narrative sections: 200-500 token range
NARRATIVE_CHUNK_OVERLAP_TOKENS = 50
TABLE_CHUNK_MAX_TOKENS = 1000           # tables are atomic; only split (by row-group) past this size
CHARS_PER_TOKEN_ESTIMATE = 4            # rough heuristic to convert token targets -> char counts for the splitter

# Hybrid retrieval (rag/vector_store.py)

DENSE_TOP_K = 20          # candidates pulled from FAISS before fusion
SPARSE_TOP_K = 20         # candidates pulled from BM25 before fusion
DENSE_WEIGHT = 0.6        # weight given to the dense retriever in RRF fusion
SPARSE_WEIGHT = 0.4       # weight given to BM25 in RRF fusion — catches tickers, $ figures, exact terms
FINAL_TOP_K = 5           # passages actually returned to the Analysis Agent

# RRF's smoothing constant. Larger values compress the score gap between
# adjacent ranks (rank 0 vs rank 9 differ by only ~13% of score when
# RRF_K=60 and top_k=10) — which matters because RECENCY_WEIGHT below can
# swing a score by up to ~16%. If recency ever visibly overpowers topical
# relevance in your real corpus, lower this to widen the rank-based gap.
RRF_K = 60

# Recency weighting (rag/vector_store.py)

RECENCY_HALF_LIFE_DAYS = 30   # a doc this old has its recency factor halved
RECENCY_WEIGHT = 0.25         # how much recency blends into the final score (0 = ignore, 1 = recency dominates)
RECENCY_FLOOR = 0.35          # never discount relevance below this factor — old 10-Ks can still matter

# Embedding (rag/vector_store.py)

NORMALIZE_EMBEDDINGS = True
FAISS_DISTANCE_STRATEGY = "cosine"  # "cosine" or "l2" (Euclidean) — must match the FAISS index type used in ingest.py

# Cross-encoder reranking (rag/vector_store.py)

ENABLE_RERANKING = True
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_CANDIDATE_POOL = 20

# Confidence gating (rag/vector_store.py)
CONFIDENCE_THRESHOLD = 0.3    # sigmoid(cross-encoder logit) below this => flag as low-confidence

if __name__ == '__main__':
    print(f"Project root : {BASE_DIR}")
