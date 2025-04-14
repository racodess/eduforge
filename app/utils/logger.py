# logger.py

import logging

logging.basicConfig(
    level=logging.INFO,
    format="\n[%(asctime)s] [%(name)s] %(levelname)s: %(message)s"
)

# Globally configured logger.
logger = logging.getLogger("flashcard_app")
