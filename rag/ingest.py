"""
FinAgent — Document Ingestion & Chunking
Location: rag/ingest.py

Loads reference documents (10-Ks, annual reports, earnings transcripts,
sector reports — whatever the RAG knowledge base is built from, per problem
statement 2.2) and turns them into LangChain Document chunks, ready to hand
to `rag/vector_store.py::FinAgentVectorStore.add_documents()`.

Chunking strategy (deliberately NOT a generic character-count splitter):

  - Tables are extracted as atomic units, never split by character count.
    Two passes run per page: pdfplumber's ruled-border ("lines") strategy
    first, then a whitespace-alignment ("text") strategy fills in tables
    that have no visible ruling — common on subsidiary/shareholding
    disclosure pages — but only in regions the first pass didn't already
    claim, so ordinary paragraphs don't get mistaken for tables.
  - Section headers ("Item 7. MD&A", "RISK FACTORS", "Liquidity and
    Capital Resources") are detected using BOTH a text pattern AND the
    page's actual layout (font size relative to the page's body text).
    Text pattern alone (e.g. Title Case) matches far too many proper-noun
    phrases in financial documents — company names, director names,
    subsidiary listings, award titles — to be trusted by itself; a line
    only counts as a header if it's also rendered in a meaningfully
    larger font than surrounding body text (or is an unambiguous "Item N"
    / ALL-CAPS line, which don't need the font check).
  - Header text is prepended into every chunk's TEXT within that section
    — not just attached as metadata — so the embedding itself carries
    that context.
  - Narrative text is split into ~200-500 token chunks (LangChain's
    RecursiveCharacterTextSplitter); tables are capped at ~1000 tokens
    and only split by row-group (header row repeated in each group) if
    they exceed it — never mid-row.
  - Rotated/sideways text (sidebar banners, vertical divider labels) is
    excluded from narrative extraction rather than being read in normal
    left-to-right order, which otherwise scrambles it into adjacent
    chunks (e.g. "Risks\nOpportunity" coming out as "sksiR\nytinutroppO").
  - Any block that survives the above still shorter than a minimum
    length is merged into its neighbor rather than dropped or indexed as
    its own information-poor fragment.
"""

import os
import re
import hashlib
import statistics
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

_ITEM_HEADER_RE = re.compile(r"^item\s+\d+[a-z]?\.?\s+.{3,80}$", re.IGNORECASE)

# Tunable knobs. Override any of these in config.py; sane defaults are used
# otherwise so this module works out of the box.
_MIN_BLOCK_CHARS = getattr(config, "MIN_BLOCK_CHARS", 150)
_HEADER_FONT_SIZE_RATIO = getattr(config, "HEADER_FONT_SIZE_RATIO", 1.15)
_ENABLE_BORDERLESS_TABLES = getattr(config, "ENABLE_BORDERLESS_TABLE_DETECTION", True)


# Public API

def load_and_chunk_document(
    file_path: str, doc_date: Optional[datetime] = None, asset: Optional[str] = None
) -> List[Document]:
    """Parse one PDF into chunks tagged with a canonical asset identifier.

    Policy: a document explicitly supplied for one asset receives that ticker.
    A filename that maps to exactly one configured company is tagged likewise.
    Ambiguous sector/multi-company documents are tagged ``MULTI_ASSET`` and
    excluded from company-scoped retrieval unless a deliberate sector query is
    implemented; they are still available to unscoped KB search.
    """
    doc_name = os.path.basename(file_path)
    resolved_date = doc_date or _infer_doc_date(file_path)
    canonical_asset, multi_asset = _document_asset_policy(doc_name, asset)

    chunks: List[Document] = []
    current_section = "General"

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            found_tables = _find_tables(page)
            tables = [t.extract() for t in found_tables]
            table_bboxes = [t.bbox for t in found_tables]

            for table in tables:
                chunks.extend(
                    _build_table_chunks(table, doc_name, current_section, page_num, resolved_date, canonical_asset, multi_asset)
                )

            lines = _extract_page_lines(page, table_bboxes)
            sub_blocks, current_section = _split_into_section_blocks(lines, current_section)
            sub_blocks = _merge_short_blocks(sub_blocks)
            for section_label, block_text in sub_blocks:
                chunks.extend(
                    _build_narrative_chunks(block_text, doc_name, section_label, page_num, resolved_date, canonical_asset, multi_asset)
                )

    return chunks


