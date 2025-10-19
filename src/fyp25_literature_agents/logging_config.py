"""Logging configuration for clean console output with optional file logging."""

import os
import sys
from pathlib import Path

from loguru import logger

# Track if logging has been configured to avoid duplicate handlers
_logging_configured = False


def setup_logging(verbose: bool = False, force: bool = False):
    """Configure logging with clean console output and optional file logging.

    Args:
        verbose: If True, show DEBUG level logs on console. Default: False (INFO only)
        force: If True, reconfigure even if already configured (for Jupyter). Default: False

    Environment Variables:
        LOG_FILE: If set, logs will be saved to this file (e.g., LOG_FILE=analysis.log)
        LOG_LEVEL: Console log level (DEBUG, INFO, WARNING, ERROR). Default: INFO

    Example:
        >>> setup_logging(verbose=True)  # Show all logs on console
        >>> # Or use environment:
        >>> # LOG_FILE=analysis.log LOG_LEVEL=DEBUG python script.py
    """
    global _logging_configured

    # Skip if already configured (unless force=True)
    if _logging_configured and not force:
        return logger

    # Remove all existing handlers
    logger.remove()

    # Get configuration from environment
    log_file = os.getenv("LOG_FILE")
    log_level = os.getenv("LOG_LEVEL", "INFO" if not verbose else "DEBUG")

    # Console logging - clean format
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
        filter=lambda record: _should_show_on_console(record, verbose),
    )

    # File logging - detailed format (if LOG_FILE is set)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

        logger.add(
            log_file,
            format=file_format,
            level="DEBUG",  # Always save DEBUG to file
            rotation="10 MB",  # Rotate after 10MB
            retention="7 days",  # Keep logs for 7 days
            compression="zip",  # Compress old logs
        )

        logger.info(f"Logging to file: {log_file}")

    # Mark as configured
    _logging_configured = True

    return logger


def _should_show_on_console(record, verbose: bool) -> bool:
    """Filter which logs to show on console.

    Args:
        record: Log record
        verbose: Whether verbose mode is enabled

    Returns:
        True if log should be shown on console
    """
    # Always show WARNING and ERROR
    if record["level"].no >= 30:  # WARNING = 30, ERROR = 40
        return True

    # In non-verbose mode, hide DEBUG logs
    if not verbose and record["level"].name == "DEBUG":
        return False

    # Hide noisy messages in non-verbose mode
    # (Most are now DEBUG level, but filter just in case)
    if not verbose:
        message = record["message"]
        if any(
            phrase in message
            for phrase in [
                "Processing article",
                "Analyzing article",  # From analyze_article method
                "✓ Completed",
                "Processing batch",
                "Initialized LiteratureAgent",
                "Searching PubMed",
            ]
        ):
            return False

    return True


def get_console_logger():
    """Get a logger that only outputs to console (for progress messages).

    Returns:
        Logger instance configured for console only
    """
    return logger
