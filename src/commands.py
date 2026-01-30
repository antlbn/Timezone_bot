"""
Commands module.
Telegram bot command handlers (/tb_*).
"""
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src import storage, geo, formatter, capture
from src.transform import get_utc_offset, parse_time_string
from src.logger import get_logger

router = Router()
logger = get_logger()


class SetTimezone(StatesGroup):
    """FSM states for /tb_settz flow."""
    waiting_for_city = State()
    waiting_for_time = State()  # Fallback when city not found


class RemoveMember(StatesGroup):
    """FSM states for /tb_remove flow."""
    waiting_for_number = State()


@router.message(Command("tb_help"))
async def cmd_help(message: Message):
    """Show help menu."""
    help_text = (
        "Timezone Bot\n"
        "/tb_help - this help\n"
        "/tb_mytz - your timezone\n"
        "/tb_settz - set city\n"
        "/tb_members - chat members\n"
        "/tb_remove - remove member\n\n"
        "Mention time (14:00) and I'll convert it!"
    )
    await message.reply(help_text)


@router.message(Command("tb_mytz"))
async def cmd_mytz(message: Message):
    """Show user's current timezone."""
    user = await storage.get_user(message.from_user.id)
    
    if not user:
        await message.reply("Not set. Use /tb_settz")
        return
    
    flag = user.get("flag", "")
    await message.reply(f"{user['city']} {flag} ({user['timezone']})")


@router.message(Command("tb_settz"))
async def cmd_settz(message: Message, state: FSMContext):
    """Start timezone setting flow."""
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(SetTimezone.waiting_for_city)
    await message.reply("Reply with your city name:")


@router.message(SetTimezone.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Process city name input - only from the user who initiated, must be reply."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        return
    
    city_name = message.text.strip()
    location = geo.get_timezone_by_city(city_name)
    
    if not location:
        # Trigger fallback: ask for current time
        await state.set_state(SetTimezone.waiting_for_time)
        await message.answer(f"City not found: {city_name}. Reply with your current time (e.g. 14:30):")
        return
    
    username = message.from_user.username or ""
    await storage.set_user(
        message.from_user.id,
        location["city"],
        location["timezone"],
        location["flag"],
        username
    )
    
    if message.chat.id != message.from_user.id:
        await storage.add_chat_member(message.chat.id, message.from_user.id)
    
    pending_time = data.get("pending_time")
    user_name = message.from_user.first_name or "User"
    
    await state.clear()
    
    await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
    logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']}")
    
    if pending_time:
        members = await storage.get_chat_members(message.chat.id)
        if members:
            reply = formatter.format_conversion_reply(
                pending_time,
                location["city"],
                location["timezone"],
                location["flag"],
                members,
                user_name
            )
            await message.answer(reply)


@router.message(SetTimezone.waiting_for_time)
async def process_fallback_time(message: Message, state: FSMContext):
    """Process user's current time for fallback timezone detection."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        return
    
    # Try to extract time from message
    times = capture.extract_times(message.text or "")
    if not times:
        await message.answer("Please enter a valid time (e.g. 14:30)")
        await state.clear()
        return
    
    try:
        # Parse user's time
        user_time = parse_time_string(times[0])
        
        # Get current UTC time
        now_utc = datetime.now(timezone.utc)
        
        # Create user's datetime (assume today)
        user_dt = datetime.combine(now_utc.date(), user_time)
        
        # Calculate offset in hours
        utc_hours = now_utc.hour + now_utc.minute / 60
        user_hours = user_time.hour + user_time.minute / 60
        offset = user_hours - utc_hours
        
        # Handle day boundary
        if offset > 12:
            offset -= 24
        elif offset < -12:
            offset += 24
        
        # Get timezone by offset
        location = geo.get_timezone_by_offset(offset)
        
        username = message.from_user.username or ""
        await storage.set_user(
            message.from_user.id,
            location["city"],
            location["timezone"],
            location["flag"],
            username
        )
        
        if message.chat.id != message.from_user.id:
            await storage.add_chat_member(message.chat.id, message.from_user.id)
        
        pending_time = data.get("pending_time")
        user_name = message.from_user.first_name or "User"
        
        await state.clear()
        
        await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
        logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']} (fallback)")
        
        # Process pending time if exists
        if pending_time:
            members = await storage.get_chat_members(message.chat.id)
            if members:
                reply = formatter.format_conversion_reply(
                    pending_time,
                    location["city"],
                    location["timezone"],
                    location["flag"],
                    members,
                    user_name
                )
                await message.answer(reply)
                
    except Exception as e:
        logger.error(f"Fallback time parsing error: {e}")
        await message.answer("Could not determine timezone. Please try /tb_settz again.")
        await state.clear()


@router.message(Command("tb_members"))
async def cmd_members(message: Message):
    """List chat members with timezones - numbered, with @usernames."""
    if message.chat.type == "private":
        await message.reply("Groups only")
        return
    
    members = await storage.get_chat_members(message.chat.id)
    
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
    
    members = await storage.get_chat_members(message.chat.id)
    
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
    
    await message.reply("\n".join(lines))


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
    await storage.remove_chat_member(message.chat.id, user_id)
    
    await state.clear()
    await message.answer(f"Removed member #{num}")
    logger.info(f"[chat:{message.chat.id}] Removed user {user_id}")


@router.message(F.text)
async def handle_time_mention(message: Message, state: FSMContext):
    """Handle regular messages - check for time mentions."""
    if not message.text:
        return
    
    times = capture.extract_times(message.text)
    if not times:
        return
    
    sender = await storage.get_user(message.from_user.id)
    user_name = message.from_user.first_name or "User"
    
    if not sender:
        await state.update_data(user_id=message.from_user.id, pending_time=times[0])
        await state.set_state(SetTimezone.waiting_for_city)
        await message.reply(f"{user_name}, reply with your city name:")
        return
    
    if message.chat.id != message.from_user.id:
        await storage.add_chat_member(message.chat.id, message.from_user.id)
    
    members = await storage.get_chat_members(message.chat.id)
    
    if not members:
        return
    
    sender_flag = sender.get("flag", "")
    
    for time_str in times:
        reply = formatter.format_conversion_reply(
            time_str,
            sender["city"],
            sender["timezone"],
            sender_flag,
            members,
            user_name
        )
        await message.answer(reply)
    
    logger.info(f"[chat:{message.chat.id}] Times: {times}")
