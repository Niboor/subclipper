import logging
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

@contextmanager
def log_time(operation: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation} completed in {duration:.2f} seconds")