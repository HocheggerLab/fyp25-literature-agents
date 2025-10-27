"""Logging configuration using loguru's native environment variables.

Set these in your .env file:
    LOGURU_AUTOINIT=False  # Disable default handler
    LOGURU_LEVEL=INFO      # Log level (DEBUG, INFO, WARNING, ERROR)
    LOGURU_FORMAT=<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>
    LOG_FILE=analysis.log  # Optional: save logs to file
"""

import os
import sys
from pathlib import Path

from loguru import logger

_configured = False


def setup_logging():
    """Configure logging. Call once at startup.

    Respects environment variables:
        LOGURU_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR). Default: INFO
        LOGURU_FORMAT: Log format string. Default: simple colored format
        LOG_FILE: Optional file path for detailed logs with rotation
    """
    global _configured
    if _configured:
        return

    # Add console handler (respects LOGURU_LEVEL and LOGURU_FORMAT from env)
    level = os.getenv("LOGURU_LEVEL", "INFO")
    fmt = os.getenv(
        "LOGURU_FORMAT",
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger.add(sys.stderr, format=fmt, level=level, colorize=True)

    # Optional file logging with detailed format
    log_file = os.getenv("LOG_FILE")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
        )

    _configured = True
