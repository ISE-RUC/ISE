from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeChunk:
    source_id: str
    source_title: str
    chunk_id: str
    content: str


@dataclass(frozen=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float
    matched_terms: tuple[str, ...]

