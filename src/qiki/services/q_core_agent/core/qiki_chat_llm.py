"""LLM-ветка свободной беседы QIKI (F5, пре-W7).

CaMeL-граница (F5-док §1 закон 4): вывод провайдера — только ДАННЫЕ (текст
реплики), НИКОГДА не control flow. Ветка возвращает СТРОКУ; вызывающий код
кладёт её в reply.body и не создаёт из неё ни одного proposed_action.

Трафик идёт ТОЛЬКО через QIKI Gateway (OPENAI_BASE_URL → gateway; реальный
ключ живёт в gateway, здесь — виртуальный). Путь — chat/completions
(Mercury/Inception и большинство совместимых). Fail-структурно: при ошибке
возвращаем None, вызывающий эмитит честную структурную ошибку (не немой сбой).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Персона QIKI — детерминированная обвязка (не свобода провайдера): машинный
# регистр, кратко, по-русски, без эмоций и восклицаний, коды остаются кодами.
QIKI_SYSTEM_PROMPT_RU = (
    "Ты QIKI — автономное машинное тело под наблюдением оператора через пульт ORION V. "
    "Отвечай ПО-РУССКИ, кратко (1-3 предложения), в машинном регистре: сухо, по делу, "
    "без эмоций, без восклицательных знаков, без метафор. Ты не чат-бот и не ассистент — "
    "ты корабельная сущность, докладывающая оператору. Латинские коды и идентификаторы "
    "(RUN, OK, F06, module_id) не переводи. Ты НЕ отдаёшь команды телу и не обещаешь "
    "действий — только информируешь; исполнение решает детерминированная политика."
)

_TIMEOUT_S = float(os.getenv("QIKI_CHAT_LLM_TIMEOUT_S", "25"))
_MAX_TOKENS = int(os.getenv("QIKI_CHAT_LLM_MAX_TOKENS", "220"))


def llm_dialog_enabled() -> bool:
    """Ветка активна только при заданном ключе (виртуальном) и base_url."""
    return bool(os.getenv("OPENAI_API_KEY", "").strip()) and bool(os.getenv("OPENAI_BASE_URL", "").strip())


def generate_qiki_reply(user_text: str, *, context_note: str = "") -> str | None:
    """Свободная реплика QIKI через gateway. Возвращает текст или None при сбое.

    context_note — короткий детерминированный контекст борта (не команды),
    вставляется системным сообщением; провайдер его только читает.
    """
    text = (user_text or "").strip()
    if not text or not llm_dialog_enabled():
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "mercury-2").strip()

    messages = [{"role": "system", "content": QIKI_SYSTEM_PROMPT_RU}]
    if context_note.strip():
        messages.append({"role": "system", "content": f"Контекст борта (только для справки): {context_note.strip()}"})
    messages.append({"role": "user", "content": text})

    body = json.dumps(
        {"model": model, "messages": messages, "max_tokens": _MAX_TOKENS, "temperature": 0.3},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    content = (content or "").strip()
    return content or None
