"""Logging configuration for the MCP server."""

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "patient_id"):
            log_data["patient_id"] = record.patient_id

        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """
    Set up logging configuration for the application.

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger("mcp_server")
    logger.setLevel(getattr(logging, settings.log_level))

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(settings.log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))

    if settings.log_format == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file_path,
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
    )
    file_handler.setLevel(getattr(logging, settings.log_level))

    if settings.log_format == "json":
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to module name)

    Returns:
        logging.Logger: Logger instance
    """
    if name is None:
        name = "mcp_server"
    return logging.getLogger(name)


# Initialize logger on module import
logger = setup_logging()
