from aiogram import Router
from aiogram.types import Message, ForceReply
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.transform import get_utc_offset
from src.logger import get_logger
from src.commands.states import RemoveMember
from src.utils import auto_cleanup

router = Router()
logger = get_logger()

@router.message(Command("tb_members"))
@auto_cleanup(delete_bot_msg=True)
async def cmd_members(message: Message):
    """List chat members with timezones - numbered, with @usernames."""
    if message.chat.type == "private":
        return await message.reply("Groups only")
    
    members = await storage.get_chat_members(message.chat.id, platform="telegram")
    
    if not members:
        return await message.reply("No members yet. Use /tb_settz")
    
    # Sort by UTC offset
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    lines = ["Chat members:"]
    for i, m in enumerate(members, 1):
        flag = m.get("flag", "")
        username = f"@{m['username']}" if m.get("username") else ""
        lines.append(f"{i}. {m['city']} {flag} {username}")
    
    lines.append("\n/tb_remove")
    return await message.reply("\n".join(lines))


@router.message(Command("tb_remove"))
@auto_cleanup(delete_bot_msg=True)
async def cmd_remove(message: Message, state: FSMContext):
    """Start member removal flow."""
    if message.chat.type == "private":
        return await message.reply("Groups only")
    
    members = await storage.get_chat_members(message.chat.id, platform="telegram")
    
    if not members:
        return await message.reply("No members to remove")
    
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
    
    prompt = await message.reply("\n".join(lines), reply_markup=ForceReply(selective=True))
    await state.update_data(prompt_message_id=prompt.message_id)
    return prompt


@router.message(RemoveMember.waiting_for_number)
@auto_cleanup(delete_bot_msg=True)
async def process_remove(message: Message, state: FSMContext):
    """Process member number for removal."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    # We don't strictly require a reply. If it's not a number, we assume they        return
    
    # Clean up the bot's prompt immediately if it exists
    if data.get("prompt_message_id"):
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["prompt_message_id"])
        except Exception:
            pass

    try:
        num = int(message.text.strip())
    except ValueError:
        # Not a number: clear state and process as a normal message
        await state.clear()
        from src.commands.common import handle_time_mention
        # Cannot return the bot msg here to auto_cleanup since it proceeds down regular pipeline.
        # But that pipeline shouldn't be auto-cleaned up. Let's just run it. 
        await handle_time_mention(message, state)
        return

    member_ids = data.get("member_ids", [])
    
    if num < 1 or num > len(member_ids):
        await state.clear()
        return await message.answer("Invalid number. Cancelled removal.")
    
    user_id = member_ids[num - 1]
    await storage.remove_chat_member(message.chat.id, user_id, platform="telegram")
    
    await state.clear()
    return await message.answer(f"Removed member #{num}")
    logger.info(f"[chat:{message.chat.id}] Removed user {user_id}")
