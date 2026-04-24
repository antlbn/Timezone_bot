import json
import logging
import re
from openai import AsyncOpenAI

from ports.detection import DetectionPort, DetectionRequest, DetectionResult
from core.domain.value_objects import TimePoint, LLMConfig

from core.domain.prompts import get_system_prompt

logger = logging.getLogger(__name__)

class OpenAIDetector(DetectionPort):
    def __init__(self, config: LLMConfig, log_prompts: bool = False):
        self._config = config
        self._log_prompts = log_prompts

    def _strip_json_fences(self, raw: str) -> str:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[^\n]*\n", "", text, count=1)
            text = re.sub(r"\n```$", "", text).strip()
        return text

    async def detect(self, request: DetectionRequest) -> DetectionResult:
        attempts = [self._config.primary]
        if self._config.fallback:
            attempts.append(self._config.fallback)

        last_error = None
        for m_cfg in attempts:
            if not m_cfg.api_key:
                logger.warning(f"No API key for model {m_cfg.model}, skipping attempt.")
                continue

            try:
                client = AsyncOpenAI(
                    api_key=m_cfg.api_key, 
                    base_url=m_cfg.base_url, 
                    timeout=5.0,
                    max_retries=0
                )
                
                system_prompt = get_system_prompt()

                user_content = f"CURRENT TIME (UTC): {request.timestamp}\nCURRENT MESSAGE:\n{request.text}"

                if self._log_prompts:
                    logger.info(
                        "LLM detection prompt model=%s system=%r user=%r",
                        m_cfg.model,
                        system_prompt,
                        user_content,
                    )

                response = await client.chat.completions.create(
                    model=m_cfg.model,
                    temperature=m_cfg.temperature,
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
                logger.error(f"Detector error for model {m_cfg.model}: {e}")
                last_error = e
                continue

        if last_error:
            logger.exception(f"All LLM attempts failed. Last error: {last_error}")
        return DetectionResult(time_mentioned=False, points=tuple())
