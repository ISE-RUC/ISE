from __future__ import annotations

from .types import RetrievalHit
from .. import prompts


PARTY_AFFAIRS_KEYWORDS = (
    "入党",
    "党员",
    "预备党员",
    "发展对象",
    "积极分子",
    "党支部",
    "团员",
    "团关系",
    "团员关系",
    "转接",
    "团委",
    "组织生活",
    "党费",
    "推优",
    "评优",
    "评先",
)


def is_party_affairs_question(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    return any(k in q for k in PARTY_AFFAIRS_KEYWORDS)


def _format_citations(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "无"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        snippet = h.chunk.content.replace("\n", " ").strip()
        snippet = snippet[:160] + ("…" if len(snippet) > 160 else "")
        lines.append(f"{i}. {h.chunk.source_title}（{h.chunk.source_id}）: {snippet}")
    return "\n".join(lines)


def build_answer(question: str, hits: list[RetrievalHit]) -> dict:
    question = (question or "").strip()

    if not is_party_affairs_question(question):
        return {
            "answer": prompts.REFUSAL_NON_PARTY_AFFAIRS,
            "citations": [],
            "hits": [],
        }

    if not hits:
        return {
            "answer": prompts.EMPTY_KB,
            "citations": [],
            "hits": [],
        }

    citations_text = _format_citations(hits)
    answer = prompts.ANSWER_TEMPLATE.format(
        conclusion="已检索到与问题相关的学院材料片段，建议按以下要点核对办理要求。",
        steps="1. 请根据引用片段确认适用对象与办理条件\n2. 按引用片段中的流程步骤准备材料\n3. 如存在时间节点或例外情况，以最新通知为准",
        materials="1. 以引用片段中的材料清单为准\n2. 如引用未覆盖材料清单，请补充具体场景后再提问",
        notes="1. 该回答基于关键词检索结果，可能存在遗漏\n2. 若引用片段互相冲突，请以最新版本或学院最新通知为准",
        citations=citations_text,
    )
    return {
        "answer": answer,
        "citations": [{"title": h.chunk.source_title, "source_id": h.chunk.source_id} for h in hits],
        "hits": [
            {
                "score": h.score,
                "source_title": h.chunk.source_title,
                "source_id": h.chunk.source_id,
                "chunk_id": h.chunk.chunk_id,
                "matched_terms": list(h.matched_terms),
                "content": h.chunk.content,
            }
            for h in hits
        ],
    }

