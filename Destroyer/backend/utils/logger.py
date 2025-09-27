# backend/utils/logger.py
import logging
import sys

# Get the logger instance
logger = logging.getLogger("Destroyer")

# Check if the logger has already been configured to avoid duplicate handlers
if not logger.handlers:
    logger.setLevel(logging.INFO)
    # Create a handler to print logs to the console
    handler = logging.StreamHandler(sys.stdout)
    # Create a formatter to define the log message format
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)