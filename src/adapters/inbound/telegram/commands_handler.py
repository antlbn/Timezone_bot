from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.domain.enums import Platform
from adapters.inbound.telegram.onboarding_handler import on_start_onboard
from adapters.inbound.telegram import ui
from adapters.inbound.telegram.common import schedule_deletion, generate_onboarding_link
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer
    from adapters.inbound.telegram.config import TelegramConfig

router = Router(name="commands")


@router.message(Command("tb_settz", "tz_settz"), StateFilter("*"))
async def cmd_start_or_settz(message: Message, state: FSMContext, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        await on_start_onboard(message, state, container)
        return

    bot_user = await message.bot.me()
    url = generate_onboarding_link(bot_user.username, message.from_user.id, str(message.chat.id))
    
    reply = await message.answer(
        ui.get_onboarding_prompt_text(message.from_user.first_name),
        reply_markup=ui.get_onboarding_prompt_keyboard(url)
    )
    
    await schedule_deletion(message, reply, delay=tg_config.delete_delay)


@router.message(Command("tb_decline", "decline"), StateFilter("*"))
async def cmd_decline(message: Message, state: FSMContext, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    await state.clear()
    await container.onboarding_completion.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
    )
    reply = await message.answer(ui.get_decline_confirmation_text())
    
    # In group, delete both. In private, delete only bot reply (keeping user command for history usually, but per previous logic we delete bot reply)
    if message.chat.type != "private":
        await schedule_deletion(message, reply, delay=tg_config.delete_delay)
    else:
        await schedule_deletion(reply, delay=tg_config.delete_delay)


@router.message(Command("tb_me", "tz_me", "me"), StateFilter("*"))
async def cmd_me(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    user = await container.profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    if not user or not user.timezone:
        await message.answer(ui.get_tz_not_set_text())
        return

    reply = await message.answer(ui.format_user_timezone(user))
    if message.chat.type != "private":
        await schedule_deletion(message, reply, delay=tg_config.delete_delay)
    else:
        await schedule_deletion(reply, delay=tg_config.delete_delay)


@router.message(Command("tb_members", "tz_members", "members"), StateFilter("*"))
async def cmd_members(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        await message.answer(ui.get_group_only_command_text())
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)

    if not members:
        await message.answer(ui.get_no_members_text(is_group=True))
        return

    reply = await message.answer(ui.format_chat_members(members))
    await schedule_deletion(message, reply, delay=tg_config.delete_delay)


@router.message(Command("tb_deletemember"), StateFilter("*"))
async def cmd_delete_member(message: Message, container: "AppContainer", tg_config: "TelegramConfig") -> None:
    if message.chat.type == "private":
        await message.answer(ui.get_group_only_command_text())
        return

    members = await container.profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)
    if not members:
        await message.answer(ui.get_no_members_text(is_group=False))
        return

    args = message.text.split()
    if len(args) < 2:
        text = ui.get_delete_member_usage_text(ui.format_chat_members(members))
        reply = await message.answer(text)
        await schedule_deletion(message, reply, delay=tg_config.delete_delay)
        return

    try:
        idx = int(args[1]) - 1
        if idx < 0 or idx >= len(members):
            raise ValueError()
        
        target = members[idx]
        await container.profile_service.remove_chat_member(
            chat_id=str(message.chat.id),
            user_id=target.user_id,
            platform=Platform.TELEGRAM
        )
        reply = await message.answer(ui.get_member_removed_text(target.username or target.city or str(target.user_id)))
    except ValueError:
        reply = await message.answer(ui.get_invalid_number_text())

    await schedule_deletion(message, reply, delay=tg_config.delete_delay)


@router.message(Command("tb_help", "tz_help", "help"), StateFilter("*"))
async def cmd_help(message: Message, tg_config: "TelegramConfig") -> None:
    reply = await message.answer(ui.get_help_text(message.chat.type))
    if message.chat.type != "private":
        await schedule_deletion(message, reply, delay=tg_config.delete_delay)
    else:
        await schedule_deletion(reply, delay=tg_config.delete_delay)
