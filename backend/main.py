import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm import get_llm
from core.log import get_logger, setup_logging
from rag.vector_store import get_vector_store

from backend.routers import decisions, knowledge_base, signals, system

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[backend] Starting up — warming LLM + vector store")
    try:
        get_llm()
        logger.info("[backend] LLM warmed up")
    except Exception as e:
        logger.warning("[backend] LLM warmup failed: %s", e)
    try:
        get_vector_store()
        logger.info("[backend] Vector store warmed up")
    except Exception as e:
        logger.warning("[backend] Vector store warmup failed: %s", e)
    yield
    logger.info("[backend] Shutting down")


app = FastAPI(title="FinAgent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router, prefix="/api/v1/signals")
app.include_router(knowledge_base.router, prefix="/api/v1/knowledge-base")
app.include_router(decisions.router, prefix="/api/v1/decisions")
app.include_router(system.router, prefix="/api/v1")
