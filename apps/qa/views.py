import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from ninja import Router, Schema
from ninja.security import django_auth

from .keyword.service import QaKeywordService
from utils.response import error, success


SESSION_CONVERSATIONS_KEY = "qa_conversations"
SESSION_ACTIVE_CONVERSATION_KEY = "qa_active_conversation_id"

router = Router()


def _bootstrap_message() -> dict:
    return {
        "role": "assistant",
        "content": "你好，我是智能问答助手。你可以在同一组对话中连续提问，我会结合上下文与学院材料进行检索与引用。\n\n例如：\n- 入党流程怎么走？\n- 需要准备哪些材料？\n- 其中“推优”一般指什么？",
    }


def _get_conversations(request) -> list[dict]:
    conversations = request.session.get(SESSION_CONVERSATIONS_KEY)
    if not isinstance(conversations, list):
        return []
    result: list[dict] = []
    for c in conversations:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        title = c.get("title") or "新对话"
        messages = c.get("messages") if isinstance(c.get("messages"), list) else []
        hits = c.get("hits") if isinstance(c.get("hits"), list) else []
        updated_at = int(c.get("updated_at") or 0)
        result.append(
            {
                "id": cid,
                "title": str(title)[:60],
                "messages": [m for m in messages if isinstance(m, dict) and m.get("role") and m.get("content")][-80:],
                "hits": [h for h in hits if isinstance(h, dict)][:12],
                "updated_at": updated_at,
            }
        )
    return [c for c in result if c.get("id")]


def _set_conversations(request, conversations: list[dict]) -> None:
    request.session[SESSION_CONVERSATIONS_KEY] = conversations[-30:]


def _make_conversation_id() -> str:
    import uuid

    return uuid.uuid4().hex


def _create_conversation(request) -> dict:
    conv = {
        "id": _make_conversation_id(),
        "title": "新对话",
        "messages": [_bootstrap_message()],
        "hits": [],
        "updated_at": 0,
    }
    conversations = _get_conversations(request)
    conversations.insert(0, conv)
    _set_conversations(request, conversations)
    request.session[SESSION_ACTIVE_CONVERSATION_KEY] = conv["id"]
    return conv


def _get_active_conversation_id(request) -> str | None:
    cid = request.session.get(SESSION_ACTIVE_CONVERSATION_KEY)
    return cid if isinstance(cid, str) and cid else None


def _find_conversation(conversations: list[dict], cid: str) -> dict | None:
    for c in conversations:
        if c.get("id") == cid:
            return c
    return None


def _get_or_create_active_conversation(request) -> dict:
    conversations = _get_conversations(request)
    cid = _get_active_conversation_id(request)
    conv = _find_conversation(conversations, cid) if cid else None
    if conv is not None:
        return conv
    if conversations:
        request.session[SESSION_ACTIVE_CONVERSATION_KEY] = conversations[0]["id"]
        return conversations[0]
    return _create_conversation(request)


def _set_active_conversation(request, cid: str) -> dict | None:
    conversations = _get_conversations(request)
    conv = _find_conversation(conversations, cid)
    if conv is None:
        return None
    request.session[SESSION_ACTIVE_CONVERSATION_KEY] = cid
    return conv


def _last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _build_retrieval_query(user_message: str, messages: list[dict]) -> str:
    user_message = (user_message or "").strip()
    if not user_message:
        return ""
    prev = _last_user_message(messages[:-1])
    short_or_ref = len(user_message) <= 12 or any(k in user_message for k in ("它", "这个", "上面", "前面", "刚才", "继续", "那", "然后", "上述", "前一个"))
    if prev and short_or_ref:
        return f"{prev} {user_message}"
    return user_message


class ChatIn(Schema):
    message: str


class SwitchIn(Schema):
    conversation_id: str


