"""
Logging Setup

Uses loguru for better logging.
"""

import sys
from pathlib import Path

from loguru import logger

_initialized = False


def setup_logger(level: str = "INFO", log_file: str | None = None) -> None:
    """
    Setup logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    global _initialized
    if _initialized:
        return

    # Remove default handler
    logger.remove()

    # Console output with colors
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File output if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
        )

    _initialized = True


def get_logger(name: str = "dreampivot"):
    """Get a logger instance."""
    return logger.bind(name=name)
