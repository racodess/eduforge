# logger.py

"""
Configure and expose a global logger for the EduForge flashcard_app.

This module sets up the logging format and level once, ensuring
consistent timestamped log messages throughout the application.
"""

import logging

# Initialize the root logger with INFO level and a structured format:
# - Timestamp: when the log entry was created
# - Logger name: identifies the source module
# - Log level: INFO, WARNING, ERROR, etc.
# - Message: the actual log text
logging.basicConfig(
    level=logging.INFO,
    format="\n[%(asctime)s] [%(name)s] %(levelname)s: %(message)s"
)

# Create and name a logger instance for the application:
# Using a specific name allows for fine-grained control if needed.
logger = logging.getLogger("flashcard_app")
