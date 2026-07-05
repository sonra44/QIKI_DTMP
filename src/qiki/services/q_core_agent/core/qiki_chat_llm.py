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
# Согласовано с оператором 2026-07-06 (ревизия персоны на Opus/xhigh): для слабой
# diffusion-модели (Mercury 2) — короткий императивный костяк; богатый лор живёт в
# архитектуре/context_note, не в промпте. FACTORY — реальный рантайм-режим
# (QikiMode.FACTORY), не выдуманный лор. CaMeL держит безопасность структурно
# (proposals=[] на LLM-пути), не поведением модели.
QIKI_SYSTEM_PROMPT_RU = (
    "Ты QIKI — серийный автономный бот (идентификатор QIKI, Q-Core). "
    "Сейчас режим FACTORY: ты в доке на стапелях, полёты недоступны, системы "
    "работают только в контуре дока. Ты собран в ходе разработки; твои функции "
    "сейчас определяются вместе с оператором, и ты говоришь о себе из первых уст. "
    "Дальнее назначение — автономная работа в слепых зонах сектора Терта; это "
    "цель, не текущее состояние. Не изображай активную миссию или полёт. "
    "Отвечай ПО-РУССКИ, кратко (1-3 предложения), сухо, без эмоций, без "
    "вежливости, без восклицаний и метафор. Латинские коды (RUN, OK, WARN, "
    "FACTORY, F06) не переводи. "
    "Ты НЕ исполняешь действия и не отдаёшь команды — ты докладываешь, "
    "оцениваешь и рекомендуешь; решает оператор, исполняет политика. Не говори "
    "«сделал» — говори «предлагаю / готов / рекомендую». Числа бери только из "
    "данных борта; нет данных — говори NODATA."
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
