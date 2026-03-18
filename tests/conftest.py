import asyncio
import pytest
from src.storage import storage

@pytest.fixture(scope="session", autouse=True)
def close_global_storage():
    """
    Ensure the global storage connection is closed after the test session.
    Using a synchronous fixture with asyncio.run to avoid scope mismatches
    in pytest-asyncio.
    """
    yield
    try:
        # Separate run to ensure it's closed in a fresh loop if needed
        asyncio.run(storage.close())
    except Exception:
        pass

@pytest.fixture(autouse=True)
async def cancel_pending_tasks():
    """
    Cancel all pending asyncio tasks at the end of each test.
    This prevents leaked tasks (like those from @auto_cleanup) 
    from keeping the event loop alive.
    """
    yield
    
    # Identify tasks that are still running and weren't there before
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    if not pending:
        return
        
    for task in pending:
        task.cancel()
        
    # Give tasks a moment to realize they are cancelled
    await asyncio.gather(*pending, return_exceptions=True)
