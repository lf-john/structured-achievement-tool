import functools
import asyncio
import time
import logging

# Configure logging for the retry decorator
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    A configurable retry decorator for synchronous and asynchronous functions.

    Args:
        max_attempts (int): Maximum number of attempts.
        delay (int/float): Initial delay in seconds between retries.
        backoff (int/float): Factor by which to multiply the delay after each retry.
        exceptions (tuple): A tuple of exception types to catch and retry on.
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.info(f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {current_delay:.2f} seconds...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}. Last exception: {e}")
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.info(f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {current_delay:.2f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}. Last exception: {e}")
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