def _chat_payload(request, user_message: str) -> dict:
    conversations = _get_conversations(request)
    conv = _get_or_create_active_conversation(request)
    messages: list[dict] = conv.get("messages") or []
    messages.append({"role": "user", "content": user_message})
    retrieval_query = _build_retrieval_query(user_message, messages)
    result = QaKeywordService().ask(retrieval_query, top_k=6, chat_messages=messages)

    assistant_text = (result.get("answer") or "").strip() or "我暂时无法生成回答。请换一种问法，或提供更具体的场景信息。"

    hits = result.get("hits", []) or []
    conv["hits"] = hits[:12]

    messages.append({"role": "assistant", "content": assistant_text})
    conv["messages"] = messages[-80:]
    if conv.get("title") in ("新对话", "", None):
        conv["title"] = user_message[:18] + ("…" if len(user_message) > 18 else "")
    conv["updated_at"] = int(conv.get("updated_at") or 0) + 1
    for i, c in enumerate(conversations):
        if c.get("id") == conv.get("id"):
            conversations.pop(i)
            break
    conversations.insert(0, conv)
    _set_conversations(request, conversations)
    return {
        "assistant": {"role": "assistant", "content": assistant_text},
        "hits": hits,
        "active_conversation_id": conv.get("id"),
        "conversations": [{"id": c.get("id"), "title": c.get("title")} for c in conversations],
    }


def _new_payload(request) -> dict:
    conv = _create_conversation(request)
    conversations = _get_conversations(request)
    return {
        "active_conversation_id": conv.get("id"),
        "conversations": [{"id": c.get("id"), "title": c.get("title")} for c in conversations],
        "messages": conv.get("messages") or [],
        "hits": conv.get("hits") or [],
    }


def _reset_payload(request) -> dict:
    request.session.pop(SESSION_CONVERSATIONS_KEY, None)
    request.session.pop(SESSION_ACTIVE_CONVERSATION_KEY, None)
    return _new_payload(request)


def _switch_payload(request, cid: str) -> dict | None:
    conv = _set_active_conversation(request, cid)
    if conv is None:
        return None
    conversations = _get_conversations(request)
    return {
        "active_conversation_id": conv.get("id"),
        "conversations": [{"id": c.get("id"), "title": c.get("title")} for c in conversations],
        "messages": conv.get("messages") or [],
        "hits": conv.get("hits") or [],
    }


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "qa/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversations = _get_conversations(self.request)
        active = _get_or_create_active_conversation(self.request)
        active_id = active.get("id")
        conversations = _get_conversations(self.request)
        context.update(
            {
                "conversations": [{"id": c.get("id"), "title": c.get("title")} for c in conversations],
                "active_conversation_id": active_id,
                "chat_messages": active.get("messages") or [],
                "hits": active.get("hits") or [],
            }
        )
        return context


class ChatMessageView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        content_type = (request.headers.get("Content-Type") or "").lower()
        if "application/json" in content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return JsonResponse(error(msg="请求格式错误", code=400), status=400)
            user_message = (payload.get("message") or "").strip()
        else:
            user_message = (request.POST.get("message") or "").strip()

        if not user_message:
            return JsonResponse(error(msg="请输入问题", code=400), status=400)

        payload = _chat_payload(request, user_message)
        return JsonResponse(success(data=payload))


class ResetConversationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        return JsonResponse(success(data=_reset_payload(request)))


class NewConversationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        return JsonResponse(success(data=_new_payload(request)))


class SwitchConversationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        content_type = (request.headers.get("Content-Type") or "").lower()
        if "application/json" in content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return JsonResponse(error(msg="请求格式错误", code=400), status=400)
            cid = (payload.get("conversation_id") or "").strip()
        else:
            cid = (request.POST.get("conversation_id") or "").strip()
        if not cid:
            return JsonResponse(error(msg="缺少会话ID", code=400), status=400)
        payload = _switch_payload(request, cid)
        if payload is None:
            return JsonResponse(error(msg="会话不存在", code=404), status=404)
        return JsonResponse(success(data=payload))


@router.post("/chat", auth=django_auth)
def api_chat(request, payload: ChatIn):
    message = (payload.message or "").strip()
    if not message:
        return error(msg="请输入问题", code=400)
    return success(data=_chat_payload(request, message))


@router.post("/new", auth=django_auth)
def api_new(request):
    return success(data=_new_payload(request))


@router.post("/reset", auth=django_auth)
def api_reset(request):
    return success(data=_reset_payload(request))


@router.post("/switch", auth=django_auth)
def api_switch(request, payload: SwitchIn):
    cid = (payload.conversation_id or "").strip()
    if not cid:
        return error(msg="缺少会话ID", code=400)
    data = _switch_payload(request, cid)
    if data is None:
        return error(msg="会话不存在", code=404)
    return success(data=data)
