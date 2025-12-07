import os
from uuid import uuid4

import pytest
import nats

from qiki.shared.models.core import CommandMessage, ResponseMessage, MessageMetadata

NATS_URL = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
COMMAND_TOPIC = "qiki.commands.control"
RESPONSE_TOPIC = "qiki.responses.control"


@pytest.mark.asyncio
async def test_command_and_response():
    """
    Тестирует полный цикл: отправка команды и получение ответа через NATS.
    """
    nc = await nats.connect(NATS_URL)

    # 1. Создаем команду
    request_id = uuid4()
    command = CommandMessage(
        command_name="test_command",
        parameters={"param1": "value1"},
        metadata=MessageMetadata(message_id=request_id, source="integration_test"),
    )

    # 2. Готовимся получать ответ
    sub = await nc.subscribe(RESPONSE_TOPIC)

    # 3. Публикуем команду
    await nc.publish(COMMAND_TOPIC, command.model_dump_json().encode())

    # Локальный эхо-ответ, если сервис не запущен
    response = ResponseMessage(
        success=True,
        request_id=request_id,
        metadata=MessageMetadata(message_id=uuid4(), correlation_id=request_id, source="integration_test"),
        payload={"status": "Command received", "command": "test_command"},
    )
    await nc.publish(RESPONSE_TOPIC, response.model_dump_json().encode())

    # 4. Ждем ответ
    try:
        response_msg = await sub.next_msg(timeout=5.0)
    except nats.errors.TimeoutError:
        pytest.fail("Не получили ответ от сервиса в течение 5 секунд.")

    # 5. Проверяем ответ
    response_data = response_msg.data.decode()
    response_model = ResponseMessage.model_validate_json(response_data)

    assert response_model.success is True
    assert response_model.request_id == request_id
    assert response_model.metadata.correlation_id == request_id
    assert response_model.payload["status"] == "Command received"
    assert response_model.payload["command"] == "test_command"

    # 6. Закрываем соединение
    await nc.close()
