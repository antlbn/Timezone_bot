from aiogram import Router
from aiogram.types import Message, ForceReply
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.transform import get_utc_offset
from src.logger import get_logger
from src.commands.states import RemoveMember

router = Router()
logger = get_logger()

@router.message(Command("tb_members"))
async def cmd_members(message: Message):
    """List chat members with timezones - numbered, with @usernames."""
    if message.chat.type == "private":
        await message.reply("Groups only")
        return
    
    members = await storage.get_chat_members(message.chat.id, platform="telegram")
    
    if not members:
        await message.reply("No members yet. Use /tb_settz")
        return
    
    # Sort by UTC offset
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    lines = ["Chat members:"]
    for i, m in enumerate(members, 1):
        flag = m.get("flag", "")
        username = f"@{m['username']}" if m.get("username") else ""
        lines.append(f"{i}. {m['city']} {flag} {username}")
    
    lines.append("\n/tb_remove")
    await message.reply("\n".join(lines))


@router.message(Command("tb_remove"))
async def cmd_remove(message: Message, state: FSMContext):
    """Start member removal flow."""
    if message.chat.type == "private":
        await message.reply("Groups only")
        return
    
    members = await storage.get_chat_members(message.chat.id, platform="telegram")
    
    if not members:
        await message.reply("No members to remove")
        return
    
    # Sort by UTC offset
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    # Store member list for later
    member_ids = [m["user_id"] for m in members]
    await state.update_data(user_id=message.from_user.id, member_ids=member_ids)
    await state.set_state(RemoveMember.waiting_for_number)
    
    lines = ["Enter number to remove:"]
    for i, m in enumerate(members, 1):
        flag = m.get("flag", "")
        username = f"@{m['username']}" if m.get("username") else ""
        lines.append(f"{i}. {m['city']} {flag} {username}")
    
    await message.reply("\n".join(lines), reply_markup=ForceReply(selective=True))


@router.message(RemoveMember.waiting_for_number)
async def process_remove(message: Message, state: FSMContext):
    """Process member number for removal."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        return
    
    try:
        num = int(message.text.strip())
    except ValueError:
        await message.answer("Enter a number")
        await state.clear()
        return
    
    member_ids = data.get("member_ids", [])
    
    if num < 1 or num > len(member_ids):
        await message.answer("Invalid number")
        await state.clear()
        return
    
    user_id = member_ids[num - 1]
    await storage.remove_chat_member(message.chat.id, user_id, platform="telegram")
    
    await state.clear()
    await message.answer(f"Removed member #{num}")
    logger.info(f"[chat:{message.chat.id}] Removed user {user_id}")
