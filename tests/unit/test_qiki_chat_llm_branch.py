"""LLM-ветка диалога QIKI (F5, CaMeL): провайдер даёт ТОЛЬКО текст, не действия.

RED-инвариант: сколько бы LLM ни «предлагал», путь никогда не создаёт
proposed_action; сбой провайдера — честная структурная реплика, не немой.
"""

from __future__ import annotations

import qiki.services.q_core_agent.core.qiki_chat_llm as llm


def test_disabled_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gw/v1")
    assert llm.llm_dialog_enabled() is False
    assert llm.generate_qiki_reply("привет") is None


def test_enabled_with_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "vk-x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gw/v1")
    assert llm.llm_dialog_enabled() is True


def test_empty_text_no_call(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "vk-x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gw/v1")

    def _boom(*a, **k):
        raise AssertionError("должно не дойти до сети")

    monkeypatch.setattr(llm.urllib.request, "urlopen", _boom)
    assert llm.generate_qiki_reply("   ") is None


def test_network_error_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "vk-x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gw/v1")

    def _fail(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(llm.urllib.request, "urlopen", _fail)
    assert llm.generate_qiki_reply("как дела") is None


def test_parses_chat_completions_shape(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "vk-x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gw/v1")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            import json
            return json.dumps(
                {"choices": [{"message": {"role": "assistant", "content": "Состояние стабильное."}}]}
            ).encode("utf-8")

    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert llm.generate_qiki_reply("доложи") == "Состояние стабильное."


def test_system_prompt_is_machine_register() -> None:
    p = llm.QIKI_SYSTEM_PROMPT_RU
    assert "не переводи" in p.lower()  # коды кодами (языковая рамка)
    assert "не исполняешь действия" in p.lower()  # CaMeL: не control flow
    assert "factory" in p.lower()  # честное текущее состояние (реальный режим)
    assert "из первых уст" in p.lower()  # происхождение: функции определяются
    assert "не изображай активную миссию" in p.lower()  # без оверклейма (Терта = цель)
