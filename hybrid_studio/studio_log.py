"""Shared logging for the hybrid studio.

Every module logs through :func:`get_logger` so execution logs are readable
and consistent across the whole pipeline.
"""

import logging
import sys

_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(name="hybrid_studio"):
    """Return a configured logger (idempotent)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def step(logger, message):
    """Log a clearly visible pipeline step marker."""
    logger.info("=" * 60)
    logger.info("STEP: %s", message)
    logger.info("=" * 60)
