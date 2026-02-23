import asyncio
import logging
import time
from functools import wraps

# Configure logging for retry attempts. This can be customized by the application.
# For testing, we are patching logging.getLogger so no explicit configuration here.

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    A configurable retry decorator.

    Args:
        max_attempts (int): Maximum number of attempts to try the function.
        delay (int): Initial delay in seconds before the first retry.
        backoff (int): Factor by which the delay will multiply after each retry.
        exceptions (tuple): A tuple of exception types to catch and retry on.
    """
    def decorator(func):
        logger = logging.getLogger(func.__module__)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        sleep_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            f"Attempt {attempt} of {max_attempts} failed for {func.__name__}: {e}. Retrying in {sleep_time:.1f}s..."
                        )
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}. Last exception: {e}")
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry decorator failed without an exception being caught in the loop.")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        sleep_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            f"Attempt {attempt} of {max_attempts} failed for {func.__name__}: {e}. Retrying in {sleep_time:.1f}s..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}. Last exception: {e}")
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry decorator failed without an exception being caught in the loop.")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
