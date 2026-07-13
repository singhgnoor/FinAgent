"""
FinAgent — Document Ingestion & Chunking
Location: rag/ingest.py

Loads reference documents (10-Ks, earnings transcripts, sector reports —
whatever the RAG knowledge base is built from, per problem statement 2.2)
and turns them into LangChain Document chunks, ready to hand to
`rag/vector_store.py::FinAgentVectorStore.add_documents()`.

Chunking strategy (deliberately NOT a generic character-count splitter):

  - Tables are extracted as atomic units via pdfplumber's layout-aware
    table detection, never split by character count. A revenue table
    split mid-row is useless to both halves.
  - Section headers ("Item 7. MD&A", "RISK FACTORS", ...) are detected
    heuristically and prepended into every chunk's TEXT within that
    section — not just attached as metadata — so the embedding itself
    carries that context.
  - Narrative text is split into ~200-500 token chunks (LangChain's
    RecursiveCharacterTextSplitter); tables are capped at ~1000 tokens
    and only split by row-group (header row repeated in each group) if
    they exceed it — never mid-row.
  - Table content is stripped out of the narrative text before splitting,
    so numbers aren't duplicated across a table chunk AND a smeared-text
    narrative chunk (pdfplumber's extract_text() does not exclude tables
    by default).
"""

import os
import re
from datetime import datetime, timezone
from typing import List, Optional

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

_ITEM_HEADER_RE = re.compile(r"^item\s+\d+[a-z]?\.?\s+.{3,80}$", re.IGNORECASE)


# Public API

def load_and_chunk_document(file_path: str, doc_date: Optional[datetime] = None) -> List[Document]:
    """Parse one PDF into narrative + table chunks with section-aware metadata."""
    doc_name = os.path.basename(file_path)
    resolved_date = doc_date or _infer_doc_date(file_path)

    chunks: List[Document] = []
    current_section = "General"

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            raw_text = page.extract_text() or ""

            # Detect headers on THIS page before tagging THIS page's tables —
            # otherwise a table sitting below a header on the same page
            # would incorrectly inherit the previous page's section. (Note:
            # this is still page-level, not true reading-order — a table
            # above its own header on the same page is a known edge case
            # pdfplumber's bounding-box order could resolve, but isn't
            # handled here.)
            for line in raw_text.split("\n"):
                stripped = line.strip()
                if _is_section_header(stripped):
                    current_section = stripped

            for table in tables:
                chunks.extend(
                    _build_table_chunks(table, doc_name, current_section, page_num, resolved_date)
                )

            narrative_text = _strip_table_lines_from_text(raw_text, tables)
            chunks.extend(
                _build_narrative_chunks(narrative_text, doc_name, current_section, page_num, resolved_date)
            )

    return chunks


def load_and_chunk_directory(dir_path: str) -> List[Document]:
    """Batch-ingest every PDF in a directory (e.g. the KB upload folder, spec 5.1)."""
    all_chunks: List[Document] = []
    for filename in sorted(os.listdir(dir_path)):
        if filename.lower().endswith(".pdf"):
            all_chunks.extend(load_and_chunk_document(os.path.join(dir_path, filename)))
    return all_chunks


# Section header detection

def _is_section_header(line: str) -> bool:
    """Heuristic: 'Item 7. MD&A' style headers, or short all-caps lines."""
    if not line or len(line) > 90:
        return False
    if _ITEM_HEADER_RE.match(line):
        return True

    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 6 and all(c.isupper() for c in letters)


# Narrative chunking

def _build_narrative_chunks(
    text: str, doc_name: str, section: str, page_num: int, doc_date: datetime
) -> List[Document]:
    text = text.strip()
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.NARRATIVE_CHUNK_TOKENS * config.CHARS_PER_TOKEN_ESTIMATE,
        chunk_overlap=config.NARRATIVE_CHUNK_OVERLAP_TOKENS * config.CHARS_PER_TOKEN_ESTIMATE,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    documents = []
    for raw_chunk in splitter.split_text(text):
        # Section context goes INTO the embedded text, not just metadata,
        # so the embedding itself "knows" this is MD&A vs. Risk Factors.
        contextualized = f"[{doc_name} | {section}]\n{raw_chunk}"
        documents.append(
            Document(
                page_content=contextualized,
                metadata=_build_metadata(doc_name, section, page_num, "narrative", doc_date),
            )
        )
    return documents


# Table chunking — atomic, never split mid-row

def _build_table_chunks(
    table: List[List[Optional[str]]], doc_name: str, section: str, page_num: int, doc_date: datetime
) -> List[Document]:
    rows = [[(cell or "").strip() for cell in row] for row in table]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []

    header_row = rows[0]
    max_chars = config.TABLE_CHUNK_MAX_TOKENS * config.CHARS_PER_TOKEN_ESTIMATE
    row_groups = _split_table_rows(rows, header_row, max_chars)

    documents = []
    for group in row_groups:
        table_text = "\n".join(" | ".join(row) for row in group)
        contextualized = f"[{doc_name} | {section} | table]\n{table_text}"
        documents.append(
            Document(
                page_content=contextualized,
                metadata=_build_metadata(doc_name, section, page_num, "table", doc_date),
            )
        )
    return documents


def _split_table_rows(
    rows: List[List[str]], header_row: List[str], max_chars: int
) -> List[List[List[str]]]:
    """Group rows under a char budget, repeating the header, never splitting a row in half."""
    groups: List[List[List[str]]] = []
    current_group = [header_row]
    current_len = len(" | ".join(header_row))

    for row in rows[1:]:
        row_len = len(" | ".join(row))
        if current_len + row_len > max_chars and len(current_group) > 1:
            groups.append(current_group)
            current_group = [header_row, row]
            current_len = len(" | ".join(header_row)) + row_len
        else:
            current_group.append(row)
            current_len += row_len

    if len(current_group) > 1 or not groups:
        groups.append(current_group)

    return groups


def _strip_table_lines_from_text(
    page_text: str, tables: List[List[List[Optional[str]]]]
) -> str:
    """
    pdfplumber's extract_text() doesn't exclude table content, so without
    this, table numbers appear twice: once as a clean atomic table chunk,
    once smeared across narrative chunks. Drop any text line that closely
    matches a table row so tables stay the single source of truth.
    """
    row_signatures = set()
    for table in tables:
        for row in table:
            cells = [c.strip() for c in row if c]
            if cells:
                row_signatures.add(" ".join(cells).lower())

    kept_lines = [
        line for line in page_text.split("\n")
        if " ".join(line.split()).lower() not in row_signatures
    ]
    return "\n".join(kept_lines)


# Shared helpers

def _build_metadata(doc_name: str, section: str, page_num: int, chunk_type: str, doc_date: datetime) -> dict:
    return {
        "doc_name": doc_name,
        "section": section,
        "page": page_num,
        "chunk_type": chunk_type,
        "doc_date": doc_date.isoformat(),
    }


def _infer_doc_date(file_path: str) -> datetime:
    """Falls back to file modification time when no explicit publish date is given."""
    mtime = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)