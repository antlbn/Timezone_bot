from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.domain.enums import Platform
from adapters.inbound.telegram.onboarding_handler import OnboardingFSM
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer

router = Router(name="commands")

@router.message(Command("start", "tb_settz", "tz_settz"))
async def cmd_start_or_settz(message: Message, state: FSMContext) -> None:
    # If in group, send them a deep link to start? 
    # Or just tell them to start the bot directly.
    if message.chat.type != "private":
        bot_user = await message.bot.me()
        await message.answer(f"Please message me privately to set your timezone: https://t.me/{bot_user.username}?start=onboard")
        return

    await state.set_state(OnboardingFSM.waiting_city)
    await message.answer(
        "🌍 <b>Type your city</b> so I can deduce your timezone.\n"
        "Or type /skip to skip."
    )

@router.message(Command("tb_skip", "tz_skip", "skip"))
async def cmd_skip(message: Message, state: FSMContext, container: "AppContainer") -> None:
    await state.clear()
    await container.onboarding_completion.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
    )
    await message.answer("Got it! I won't ask you again. Use /tb_settz if you change your mind.")

@router.message(Command("tb_me", "tz_me", "me"))
async def cmd_me(message: Message, container: "AppContainer") -> None:
    user = await container.profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    if not user or not user.timezone:
        await message.answer("Not set. Use /tb_settz")
        return

    flag = user.flag or ""
    city = user.city or "Unknown"
    await message.answer(f"{city} {flag} ({user.timezone})")

@router.message(Command("tb_members", "tz_members", "members"))
async def cmd_members(message: Message, container: "AppContainer") -> None:
    if message.chat.type == "private":
        await message.answer("This command only works in groups.")
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)

    if not members:
        await message.answer("No members registered here yet. Use /tb_settz")
        return

    lines = ["**Chat members:**"]
    for i, m in enumerate(members, 1):
        flag = m.flag or ""
        city = m.city or "Unknown"
        name = f" (@{m.username})" if m.username else ""
        lines.append(f"{i}. {city} {flag}{name}")

    await message.answer("\n".join(lines))

@router.message(Command("tb_help", "tz_help", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "I detect time mentions and convert them for your chat members automatically! "
        "Use /tb_settz to set your timezone."
    )
