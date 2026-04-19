import pytest

from core.domain.commands import SendReply
from core.domain.enums import Platform
from adapters.outbound.delivery_service import DeliveryService
from tests.fakes.ports import FakeCommandExecutorPort


@pytest.mark.asyncio
async def test_delivery_routes_commands_to_platform_executor():
    tg = FakeCommandExecutorPort()
    delivery = DeliveryService(tg_executor=tg)

    await delivery.deliver(
        Platform.TELEGRAM,
        [SendReply(text="15:00 Berlin", chat_id="chat1", thread_id="thread-1")],
    )

    assert tg.executed_commands == [
        SendReply(text="15:00 Berlin", chat_id="chat1", thread_id="thread-1")
    ]


@pytest.mark.asyncio
async def test_delivery_ignores_empty_command_list():
    tg = FakeCommandExecutorPort()
    delivery = DeliveryService(tg_executor=tg)

    await delivery.deliver(Platform.TELEGRAM, [])

    assert tg.executed_commands == []


@pytest.mark.asyncio
async def test_delivery_noops_when_platform_route_is_missing():
    delivery = DeliveryService()

    await delivery.deliver(
        Platform.TELEGRAM,
        [SendReply(text="15:00 Berlin", chat_id="chat1", thread_id="thread-1")],
    )
