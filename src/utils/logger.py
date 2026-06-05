"""
logger.py — Structured JSON Logging Configuration
==================================================
Configures structlog to output unified structured JSON lines to standard output,
intercepting standard Python logging calls to ensure compatibility with Loki/Grafana stacks.
"""

import logging
import sys
from typing import Any, Dict
import structlog


def add_pipeline_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Adds global context parameters to the structured log events."""
    event_dict["service"] = "cortex-pipeline"
    return event_dict


def configure_logger(log_level: int = logging.INFO) -> None:
    """Configures the global structlog system and standard logging wrappers."""
    # 1. Setup structlog processors chain
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_pipeline_context,
        structlog.processors.JSONRenderer()
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2. Redirect standard python logging to structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
        ],
        processor=structlog.processors.JSONRenderer(),
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Clear existing handlers to prevent duplicate printing
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress verbose standard third party log lines
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    structlog.get_logger(__name__).info("Structured JSON logging initialized successfully.")
