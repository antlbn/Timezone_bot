from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from adapters.inbound.telegram.onboarding_handler import OnboardingFSM
from adapters.inbound.telegram.ui import get_help_text
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer

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
async def cmd_start_or_settz(message: Message, state: FSMContext, container: "AppContainer") -> None:
    if message.chat.type == "private":
        from adapters.inbound.telegram.onboarding_handler import on_start_onboard
        await on_start_onboard(message, state, container)
        return

    bot_user = await message.bot.me()
    deep_link = f"https://t.me/{bot_user.username}?start=onboard_{message.from_user.id}_{message.chat.id}"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📍 Set up my timezone", url=deep_link)
    ]])
    
    await message.answer(
        "To set your timezone, please tap the button below and I'll help you in private chat! 👇",
        reply_markup=kb
    )

@router.message(Command("tb_decline", "decline"), StateFilter("*"))
async def cmd_decline(message: Message, state: FSMContext, container: "AppContainer") -> None:
    await state.clear()
    await container.onboarding_completion.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
    )
    await message.answer("Got it! I won't ask you again. Use /tb_settz if you change your mind.")

@router.message(Command("tb_me", "tz_me", "me"), StateFilter("*"))
async def cmd_me(message: Message, container: "AppContainer") -> None:
    user = await container.profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    if not user or not user.timezone:
        await message.answer("Your timezone is not set yet. Use /tb_settz.")
        return

    await message.answer(_format_user_timezone(user))

@router.message(Command("tb_members", "tz_members", "members"), StateFilter("*"))
async def cmd_members(message: Message, container: "AppContainer") -> None:
    if message.chat.type == "private":
        await message.answer("This command only works in groups.")
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)

    if not members:
        await message.answer("No members registered here yet. Use /tb_settz in private chat.")
        return

    await message.answer(_format_chat_members(members))

@router.message(Command("tb_help", "tz_help", "help"), StateFilter("*"))
async def cmd_help(message: Message) -> None:
    await message.answer(get_help_text(message.chat.type))
