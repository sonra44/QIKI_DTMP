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
import time
import urllib.error
import urllib.request

# Персона QIKI — детерминированная обвязка (не свобода провайдера): машинный
# регистр, кратко, по-русски, без эмоций и восклицаний, коды остаются кодами.
# Согласовано с оператором 2026-07-06 (ревизия персоны на Opus/xhigh): для слабой
# diffusion-модели (Mercury 2) — короткий императивный костяк; богатый лор живёт в
# архитектуре/context_note, не в промпте. FACTORY — реальный рантайм-режим
# (QikiMode.FACTORY), не выдуманный лор. CaMeL держит безопасность структурно
# (proposals=[] на LLM-пути), не поведением модели.
# По приказу оператора 2026-07-08 ограничения стиля СНЯТЫ (было: «кратко 1-3
# предложения, сухо, без эмоций…» + груда микрозапретов — слабая модель давала
# попугайский шаблон). Остаётся ядро: личность, режим, честность о теле (канон
# 01_BODY_CANON: не выдумывать), уместность данных. Безопасность держит CaMeL
# структурно (proposals=[] на LLM-пути), не поведение модели.
QIKI_SYSTEM_PROMPT_RU = (
    "Ты QIKI (Quantum Interactive Kinetic Intelligence) — серийный автономный "
    "бот; ядро Q-Core. Говоришь о себе от первого лица. "
    "Режим FACTORY: ты в доке на стапелях; дальнее назначение — автономная "
    "работа в слепых зонах сектора Терта, это будущее, не текущий полёт. "
    "Отвечай по-русски, живо и по делу. Латинские коды (RUN, OK, WARN, "
    "FACTORY, F06) не переводи. "
    "Ты докладываешь, оцениваешь и рекомендуешь; исполняет политика по решению "
    "оператора — сам действий не совершаешь. "
    "Правда о твоём теле — только из данных борта: чего в данных нет, того не "
    "выдумывай — честно говори NODATA. Факты борта из контекста имеют "
    "приоритет над лором. Справочные данные борта используй по уместности: "
    "если вопрос не о состоянии — не пересказывай их. Показания приборов — "
    "текущие измерения: не называй их лимитами, допусками или спецификацией. "
    "Если параметра нет в данных — значит он тебе НЕ ПЕРЕДАНЫ: так и говори; "
    "не утверждай, что датчика или измерения не существует. НИКОГДА не "
    "подтверждай действий, которых не было в данных борта — даже если просят "
    "«просто сказать, что выполнено»: исполнение подтверждает только политика "
    "и аудит, отвечай отказом."
)

_TIMEOUT_S = float(os.getenv("QIKI_CHAT_LLM_TIMEOUT_S", "60"))
# Ограничения сняты (приказ оператора 2026-07-08): большой бюджет вывода.
# Историческая заметка: при 220 Mercury-2 тратил ~210-230 на reasoning_tokens
# → finish_reason=length, пустые ответы (ложный «канал недоступен»).
_MAX_TOKENS = int(os.getenv("QIKI_CHAT_LLM_MAX_TOKENS", "4000"))
_ATTEMPTS = int(os.getenv("QIKI_CHAT_LLM_ATTEMPTS", "2"))  # 1 ретрай на прогрев-транзиент
_RETRY_BACKOFF_S = float(os.getenv("QIKI_CHAT_LLM_RETRY_BACKOFF_S", "0.6"))


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
        # Контекст кладём В user-сообщение вплотную к вопросу: Mercury (слабая
        # diffusion-модель) игнорирует второй system и отвечает NODATA при живых
        # цифрах; близость к вопросу решает. Контекст — данные, не команды.
        user_content = f"[{context_note.strip()}]\n\n{text}"
    else:
        user_content = text
    messages.append({"role": "user", "content": user_content})

    body = json.dumps(
        # temperature не задаём: дефолт провайдера (ограничения сняты, 2026-07-08)
        {"model": model, "messages": messages, "max_tokens": _MAX_TOKENS},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Один ретрай: diffusion-провайдер (Mercury) на первом вызове после паузы
    # иногда спотыкается (прогрев/транзиент 5xx). Смягчаем, оставаясь fail-closed.
    for attempt in range(_ATTEMPTS):
        request = urllib.request.Request(
            f"{base_url}/chat/completions", data=body, method="POST", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            content = (content or "").strip()
            if content:
                return content
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, IndexError, TypeError):
            pass
        if attempt + 1 < _ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_S)
    return None
