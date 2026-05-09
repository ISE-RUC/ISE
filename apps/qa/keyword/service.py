from __future__ import annotations

import hashlib
import os
import shutil

from .answer import build_answer
from .index import KeywordIndex
from .paths import qa_kb_index_dir, qa_kb_sources_dir, qa_keyword_index_path


def _sources_signature(source_dir) -> str:
    h = hashlib.sha256()
    ocr_lang = (os.getenv("QA_OCR_LANG") or "chi_sim+eng").strip()
    tesseract_path = shutil.which("tesseract") or ""
    h.update(b"extractors\0")
    h.update(f"ocr_lang={ocr_lang}".encode("utf-8"))
    h.update(b"\0")
    h.update(f"tesseract={tesseract_path}".encode("utf-8"))
    h.update(b"\0")
    for p in sorted(source_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        rel = str(p.relative_to(source_dir)).replace("\\", "/")
        st = p.stat()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(int(st.st_mtime)).encode("utf-8"))
        h.update(b"\0")
        h.update(str(int(st.st_size)).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


class QaKeywordService:
    def __init__(self) -> None:
        self._index: KeywordIndex | None = None

    def _load_index(self) -> KeywordIndex:
        if self._index is not None:
            return self._index

        index_path = qa_keyword_index_path()
        sig_path = qa_kb_index_dir() / "sources.sig"
        source_dir = qa_kb_sources_dir()
        source_dir.mkdir(parents=True, exist_ok=True)

        current_sig = _sources_signature(source_dir)
        saved_sig = sig_path.read_text(encoding="utf-8").strip() if sig_path.exists() else ""

        if (not index_path.exists()) or (current_sig != saved_sig):
            index = KeywordIndex.build_from_sources(source_dir)
            index.dump(index_path)
            sig_path.parent.mkdir(parents=True, exist_ok=True)
            sig_path.write_text(current_sig, encoding="utf-8")
        else:
            index = KeywordIndex.load(index_path)
        self._index = index
        return index

    def _refresh_index_if_needed(self) -> None:
        index_path = qa_keyword_index_path()
        sig_path = qa_kb_index_dir() / "sources.sig"
        source_dir = qa_kb_sources_dir()
        source_dir.mkdir(parents=True, exist_ok=True)

        current_sig = _sources_signature(source_dir)
        saved_sig = sig_path.read_text(encoding="utf-8").strip() if sig_path.exists() else ""
        if (not index_path.exists()) or (current_sig != saved_sig):
            index = KeywordIndex.build_from_sources(source_dir)
            index.dump(index_path)
            sig_path.parent.mkdir(parents=True, exist_ok=True)
            sig_path.write_text(current_sig, encoding="utf-8")
            self._index = index

    def ask(self, question: str, top_k: int = 5, chat_messages: list[dict] | None = None) -> dict:
        index = self._load_index()
        self._refresh_index_if_needed()
        index = self._index or index
        hits = index.search(question, top_k=top_k)
        return build_answer(question=question, hits=hits, chat_messages=chat_messages)
