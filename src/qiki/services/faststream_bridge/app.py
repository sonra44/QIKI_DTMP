import logging
from faststream import FastStream, Logger
from faststream.nats import NatsBroker

# Импортируем наши Pydantic модели
# Важно, чтобы PYTHONPATH был настроен правильно, чтобы найти shared
# В Docker-окружении это будет работать, так как корень проекта - /workspace
from shared.models.core import CommandMessage, ResponseMessage, MessageMetadata

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация NATS брокера
# Имя контейнера 'qiki-nats-phase1' используется как хост
broker = NatsBroker("nats://qiki-nats-phase1:4222")
app = FastStream(broker)


@broker.subscriber("qiki.commands.control")
@broker.publisher("qiki.responses.control")
async def handle_control_command(
    msg: CommandMessage, logger: Logger
) -> ResponseMessage:
    """
    Этот обработчик принимает команды управления, логирует их
    и возвращает простое подтверждение.
    """
    logger.info(f"Received command: {msg.command_name}")
    logger.info(f"Parameters: {msg.parameters}")

    # Простое бизнес-логика: отвечаем успехом
    response_payload = {
        "status": "Command received",
        "command": msg.command_name,
    }

    response = ResponseMessage(
        request_id=msg.metadata.message_id,
        metadata=MessageMetadata(
            source="faststream_bridge", correlation_id=msg.metadata.message_id
        ),
        payload=response_payload,
        success=True,
    )

    logger.info(f"Sending response: {response}")
    return response


@app.on_startup
async def on_startup():
    logger.info("FastStream bridge service has started.")


@app.on_shutdown
async def on_shutdown():
    logger.info("FastStream bridge service is shutting down.")
