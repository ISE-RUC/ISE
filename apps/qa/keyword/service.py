from __future__ import annotations

from .answer import build_answer
from .index import KeywordIndex
from .paths import qa_kb_sources_dir, qa_keyword_index_path


class QaKeywordService:
    def __init__(self) -> None:
        self._index: KeywordIndex | None = None

    def _load_index(self) -> KeywordIndex:
        if self._index is not None:
            return self._index

        index_path = qa_keyword_index_path()
        index = KeywordIndex.load(index_path)
        if not index_path.exists():
            source_dir = qa_kb_sources_dir()
            source_dir.mkdir(parents=True, exist_ok=True)
            index = KeywordIndex.build_from_text_files(source_dir)
        self._index = index
        return index

    def ask(self, question: str, top_k: int = 5, chat_messages: list[dict] | None = None) -> dict:
        index = self._load_index()
        hits = index.search(question, top_k=top_k)
        return build_answer(question=question, hits=hits, chat_messages=chat_messages)
