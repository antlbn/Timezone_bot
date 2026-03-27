import asyncio
import os

from src.logger import get_logger

# Locks to ensure only one LLM request fires per chat at a given time.
_chat_locks: dict[tuple[str, str], asyncio.Lock] = {}
_graph_runtime_lock = asyncio.Lock()
_compiled_graph = None
_checkpointer_cm = None

logger = get_logger()


def get_chat_lock(platform: str, chat_id: str) -> asyncio.Lock:
    """Retrieve the unique asyncio lock for the specified chat."""
    key = (platform, str(chat_id))
    if key not in _chat_locks:
        _chat_locks[key] = asyncio.Lock()
    return _chat_locks[key]


async def get_graph_app():
    """Return a process-wide compiled LangGraph app backed by a shared sqlite saver."""
    global _compiled_graph, _checkpointer_cm

    if _compiled_graph is not None:
        return _compiled_graph

    async with _graph_runtime_lock:
        if _compiled_graph is not None:
            return _compiled_graph

        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from src.event_detection.graph import build_agent_graph

        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "graph_checkpoints.db")

        checkpointer_cm = AsyncSqliteSaver.from_conn_string(db_path)
        checkpointer = await checkpointer_cm.__aenter__()
        try:
            await checkpointer.setup()
            _compiled_graph = build_agent_graph().compile(checkpointer=checkpointer)
            _checkpointer_cm = checkpointer_cm
        except Exception:
            await checkpointer_cm.__aexit__(None, None, None)
            raise

        logger.info(f"Initialized shared event detection graph runtime at {db_path}")
        return _compiled_graph


async def reset_graph_runtime() -> None:
    """Close and clear the shared graph runtime. Intended for tests/shutdown."""
    global _compiled_graph, _checkpointer_cm

    async with _graph_runtime_lock:
        if _checkpointer_cm is not None:
            await _checkpointer_cm.__aexit__(None, None, None)
        _compiled_graph = None
        _checkpointer_cm = None
