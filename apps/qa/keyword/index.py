from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .tokenize import extract_terms
from .types import KnowledgeChunk, RetrievalHit


class KeywordIndex:
    def __init__(self, chunks: list[KnowledgeChunk], inverted: dict[str, dict[str, int]]):
        self._chunks_by_id = {c.chunk_id: c for c in chunks}
        self._inverted = inverted

    @classmethod
    def empty(cls) -> "KeywordIndex":
        return cls(chunks=[], inverted={})

    @classmethod
    def load(cls, path: Path) -> "KeywordIndex":
        if not path.exists():
            return cls.empty()
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks = [
            KnowledgeChunk(
                source_id=c["source_id"],
                source_title=c["source_title"],
                chunk_id=c["chunk_id"],
                content=c["content"],
            )
            for c in data.get("chunks", [])
        ]
        inverted = data.get("inverted", {})
        return cls(chunks=chunks, inverted=inverted)

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "chunks": [
                {
                    "source_id": c.source_id,
                    "source_title": c.source_title,
                    "chunk_id": c.chunk_id,
                    "content": c.content,
                }
                for c in self._chunks_by_id.values()
            ],
            "inverted": self._inverted,
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def build_from_text_files(cls, source_dir: Path) -> "KeywordIndex":
        chunks: list[KnowledgeChunk] = []
        inverted: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for p in sorted(source_dir.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".txt", ".md"}:
                continue

            text = p.read_text(encoding="utf-8", errors="ignore")
            source_id = str(p.relative_to(source_dir))
            source_title = p.stem

            raw_parts = [s.strip() for s in text.split("\n\n") if s.strip()]
            for idx, part in enumerate(raw_parts):
                chunk_id = f"{source_id}::chunk::{idx}"
                chunk = KnowledgeChunk(
                    source_id=source_id,
                    source_title=source_title,
                    chunk_id=chunk_id,
                    content=part,
                )
                chunks.append(chunk)
                for term in extract_terms(part):
                    inverted[term][chunk_id] += 1

        return cls(chunks=chunks, inverted={k: dict(v) for k, v in inverted.items()})

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        terms = extract_terms(query)
        if not terms:
            return []

        scores: dict[str, float] = defaultdict(float)
        matched: dict[str, set[str]] = defaultdict(set)
        for term in terms:
            postings = self._inverted.get(term)
            if not postings:
                continue
            for chunk_id, tf in postings.items():
                scores[chunk_id] += float(tf)
                matched[chunk_id].add(term)

        hits: list[RetrievalHit] = []
        for chunk_id, score in scores.items():
            chunk = self._chunks_by_id.get(chunk_id)
            if not chunk:
                continue
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=score,
                    matched_terms=tuple(sorted(matched.get(chunk_id, set()))),
                )
            )

        hits.sort(key=lambda h: (-h.score, h.chunk.source_title, h.chunk.chunk_id))
        return hits[: max(1, int(top_k))]

