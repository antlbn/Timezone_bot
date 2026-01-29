"""
Logging setup.
Simple stdout logging based on config level.
"""
import logging
import sys
from src.config import get_log_level

def setup_logging() -> logging.Logger:
    """Configure and return the main logger."""
    level = get_log_level()
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    
    logger = logging.getLogger("timezone_bot")
    logger.info(f"Logging initialized at {level} level")
    return logger

# Singleton logger
_logger = None

def get_logger() -> logging.Logger:
    """Get or create the main logger."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger
