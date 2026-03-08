"""
retry_utils.py — Retry Logic with Exponential Backoff
Provides decorators and utilities for automatic retry with exponential backoff

Features:
- Configurable retry attempts and delays
- Exponential backoff with jitter
- Support for sync and async functions
- Conditional retry based on exception type
- Retry callbacks for logging/monitoring

Usage:
    from retry_utils import retry, async_retry
    
    @retry(max_attempts=3, backoff_base=2)
    def unreliable_function():
        # Your code here
        pass
    
    @async_retry(max_attempts=5, backoff_base=1.5)
    async def unreliable_async_function():
        # Your async code here
        pass
"""

import asyncio
import functools
import logging
import random
import time
from typing import Callable, Optional, Tuple, Type, Union


# Setup logging
logger = logging.getLogger(__name__)


# ── Retry Configuration ───────────────────────────────────────────────────────

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        on_retry: Optional[Callable] = None,
    ):
        """
        Args:
            max_attempts: Maximum number of retry attempts
            backoff_base: Base for exponential backoff (delay = base ^ attempt)
            backoff_max: Maximum delay between retries in seconds
            jitter: Add random jitter to prevent thundering herd
            exceptions: Tuple of exceptions to catch and retry
            on_retry: Callback function called on each retry (receives attempt, exception, delay)
        """
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.jitter = jitter
        self.exceptions = exceptions
        self.on_retry = on_retry


def calculate_backoff(attempt: int, base: float, max_delay: float, jitter: bool = True) -> float:
    """
    Calculate delay for exponential backoff
    
    Args:
        attempt: Current attempt number (starting from 0)
        base: Base for exponential calculation
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter
    
    Returns:
        Delay in seconds
    """
    # Calculate exponential backoff
    delay = min(base ** attempt, max_delay)
    
    # Add jitter to prevent thundering herd
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


# ── Synchronous Retry ─────────────────────────────────────────────────────────

def retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for automatic retry with exponential backoff (synchronous functions)
    
    Example:
        @retry(max_attempts=5, backoff_base=1.5)
        def fetch_data():
            response = requests.get("http://api.example.com/data")
            return response.json()
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    # Calculate delay
                    delay = calculate_backoff(attempt, backoff_base, backoff_max, jitter)
                    
                    # Log retry
                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__}: "
                        f"{type(e).__name__}: {str(e)}. Retrying in {delay:.2f}s..."
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(attempt + 1, e, delay)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All {max_attempts} attempts failed for {func.__name__}: "
                f"{type(last_exception).__name__}: {str(last_exception)}"
            )
            raise last_exception
        
        return wrapper
    
    return decorator


# ── Asynchronous Retry ────────────────────────────────────────────────────────

def async_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for automatic retry with exponential backoff (async functions)
    
    Example:
        @async_retry(max_attempts=5, backoff_base=1.5)
        async def fetch_data():
            async with aiohttp.ClientSession() as session:
                async with session.get("http://api.example.com/data") as response:
                    return await response.json()
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    # Calculate delay
                    delay = calculate_backoff(attempt, backoff_base, backoff_max, jitter)
                    
                    # Log retry
                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__}: "
                        f"{type(e).__name__}: {str(e)}. Retrying in {delay:.2f}s..."
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            if asyncio.iscoroutinefunction(on_retry):
                                await on_retry(attempt + 1, e, delay)
                            else:
                                on_retry(attempt + 1, e, delay)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All {max_attempts} attempts failed for {func.__name__}: "
                f"{type(last_exception).__name__}: {str(last_exception)}"
            )
            raise last_exception
        
        return wrapper
    
    return decorator


# ── Retry Context Manager ─────────────────────────────────────────────────────

