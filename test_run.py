import asyncio
from src.adapters.outbound.sqlite_storage import SQLiteStorage
from src.adapters.outbound.openai_detector import OpenAIDetector
from src.core.pipeline.pipeline import Pipeline
from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage
from src.core.domain.value_objects import InputData, MessageContext
from src.core.domain.enums import Platform
from datetime import datetime, timezone
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

async def run():
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    await storage._get_conn() 
    detector = OpenAIDetector()
    pipeline = Pipeline([GuardStage(), AgingStage(120), DetectionStage(detector), ResolveStage(storage), FormatStage(storage)])
    ctx = MessageContext(input=InputData(text="hello", user_id=123, platform=Platform.DISCORD, author_name="test", timestamp_utc=datetime.now(timezone.utc), chat_id="456"))
    try:
        ctx = await pipeline.run(ctx)
        print("SUCCESS:", ctx)
    except Exception as e:
        print("FAILED:", repr(e))
        import traceback
        traceback.print_exc()
        
asyncio.run(run())
