import json
import logging
import os
import re
from openai import AsyncOpenAI

from src.ports.detection import DetectionPort, DetectionRequest, DetectionResult
from src.core.domain.value_objects import TimePoint

logger = logging.getLogger(__name__)

# To decouple completely from legacy config, we use env vars directly.
class OpenAIDetector(DetectionPort):
    def __init__(self):
        # We will initialize connection logic inline or pass a client 
        pass

    def _strip_json_fences(self, raw: str) -> str:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[^\n]*\n", "", text, count=1)
            text = re.sub(r"\n```$", "", text).strip()
        return text

    async def detect(self, request: DetectionRequest) -> DetectionResult:
        api_key = os.getenv("LLM_FALLBACK_API_KEY")
        base_url = os.getenv("LLM_FALLBACK_BASE_URL")
        model = os.getenv("LLM_FALLBACK_MODEL", "gpt-4o-mini")

        if not api_key:
            logger.error("No LLM_API_KEY found")
            return DetectionResult(time_mentioned=False, points=tuple())

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        # Super simplified system prompt for testing
        system_prompt = """You extract time references from conversational text and return a JSON object.
Return JSON: {"time_mentioned": bool, "points": [{"time": "HH:MM", "tz_city": "CityName", "event_title": "Title", "am_pm_clear": true}]}.
Keep am_pm_clear true unless ambiguous."""

        user_content = f"CURRENT TIME (UTC): {request.timestamp}\nCURRENT MESSAGE:\n{request.text}"

        try:
            response = await client.chat.completions.create(
                model=model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(self._strip_json_fences(raw))
            time_mentioned = parsed.get("time_mentioned", False)
            points_raw = parsed.get("points", [])
            
            points = []
            for p in points_raw:
                time_val = p.get("time")
                if time_val and re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_val):
                    points.append(TimePoint(
                        time=time_val,
                        tz_city=p.get("tz_city"),
                        am_pm_clear=p.get("am_pm_clear", True),
                        event_title=p.get("event_title")
                    ))

            return DetectionResult(time_mentioned=time_mentioned, points=tuple(points))
        except Exception as e:
            logger.error(f"Detector error: {e}")
            return DetectionResult(time_mentioned=False, points=tuple())
