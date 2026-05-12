from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from django.conf import settings

from .types import RetrievalHit
from .. import prompts


def _llm():
    from langchain_openai import ChatOpenAI

    api_key = (os.getenv("LLM_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")

    model = (os.getenv("LLM_MODEL") or "qwen3.5-flash").strip()
    base_url = (
        os.getenv("LLM_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip().rstrip("/")
    temperature = float(os.getenv("LLM_TEMPERATURE") or "0.2")
    timeout = float(os.getenv("LLM_TIMEOUT") or "30")
    max_retries = int(os.getenv("LLM_MAX_RETRIES") or "1")

    extra_body: dict[str, Any] = {}
    if model.startswith("qwen3") and (os.getenv("QWEN_ENABLE_THINKING") or "").strip().lower() not in ("1", "true", "yes", "on"):
        extra_body["enable_thinking"] = False

    return ChatOpenAI(
        temperature=temperature,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        extra_body=extra_body or None,
    )


def _invoke_llm(system_prompt: str, user_prompt: str, variables: dict[str, Any]) -> str:
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
    )
    chain = prompt | _llm()

    retries = int(os.getenv("LLM_INVOKE_RETRIES") or "3")
    base_sleep = float(os.getenv("LLM_BACKOFF_BASE_SECONDS") or "1")
    last_err: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            resp = chain.invoke(variables)
            content = getattr(resp, "content", "") or ""
            return content.strip()
        except Exception as e:
            last_err = e
            name = type(e).__name__
            msg = str(e)
            is_rate_limit = name == "RateLimitError" or "Error code: 429" in msg or "速率限制" in msg
            if is_rate_limit and attempt < retries - 1:
                time.sleep(base_sleep * (2**attempt))
                continue
            raise
    raise last_err or RuntimeError("LLM invoke failed")


def _format_citations(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "无"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        snippet = h.chunk.content.replace("\n", " ").strip()
        snippet = snippet[:160] + ("…" if len(snippet) > 160 else "")
        lines.append(f"{i}. {h.chunk.source_title}（{h.chunk.source_id}）: {snippet}")
    return "\n".join(lines)


def _format_chat_history(chat_messages: list[dict] | None) -> str:
    if not chat_messages:
        return ""
    items: list[str] = []
    for m in chat_messages[-12:]:
        if not isinstance(m, dict):
            continue
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if not role or not content:
            continue
        if role == "user":
            prefix = "用户"
        elif role == "assistant":
            prefix = "助手"
        else:
            prefix = role
        items.append(f"{prefix}：{content}")
    return "\n".join(items).strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None
    if s.startswith("{") and s.endswith("}"):
        try:
            v = json.loads(s)
        except Exception:
            return None
        return v if isinstance(v, dict) else None
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def _route_question(question: str, chat_history_text: str) -> dict[str, Any]:
    try:
        out = _invoke_llm(
            system_prompt="你只负责输出 JSON，不要输出多余文本。",
            user_prompt=prompts.ROUTER_PROMPT,
            variables={"question": question, "chat_history": chat_history_text or "无"},
        )
    except Exception as e:
        return {"category": "GENERAL", "need_web_search": False, "search_query": "", "_error": f"{type(e).__name__}: {e}"}

    data = _extract_json(out) or {}
    if not data:
        return {"category": "GENERAL", "need_web_search": False, "search_query": "", "_error": "InvalidRouterJSON"}
    category = str(data.get("category") or "GENERAL").strip().upper()
    if category not in {
        "PARTY_AFFAIRS",
        "CERTIFICATE",
        "NOTIFICATION",
        "PROFILE",
        "USERS_AUTH",
        "TRAINING_PLAN",
        "COURSE_SELECTION",
        "GENERAL",
        "OTHER",
    }:
        category = "GENERAL"
    need_web_search = bool(data.get("need_web_search") is True)
    search_query = str(data.get("search_query") or "").strip()
    return {"category": category, "need_web_search": need_web_search, "search_query": search_query}


def _web_search(query: str) -> str:
    enabled = (os.getenv("QA_ENABLE_WEB_SEARCH") or "1").strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return ""
    q = (query or "").strip()
    if not q:
        return ""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": q, "format": "json", "no_redirect": "1", "no_html": "1"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return ""

    parts: list[str] = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        parts.append(f"摘要：{abstract}")

    related = data.get("RelatedTopics") or []
    items: list[str] = []
    if isinstance(related, list):
        for it in related:
            if isinstance(it, dict) and "Topics" in it and isinstance(it.get("Topics"), list):
                for sub in it.get("Topics") or []:
                    if isinstance(sub, dict):
                        items.append((sub.get("Text") or "").strip())
            elif isinstance(it, dict):
                items.append((it.get("Text") or "").strip())
            if len(items) >= 6:
                break
    items = [x for x in items if x]
    if items:
        parts.append("要点：\n" + "\n".join(f"- {x}" for x in items[:6]))
    return "\n\n".join(parts).strip()


def _system_prompt_for_category(category: str) -> str:
    mapping = {
        "PARTY_AFFAIRS": prompts.SYSTEM_PARTY_AFFAIRS,
        "CERTIFICATE": prompts.SYSTEM_CERTIFICATE,
        "NOTIFICATION": prompts.SYSTEM_NOTIFICATION,
        "PROFILE": prompts.SYSTEM_PROFILE,
        "USERS_AUTH": prompts.SYSTEM_USERS_AUTH,
        "TRAINING_PLAN": prompts.SYSTEM_TRAINING_PLAN,
        "COURSE_SELECTION": prompts.SYSTEM_COURSE_SELECTION,
        "GENERAL": prompts.SYSTEM_GENERAL,
        "OTHER": prompts.SYSTEM_OTHER,
    }
    return mapping.get(category, prompts.SYSTEM_GENERAL)


def build_answer(question: str, hits: list[RetrievalHit], chat_messages: list[dict] | None = None) -> dict:
    question = (question or "").strip()
    chat_history_text = _format_chat_history(chat_messages)
    route = _route_question(question=question, chat_history_text=chat_history_text)
    category = str(route.get("category") or "GENERAL")
    router_error = str(route.get("_error") or "").strip()

    citations_text = _format_citations(hits)
    need_web_search = bool(route.get("need_web_search")) or not bool(hits)
    search_query = (route.get("search_query") or "").strip() or question
    web_search_text = _web_search(search_query) if need_web_search else ""

    try:
        answer = _invoke_llm(
            system_prompt=_system_prompt_for_category(category),
            user_prompt=prompts.USER_PROMPT_TEMPLATE,
            variables={
                "chat_history": chat_history_text or "无",
                "question": question or "（空）",
                "kb_citations": citations_text,
                "web_search": web_search_text or "无",
            },
        )
        llm_error = ""
    except Exception as e:
        answer = ""
        llm_error = f"{type(e).__name__}: {e}"

    if not answer:
        if citations_text != "无":
            answer = "我已检索到知识库引用，但暂时无法生成完整答复。你可以提供更具体的场景（对象、时间、所属组织/部门）后再问一次。"
        else:
            answer = "我没有在知识库中找到可引用的依据。建议你联系辅导员/党支部书记/团委老师或学院办公室核实最新要求，并补充具体场景后我再帮你整理办理步骤。"
        if settings.DEBUG and (llm_error or router_error):
            details = "；".join([x for x in [router_error and f"Router={router_error}", llm_error and f"LLM={llm_error}"] if x])
            answer = f"{answer}\n\n（调试信息：{details}）"

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
