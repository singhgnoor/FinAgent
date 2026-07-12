"""
FinAgent — LLM Backbone (OpenAI via LangChain)

Declares the LLM backbone per PS 3.1. One shared ChatOpenAI client, built
with langchain-openai to satisfy the "LangChain for agent tooling"
requirement — Analysis and Decision agents will call get_llm() rather
than instantiating their own clients.
"""

from typing import Optional

from langchain_openai import ChatOpenAI

import config

_llm: Optional[ChatOpenAI] = None


def get_llm() -> ChatOpenAI:
    """Lazily build+cache the shared LLM client (mirrors get_vector_store())."""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=config.LLM_MODEL_NAME,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.OPENAI_API_KEY,
        )
    return _llm