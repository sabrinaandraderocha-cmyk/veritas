from __future__ import annotations

import io
import re
import html
import difflib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from docx import Document
from pypdf import PdfReader


@dataclass
class Match:
    source_doc: str
    query_chunk: str
    source_chunk: str
    score: float


def extract_text_from_txt_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text_from_docx_bytes(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    table_rows: List[str] = []
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                table_rows.append(" | ".join(cells))
    return "\n".join(paragraphs + table_rows)


def extract_text_from_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-zÀ-ÿ0-9]+", normalize_text(text))


def make_chunks(text: str, chunk_words: int, stride_words: int) -> List[str]:
    words = split_words(text)
    if not words:
        return []
    chunks: List[str] = []
    for start in range(0, len(words), max(1, stride_words)):
        chunk = words[start : start + chunk_words]
        if len(chunk) < max(12, chunk_words // 2):
            break
        chunks.append(" ".join(chunk))
    return list(dict.fromkeys(chunks))


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b), autojunk=False).ratio()


def compute_matches(
    query_text: str,
    library: Dict[str, str],
    chunk_words: int,
    stride_words: int,
    top_k_per_chunk: int,
    threshold: float,
) -> Tuple[float, List[Match]]:
    query_chunks = make_chunks(query_text, chunk_words, stride_words)
    if not query_chunks or not library:
        return 0.0, []

    source_chunks: Dict[str, List[str]] = {
        name: make_chunks(text, chunk_words, stride_words)
        for name, text in library.items()
        if text and text.strip()
    }

    matches: List[Match] = []
    matched_query_indexes = set()

    for idx, query_chunk in enumerate(query_chunks):
        candidates: List[Match] = []
        for source_name, chunks in source_chunks.items():
            for source_chunk in chunks:
                score = _similarity(query_chunk, source_chunk)
                if score >= threshold:
                    candidates.append(Match(source_name, query_chunk, source_chunk, score))
        candidates.sort(key=lambda item: item.score, reverse=True)
        selected = candidates[: max(1, top_k_per_chunk)]
        if selected:
            matched_query_indexes.add(idx)
            matches.extend(selected)

    # Cobertura aproximada de fragmentos do texto analisado. Evita somar scores sobrepostos.
    similarity = len(matched_query_indexes) / len(query_chunks)
    matches.sort(key=lambda item: item.score, reverse=True)
    return similarity, matches


def highlight_text(text: str, matches: Iterable[Match]) -> str:
    safe = html.escape(text or "")
    # Destaque simples e seguro para a versão inicial.
    for match in sorted(matches, key=lambda m: len(m.query_chunk), reverse=True):
        fragment = html.escape(match.query_chunk)
        safe = safe.replace(fragment, f"<mark>{fragment}</mark>")
    return safe.replace("\n", "<br>")