class RetryContext:
    """Context manager for retry logic"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.attempt = 0
        self.last_exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True
        
        # Check if exception should be retried
        if not isinstance(exc_val, self.config.exceptions):
            return False
        
        self.last_exception = exc_val
        self.attempt += 1
        
        # Check if we should retry
        if self.attempt < self.config.max_attempts:
            delay = calculate_backoff(
                self.attempt - 1,
                self.config.backoff_base,
                self.config.backoff_max,
                self.config.jitter
            )
            
            logger.warning(
                f"Retry {self.attempt}/{self.config.max_attempts}: "
                f"{exc_type.__name__}: {str(exc_val)}. Retrying in {delay:.2f}s..."
            )
            
            if self.config.on_retry:
                try:
                    self.config.on_retry(self.attempt, exc_val, delay)
                except Exception as e:
                    logger.error(f"Error in retry callback: {e}")
            
            time.sleep(delay)
            return True  # Suppress exception, will retry
        
        # All retries exhausted
        logger.error(
            f"All {self.config.max_attempts} attempts failed: "
            f"{exc_type.__name__}: {str(exc_val)}"
        )
        return False  # Re-raise exception


# ── Utility Functions ─────────────────────────────────────────────────────────

def retry_with_timeout(
    func: Callable,
    max_attempts: int = 3,
    timeout: float = 10.0,
    backoff_base: float = 2.0,
    **kwargs
):
    """
    Retry a function with timeout on each attempt
    
    Args:
        func: Function to retry
        max_attempts: Maximum retry attempts
        timeout: Timeout for each attempt in seconds
        backoff_base: Base for exponential backoff
        **kwargs: Additional arguments to pass to func
    
    Returns:
        Result of successful function call
    
    Raises:
        TimeoutError: If all attempts timeout
        Exception: If function raises non-timeout exception
    """
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Function call timed out")
    
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            # Set timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))
            
            try:
                result = func(**kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
            finally:
                signal.alarm(0)  # Ensure alarm is cancelled
                
        except TimeoutError as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                delay = calculate_backoff(attempt, backoff_base, 60.0)
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{max_attempts}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {max_attempts} attempts timed out")
                raise
        
        except Exception as e:
            # Non-timeout exception, don't retry
            logger.error(f"Non-timeout exception: {type(e).__name__}: {str(e)}")
            raise
    
    raise last_exception


async def async_retry_with_timeout(
    func: Callable,
    max_attempts: int = 3,
    timeout: float = 10.0,
    backoff_base: float = 2.0,
    **kwargs
):
    """
    Async version of retry_with_timeout
    
    Args:
        func: Async function to retry
        max_attempts: Maximum retry attempts
        timeout: Timeout for each attempt in seconds
        backoff_base: Base for exponential backoff
        **kwargs: Additional arguments to pass to func
    
    Returns:
        Result of successful function call
    
    Raises:
        TimeoutError: If all attempts timeout
        Exception: If function raises non-timeout exception
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            result = await asyncio.wait_for(func(**kwargs), timeout=timeout)
            return result
            
        except asyncio.TimeoutError as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                delay = calculate_backoff(attempt, backoff_base, 60.0)
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{max_attempts}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_attempts} attempts timed out")
                raise TimeoutError(f"All {max_attempts} attempts timed out")
        
        except Exception as e:
            # Non-timeout exception, don't retry
            logger.error(f"Non-timeout exception: {type(e).__name__}: {str(e)}")
            raise
    
    raise last_exception


# ── Example Usage ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example 1: Simple retry decorator
    @retry(max_attempts=3, backoff_base=2)
    def unreliable_function():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Random failure")
        return "Success!"
    
    # Example 2: Async retry decorator
    @async_retry(max_attempts=5, backoff_base=1.5)
    async def unreliable_async_function():
        import random
        if random.random() < 0.7:
            raise TimeoutError("Random timeout")
        return "Async success!"
    
    # Example 3: Retry with callback
    def on_retry_callback(attempt, exception, delay):
        print(f"Callback: Attempt {attempt} failed with {exception}, waiting {delay:.2f}s")
    
    @retry(max_attempts=3, on_retry=on_retry_callback)
    def function_with_callback():
        raise ValueError("Test error")
    
    # Run examples
    print("Example 1: Simple retry")
    try:
        result = unreliable_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")
    
    print("\nExample 2: Async retry")
    try:
        result = asyncio.run(unreliable_async_function())
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")
    
    print("\nExample 3: Retry with callback")
    try:
        function_with_callback()
    except Exception as e:
        print(f"Failed as expected: {e}")
