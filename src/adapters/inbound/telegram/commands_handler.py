from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from adapters.inbound.telegram.onboarding_handler import OnboardingFSM
from adapters.inbound.telegram import ui
from adapters.inbound.telegram.common import schedule_deletion, generate_onboarding_link
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer
    from adapters.inbound.telegram.config import TelegramConfig

router = Router(name="commands")


def _format_user_timezone(user: UserProfile) -> str:
    flag = f" {user.flag}" if user.flag else ""
    city = user.city or "Unknown"
    return f"{city}{flag} ({user.timezone})"


def _format_chat_members(members: list[UserProfile]) -> str:
    lines = ["<b>Chat members:</b>"]
    for i, member in enumerate(members, 1):
        flag = f" {member.flag}" if member.flag else ""
        city = member.city or "Unknown"
        username = f" (@{member.username})" if member.username else ""
        suffix = "" if member.timezone else " — timezone not set"
        lines.append(f"{i}. {city}{flag}{username}{suffix}")
    return "\n".join(lines)


@router.message(Command("tb_settz", "tz_settz"), StateFilter("*"))
async def cmd_start_or_settz(message: Message, state: FSMContext, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        from adapters.inbound.telegram.onboarding_handler import on_start_onboard
        await on_start_onboard(message, state, container)
        return

    bot_user = await message.bot.me()
    url = generate_onboarding_link(bot_user.username, message.from_user.id, str(message.chat.id))
    
    reply = await message.answer(
        ui.get_onboarding_prompt_text(message.from_user.first_name),
        reply_markup=ui.get_onboarding_prompt_keyboard(url)
    )
    
    if message.chat.type != "private":
        await schedule_deletion(message, delay=tg_config.delete_delay)
        await schedule_deletion(reply, delay=tg_config.delete_delay)
    else:
        # In private chat, also delete setup prompts
        await schedule_deletion(reply, delay=tg_config.delete_delay)

@router.message(Command("tb_decline", "decline"), StateFilter("*"))
async def cmd_decline(message: Message, state: FSMContext, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    await state.clear()
    await container.onboarding_completion.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
    )
    reply = await message.answer("Got it! I won't ask you again. Use /tb_settz if you change your mind.")
    
    if message.chat.type != "private":
        await schedule_deletion(message, delay=tg_config.delete_delay)
        await schedule_deletion(reply, delay=tg_config.delete_delay)
    else:
        # Also delete the decline confirmation in DM
        await schedule_deletion(reply, delay=tg_config.delete_delay)

@router.message(Command("tb_me", "tz_me", "me"), StateFilter("*"))
async def cmd_me(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    user = await container.profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    if not user or not user.timezone:
        await message.answer("Your timezone is not set yet. Use /tb_settz.")
        return

    reply = await message.answer(_format_user_timezone(user))
    if message.chat.type != "private":
        await schedule_deletion(message, delay=tg_config.delete_delay)
        await schedule_deletion(reply, delay=tg_config.delete_delay)
    else:
        # Also delete /me output in DM
        await schedule_deletion(reply, delay=tg_config.delete_delay)

@router.message(Command("tb_members", "tz_members", "members"), StateFilter("*"))
async def cmd_members(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        await message.answer("This command only works in groups.")
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)

    if not members:
        await message.answer("No members registered here yet. Use /tb_settz in private chat.")
        return

    reply = await message.answer(_format_chat_members(members))
    await schedule_deletion(message, delay=tg_config.delete_delay)
    await schedule_deletion(reply, delay=tg_config.delete_delay)


@router.message(Command("tb_deletemember"), StateFilter("*"))
async def cmd_delete_member(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        await message.answer("This command only works in groups.")
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)
    if not members:
        await message.answer("No members registered here yet.")
        return

    args = message.text.split()
    if len(args) < 2:
        text = _format_chat_members(members)
        text += "\n\nTo remove a member, use: <code>/tb_deletemember [number]</code>"
        reply = await message.answer(text)
        await schedule_deletion(message, delay=tg_config.delete_delay)
        await schedule_deletion(reply, delay=tg_config.delete_delay)
        return

    try:
        idx = int(args[1]) - 1
        if idx < 0 or idx >= len(members):
            raise ValueError()
        
        target = members[idx]
        await container.chats_repo.remove_chat_member(
            chat_id=str(message.chat.id),
            user_id=target.user_id,
            platform=Platform.TELEGRAM
        )
        reply = await message.answer(f"✅ Removed <b>{target.username or target.city or target.user_id}</b> from this chat's list.")
    except ValueError:
        reply = await message.answer("❌ Invalid number. Please use a number from the list.")

    await schedule_deletion(message, delay=tg_config.delete_delay)
    await schedule_deletion(reply, delay=tg_config.delete_delay)


@router.message(Command("tb_help", "tz_help", "help"), StateFilter("*"))
async def cmd_help(message: Message, tg_config: "TelegramConfig") -> None:
    reply = await message.answer(ui.get_help_text(message.chat.type))
    if message.chat.type != "private":
        await schedule_deletion(message, delay=tg_config.delete_delay)
        await schedule_deletion(reply, delay=tg_config.delete_delay)
    else:
        # Also delete help in DM
        await schedule_deletion(reply, delay=tg_config.delete_delay)