def load_and_chunk_directory(dir_path: str) -> List[Document]:
    """Batch-ingest every PDF in a directory (e.g. the KB upload folder, spec 5.1)."""
    all_chunks: List[Document] = []
    for filename in sorted(os.listdir(dir_path)):
        if filename.lower().endswith(".pdf"):
            all_chunks.extend(load_and_chunk_document(os.path.join(dir_path, filename)))
    return all_chunks


def inspect_chunk_lengths(chunks: List[Document]) -> dict:
    """Quick health check for a chunk set. Run this after ingesting a
    document and confirm p10 sits well above fragment-sized (~20-40 char)
    territory before touching anything downstream (retriever weights,
    reranker thresholds, etc.) — cheaper and more honest than eyeballing
    search results after every ingestion tweak."""
    lengths = sorted(len(c.page_content) for c in chunks)
    if not lengths:
        return {"n": 0}
    n = len(lengths)
    return {
        "n": n,
        "median": statistics.median(lengths),
        "p10": lengths[max(0, n // 10 - 1)] if n >= 10 else lengths[0],
        "min": lengths[0],
        "max": lengths[-1],
    }


# Table detection — ruled-border pass, then whitespace-alignment pass for
# borderless tables, restricted to regions the first pass didn't claim

def _find_tables(page: "pdfplumber.page.Page") -> list:
    """Ruled-border ('lines') detection runs first since it's high
    precision. Whitespace-alignment ('text') detection then fills in
    tables with no visible ruling — but only where the first pass found
    nothing, since text-strategy detection can over-segment ordinary
    paragraphs if applied everywhere. Disable via
    config.ENABLE_BORDERLESS_TABLE_DETECTION = False if it misfires on
    your document set."""
    bordered = page.find_tables()
    if not _ENABLE_BORDERLESS_TABLES:
        return bordered

    bordered_bboxes = [t.bbox for t in bordered]
    borderless = page.find_tables(table_settings={
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
    })
    borderless = [t for t in borderless if not _bbox_overlaps_any(t.bbox, bordered_bboxes)]

    return bordered + borderless


def _bbox_overlaps_any(bbox: tuple, other_bboxes: list) -> bool:
    x0, top, x1, bottom = bbox
    for (ox0, otop, ox1, obottom) in other_bboxes:
        if x0 < ox1 and x1 > ox0 and top < obottom and bottom > otop:
            return True
    return False


# Table region exclusion (geometric)

def _is_within_any_bbox(obj: dict, bboxes: list, tolerance: float = 2.0) -> bool:
    """
    True if a pdfplumber layout object (char, word) falls inside any table
    bbox. page.extract_tables() only gives cell strings, not bboxes —
    page.find_tables() gives both, so text can be excluded by geometry
    instead of fragile string matching.
    """
    obj_top, obj_bottom = obj.get("top"), obj.get("bottom")
    obj_x0, obj_x1 = obj.get("x0"), obj.get("x1")
    if None in (obj_top, obj_bottom, obj_x0, obj_x1):
        return False
    for (x0, top, x1, bottom) in bboxes:
        if (obj_x0 >= x0 - tolerance and obj_x1 <= x1 + tolerance and
                obj_top >= top - tolerance and obj_bottom <= bottom + tolerance):
            return True
    return False


# Page line extraction — words grouped into lines, carrying font size and
# excluding table regions and rotated (sideways) text

def _extract_page_lines(page: "pdfplumber.page.Page", table_bboxes: list) -> List[dict]:
    """Group visible (non-table, upright) words into text lines with
    position + font-size info. This replaces plain extract_text(): it
    lets headers be detected by actual layout (font size) rather than
    capitalization pattern alone, and it drops rotated glyphs (sidebar
    banners, vertical divider labels) instead of letting them get sorted
    into normal reading order and come out scrambled."""
    words = page.extract_words(extra_attrs=["size", "upright"])
    visible = [
        w for w in words
        if w.get("upright", True) and not _is_within_any_bbox(w, table_bboxes)
    ]
    if not visible:
        return []

    visible.sort(key=lambda w: (w["top"], w["x0"]))

    lines: List[dict] = []
    bucket: List[dict] = []
    bucket_top = visible[0]["top"]
    tolerance = 3.0

    for w in visible:
        if bucket and abs(w["top"] - bucket_top) > tolerance:
            lines.append(_finalize_line(bucket))
            bucket = []
        if not bucket:
            bucket_top = w["top"]
        bucket.append(w)
    if bucket:
        lines.append(_finalize_line(bucket))

    return lines


def _finalize_line(words: List[dict]) -> dict:
    words_sorted = sorted(words, key=lambda w: w["x0"])
    text = " ".join(w["text"] for w in words_sorted)
    sizes = [w["size"] for w in words_sorted if w.get("size")]
    size = statistics.median(sizes) if sizes else 0.0
    top = min(w["top"] for w in words_sorted)
    return {"text": text, "size": size, "top": top}


def _page_body_font_size(lines: List[dict]) -> float:
    """Median line font size on the page, used as the body-text baseline
    that a header's font size must meaningfully exceed."""
    sizes = [l["size"] for l in lines if l["size"]]
    return statistics.median(sizes) if sizes else 0.0


# Section header detection

def _is_section_header(line_text: str, line_size: float, body_size: float) -> bool:
    """A line only counts as a genuine section header if it matches a
    header-like text pattern AND (unless the pattern is unambiguous on
    its own) is rendered in a meaningfully larger font than the page's
    body text. Text pattern alone matches far too many proper-noun
    phrases in financial documents — subsidiary names, director names,
    rating agencies, award titles — to be reliable by itself."""
    if not line_text or len(line_text) > 90:
        return False

    if _ITEM_HEADER_RE.match(line_text):
        return True  # "Item 7. MD&A" style headers are unambiguous regardless of font

    letters = [c for c in line_text if c.isalpha()]
    is_all_caps = len(letters) >= 6 and all(c.isupper() for c in letters)
    is_title_case = _is_title_case_subheading(line_text)

    if not (is_all_caps or is_title_case):
        return False

    if body_size <= 0:
        # No reliable font baseline on this page (e.g. missing font info) —
        # fall back to ALL-CAPS only, since Title Case alone is far too
        # loose a signal to use without the font check backing it up.
        return is_all_caps

    return line_size >= body_size * _HEADER_FONT_SIZE_RATIO


def _is_title_case_subheading(line: str) -> bool:
    words = line.split()
    if not (2 <= len(words) <= 8) or line.endswith((".", ",", ";", ":")):
        return False
    minor = {"and", "of", "the", "in", "for", "to", "on", "at", "by"}
    for w in words:
        clean = w.strip(",:;")
        if clean.lower() in minor:
            continue
        if not clean[:1].isupper():
            return False
    return True


# Section-boundary splitting (so a chunk can never straddle two subsections)

def _split_into_section_blocks(lines: List[dict], carry_in_section: str) -> Tuple[List[Tuple[str, str]], str]:
    """Splits page lines at genuine header lines so a downstream chunk can
    never straddle two subsections. Returns (blocks, section_to_carry_to_next_page)."""
    blocks: List[Tuple[str, str]] = []
    current_section = carry_in_section
    current_lines: List[str] = []

    body_size = _page_body_font_size(lines)

    for line in lines:
        text = line["text"].strip()
        if not text:
            continue
        if _is_section_header(text, line["size"], body_size):
            if current_lines:
                blocks.append((current_section, "\n".join(current_lines)))
                current_lines = []
            current_section = text
        else:
            current_lines.append(text)

    if current_lines:
        blocks.append((current_section, "\n".join(current_lines)))
    return blocks, current_section


# Quality gate — merge (never drop) blocks too short to be useful on their own

def _merge_short_blocks(blocks: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Folds very short blocks into the previous block instead of emitting
    them as their own tiny, context-poor chunk. Even after fixing header
    detection, some genuinely short blocks remain (a one-line disclosure,
    a short callout) — merging preserves that content instead of dropping
    or isolating it."""
    merged: List[Tuple[str, str]] = []
    for section, text in blocks:
        if merged and len(text.strip()) < _MIN_BLOCK_CHARS:
            prev_section, prev_text = merged[-1]
            merged[-1] = (prev_section, prev_text + "\n" + text)
        else:
            merged.append((section, text))
    return merged


# Narrative chunking

def _build_narrative_chunks(
    text: str, doc_name: str, section: str, page_num: int, doc_date: datetime,
    asset: str = "UNSCOPED", multi_asset: bool = False,
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
                metadata=_build_metadata(doc_name, section, page_num, "narrative", doc_date, contextualized, asset, multi_asset),
            )
        )
    return documents


# Table chunking — atomic, never split mid-row

def _build_table_chunks(
    table: List[List[Optional[str]]], doc_name: str, section: str, page_num: int, doc_date: datetime,
    asset: str, multi_asset: bool,
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
                metadata=_build_metadata(doc_name, section, page_num, "table", doc_date, contextualized, asset, multi_asset),
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


# Shared helpers

def _build_metadata(
    doc_name: str, section: str, page_num: int, chunk_type: str, doc_date: datetime,
    chunk_text: str, asset: str = "UNSCOPED", multi_asset: bool = False,
) -> dict:
    return {
        "doc_name": doc_name,
        "section": section,
        "page": page_num,
        "chunk_type": chunk_type,
        "doc_date": doc_date.isoformat(),
        "chunk_id": _stable_chunk_id(doc_name, page_num, chunk_type, chunk_text),
        "asset": asset,
        "multi_asset": multi_asset,
    }


def _stable_chunk_id(doc_name: str, page_num: int, chunk_type: str, chunk_text: str) -> str:
    """Reproducible across re-ingestion runs — unlike Python's hash(), which
    is randomized per-process (PYTHONHASHSEED) and unsafe to persist or
    compare across runs, which is what vector_store.py's _document_key()
    currently relies on."""
    digest_input = f"{doc_name}::{page_num}::{chunk_type}::{chunk_text}".encode("utf-8")
    return hashlib.sha1(digest_input).hexdigest()[:16]


def _infer_doc_date(file_path: str) -> datetime:
    """Falls back to file modification time when no explicit publish date is given."""
    mtime = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _document_asset_policy(doc_name: str, explicit_asset: Optional[str]) -> Tuple[str, bool]:
    if explicit_asset and explicit_asset.strip():
        return _canonical_asset(explicit_asset), False
    haystack = doc_name.upper()
    matches = []
    for ticker, aliases in config.ASSET_ALIASES.items():
        tokens = [ticker, *aliases]
        if any(token.upper() in haystack for token in tokens):
            matches.append(ticker)
    if len(matches) == 1:
        return matches[0], False
    return ("MULTI_ASSET", True) if len(matches) > 1 else ("UNSCOPED", False)


def _canonical_asset(asset: str) -> str:
    token = " ".join(asset.upper().split())
    for ticker, aliases in config.ASSET_ALIASES.items():
        if token == ticker or token in {" ".join(a.upper().split()) for a in aliases}:
            return ticker
    return token
