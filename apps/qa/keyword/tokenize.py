from __future__ import annotations

import re


_WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


def _cjk_bigrams(text: str) -> list[str]:
    if len(text) < 2:
        return []
    return [text[i : i + 2] for i in range(len(text) - 1)]


def extract_terms(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    terms: list[str] = []
    for m in _WORD_RE.finditer(text):
        s = m.group(0).strip()
        if not s:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", s):
            if len(s) >= 2:
                terms.append(s)
            terms.extend(_cjk_bigrams(s))
        else:
            if len(s) >= 2:
                terms.append(s.lower())

    seen: set[str] = set()
    deduped: list[str] = []
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)
    return deduped

