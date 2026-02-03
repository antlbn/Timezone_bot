from datetime import datetime, timezone

from aiogram import Router
from aiogram.types import Message, ForceReply
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src import geo, formatter, capture
from src.transform import parse_time_string
from src.logger import get_logger
from src.commands.states import SetTimezone

router = Router()
logger = get_logger()

@router.message(Command("tb_mytz"))
async def cmd_mytz(message: Message):
    """Show user's current timezone."""
    existing_user = await storage.get_user(message.from_user.id, platform="telegram")
    
    if not existing_user:
        await message.reply("Not set. Use /tb_settz")
        return
    
    await message.reply(f"{existing_user['city']} {existing_user['flag']} ({existing_user['timezone']})")


@router.message(Command("tb_settz"))
async def cmd_settz(message: Message, state: FSMContext):
    """Start timezone setting flow."""
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(SetTimezone.waiting_for_city)
    await message.reply("What city are you in?", reply_markup=ForceReply(selective=True))


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
        # Trigger fallback: ask for time or city retry
        await state.set_state(SetTimezone.waiting_for_time)
        await message.reply(
            f"City not found: {city_name}.\n"
            "Enter your current time (e.g. 14:30) or try another city:",
            reply_markup=ForceReply(selective=True)
        )
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
async def process_fallback_input(message: Message, state: FSMContext):
    """Process user's input for fallback - can be time OR city retry."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        return
    
    user_input = (message.text or "").strip()
    user_name = message.from_user.first_name or "User"
    username = message.from_user.username or ""
    pending_time = data.get("pending_time")
    
    # First, try to geocode as city (user might retry with correct spelling)
    location = geo.get_timezone_by_city(user_input)
    
    if location:
        # City found! Save and proceed
        # Save to DB
        await storage.set_user(
            user_id=message.from_user.id,
            platform="telegram",
            city=location["city"],
            timezone=location["timezone"],
            flag=location["flag"],
            username=message.from_user.username or ""
        )
        
        # Update chat member if in group
        if message.chat.type in ["group", "supergroup"]:
            await storage.add_chat_member(message.chat.id, message.from_user.id, platform="telegram")
            
        await state.clear()
        
        await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
        logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']} (retry)")
        
        # Process pending time if exists
        if pending_time:
            members = await storage.get_chat_members(message.chat.id, platform="telegram")
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
        return
    
    # City not found - try to extract time
    times = capture.extract_times(user_input)
    
    if times:
        try:
            # Parse user's time
            user_time = parse_time_string(times[0])
            
            # Get current UTC time
            now_utc = datetime.now(timezone.utc)
            
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
            
            await storage.set_user(
                message.from_user.id,
                platform="telegram",
                city=location["city"],
                timezone=location["timezone"],
                flag=location["flag"],
                username=username
            )
            
            if message.chat.id != message.from_user.id:
                await storage.add_chat_member(message.chat.id, message.from_user.id, platform="telegram")
            
            await state.clear()
            
            await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
            logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']} (fallback)")
            
            # Process pending time if exists
            if pending_time:
                members = await storage.get_chat_members(message.chat.id, platform="telegram")
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
            return
                
        except Exception as e:
            logger.error(f"Fallback time parsing error: {e}")
    
    # Neither city nor time - ask again
    await message.reply(
        f"Could not find '{user_input}'.\n"
        "Enter your current time (e.g. 14:30) or try another city:",
        reply_markup=ForceReply(selective=True)
    )
    # Stay in waiting_for_time state for retry
