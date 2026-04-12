import asyncio
from src.adapters.outbound.openai_detector import OpenAIDetector
from src.ports.detection import DetectionRequest
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
load_dotenv()

async def run():
    detector = OpenAIDetector()
    req = DetectionRequest(text="let's meet at 5 PM", timestamp=datetime.now(timezone.utc))
    res = await detector.detect(req)
    print("SUCCESS:", res)
        
asyncio.run(run())
