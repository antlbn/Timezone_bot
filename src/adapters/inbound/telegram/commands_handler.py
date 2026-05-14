from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.domain.enums import Platform
from adapters.inbound.telegram.onboarding_handler import start_onboarding_flow
from adapters.inbound.telegram import ui
from adapters.inbound.telegram.common import DeletionScheduler, generate_onboarding_link
from core.services.profile import ProfileService
from core.services.onboarding import OnboardingCompletionUseCase
from adapters.inbound.telegram.config import TelegramConfig
import logging

logger = logging.getLogger(__name__)

async def auto_cleanup(
    scheduler: DeletionScheduler,
    message: Message,
    reply: Message | None,
    config: TelegramConfig,
) -> None:
    if message.chat.type != "private":
        await scheduler.schedule(message, reply, delay=config.delete_delay)
    elif reply:
        await scheduler.schedule(reply, delay=config.delete_delay)

router = Router(name="commands")


@router.message(Command("tb_settz", "tz_settz"), StateFilter("*"))
async def cmd_start_or_settz(
    message: Message, 
    state: FSMContext, 
    onboarding_completion: OnboardingCompletionUseCase,
    profile_service: ProfileService,
    tg_config: TelegramConfig,
    deletion_scheduler: DeletionScheduler,
) -> None:
    if message.chat.type == "private":
        await start_onboarding_flow(message, state, onboarding_completion, profile_service, tg_config, deletion_scheduler)
        return

    bot_user = await message.bot.me()
    url = generate_onboarding_link(bot_user.username, message.from_user.id, str(message.chat.id))
    
    reply = await message.answer(
        ui.get_onboarding_prompt_text(message.from_user.first_name),
        reply_markup=ui.get_onboarding_prompt_keyboard(url)
    )
    await deletion_scheduler.schedule(message, reply, delay=tg_config.delete_delay)

@router.message(Command("tb_decline", "decline"), StateFilter("*"))
async def cmd_decline(
    message: Message, 
    state: FSMContext, 
    onboarding_completion: OnboardingCompletionUseCase,
    tg_config: TelegramConfig,
    deletion_scheduler: DeletionScheduler,
) -> None:
    await state.clear()
    await onboarding_completion.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
    )
    reply = await message.answer(ui.get_decline_confirmation_text())
    
    if message.chat.type != "private":
        await deletion_scheduler.schedule(message, reply, delay=tg_config.delete_delay)
    else:
        await deletion_scheduler.schedule(reply, delay=tg_config.delete_delay)


@router.message(Command("tb_me", "tz_me", "me"), StateFilter("*"))
async def cmd_me(message: Message, profile_service: ProfileService, tg_config: TelegramConfig, deletion_scheduler: DeletionScheduler) -> None:
    user = await profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    if not user or not user.timezone:
        await message.answer(ui.get_tz_not_set_text())
        return

    reply = await message.answer(ui.format_user_timezone(user))
    await auto_cleanup(deletion_scheduler, message, reply, tg_config)


@router.message(Command("tb_members", "tz_members", "members"), StateFilter("*"))
async def cmd_members(message: Message, profile_service: ProfileService, tg_config: TelegramConfig, deletion_scheduler: DeletionScheduler) -> None:
    if message.chat.type == "private":
        await message.answer(ui.get_group_only_command_text())
        return

    members = await profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)

    if not members:
        await message.answer(ui.get_no_members_text(is_group=True))
        return

    reply = await message.answer(ui.format_chat_members(members))
    await auto_cleanup(deletion_scheduler, message, reply, tg_config)


@router.message(Command("tb_deletemember"), StateFilter("*"))
async def cmd_delete_member(message: Message, profile_service: ProfileService, tg_config: TelegramConfig, deletion_scheduler: DeletionScheduler) -> None:
    if message.chat.type == "private":
        await message.answer(ui.get_group_only_command_text())
        return

    members = await profile_service.get_sorted_chat_members(str(message.chat.id), Platform.TELEGRAM)
    if not members:
        await message.answer(ui.get_no_members_text(is_group=False))
        return

    command_parts = message.text.split()
    if len(command_parts) < 2:
        text = ui.get_delete_member_usage_text(ui.format_chat_members(members))
        reply = await message.answer(text)
        await deletion_scheduler.schedule(message, reply, delay=tg_config.delete_delay)
        return

    reply = None
    try:
        member_position = int(command_parts[1]) - 1
        if member_position < 0 or member_position >= len(members):
            raise ValueError()
        
        selected_member = members[member_position]
        await profile_service.remove_chat_member(
            chat_id=str(message.chat.id),
            user_id=selected_member.user_id,
            platform=Platform.TELEGRAM
        )
        reply = await message.answer(ui.get_member_removed_text(selected_member.username or selected_member.city or str(selected_member.user_id)))
    except ValueError:
        reply = await message.answer(ui.get_invalid_number_text())
    
    if reply:
        await auto_cleanup(deletion_scheduler, message, reply, tg_config)


@router.message(Command("tb_help", "tz_help", "help"), StateFilter("*"))
async def cmd_help(message: Message, tg_config: TelegramConfig, deletion_scheduler: DeletionScheduler) -> None:
    reply = await message.answer(ui.get_help_text())
    await auto_cleanup(deletion_scheduler, message, reply, tg_config)
