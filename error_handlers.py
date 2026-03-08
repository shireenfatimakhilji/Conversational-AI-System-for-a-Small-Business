"""
error_handlers.py — Centralized Error Handling Utilities
Provides comprehensive error handling, logging, and recovery strategies

Features:
- Structured error logging with context
- Error classification and categorization
- Integration with retry and circuit breaker
- Error reporting and notifications
- Graceful degradation strategies
- Custom error responses for API

Usage:
    from error_handlers import (
        handle_error,
        APIErrorHandler,
        WebSocketErrorHandler,
        ErrorCategory
    )
"""

import functools
import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union

from retry_utils import retry, async_retry
from circuit_breaker import CircuitBreaker, CircuitBreakerError


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ── Error Categories ──────────────────────────────────────────────────────────

class ErrorCategory(Enum):
    """Classification of errors for better handling"""
    
    # Network errors (retry with backoff)
    NETWORK = "network"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    
    # Client errors (don't retry)
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    BAD_REQUEST = "bad_request"
    
    # Server errors (retry with circuit breaker)
    SERVER_ERROR = "server_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DATABASE_ERROR = "database_error"
    
    # Business logic errors
    BUSINESS_LOGIC = "business_logic"
    
    # Unknown errors
    UNKNOWN = "unknown"


# ── Error Classification ──────────────────────────────────────────────────────

def classify_error(exception: Exception) -> ErrorCategory:
    """
    Classify an exception into an error category
    
    Args:
        exception: The exception to classify
    
    Returns:
        ErrorCategory enum value
    """
    exception_name = type(exception).__name__
    exception_str = str(exception).lower()
    
    # Network errors
    if isinstance(exception, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return ErrorCategory.CONNECTION
    
    if isinstance(exception, TimeoutError) or "timeout" in exception_str:
        return ErrorCategory.TIMEOUT
    
    if "network" in exception_str or "connection" in exception_str:
        return ErrorCategory.NETWORK
    
    # HTTP errors (if using requests or similar)
    if hasattr(exception, 'response'):
        status_code = getattr(exception.response, 'status_code', None)
        if status_code:
            if status_code == 400:
                return ErrorCategory.BAD_REQUEST
            elif status_code == 401:
                return ErrorCategory.AUTHENTICATION
            elif status_code == 403:
                return ErrorCategory.AUTHORIZATION
            elif status_code == 404:
                return ErrorCategory.NOT_FOUND
            elif 500 <= status_code < 600:
                return ErrorCategory.SERVER_ERROR
    
    # Validation errors
    if "validation" in exception_str or "invalid" in exception_str:
        return ErrorCategory.VALIDATION
    
    # Database errors
    if "database" in exception_str or "sql" in exception_str:
        return ErrorCategory.DATABASE_ERROR
    
    return ErrorCategory.UNKNOWN


def should_retry(error_category: ErrorCategory) -> bool:
    """Determine if an error should be retried"""
    retryable_categories = {
        ErrorCategory.NETWORK,
        ErrorCategory.TIMEOUT,
        ErrorCategory.CONNECTION,
        ErrorCategory.SERVER_ERROR,
        ErrorCategory.SERVICE_UNAVAILABLE,
    }
    return error_category in retryable_categories


# ── Error Context ─────────────────────────────────────────────────────────────

class ErrorContext:
    """Stores context information about an error"""
    
    def __init__(
        self,
        exception: Exception,
        function_name: str,
        args: tuple = (),
        kwargs: dict = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[dict] = None,
    ):
        self.exception = exception
        self.exception_type = type(exception).__name__
        self.exception_message = str(exception)
        self.function_name = function_name
        self.args = args
        self.kwargs = kwargs or {}
        self.user_id = user_id
        self.session_id = session_id
        self.additional_context = additional_context or {}
        self.timestamp = datetime.now()
        self.category = classify_error(exception)
        self.traceback = traceback.format_exc()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/reporting"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "category": self.category.value,
            "function": self.function_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "traceback": self.traceback,
            **self.additional_context,
        }
    
    def log(self, level: int = logging.ERROR):
        """Log the error with full context"""
        logger.log(
            level,
            f"Error in {self.function_name}: {self.exception_type} - {self.exception_message}",
            extra={"error_context": self.to_dict()}
        )


# ── Error Handler Decorator ───────────────────────────────────────────────────

def handle_error(
    retry_enabled: bool = True,
    retry_attempts: int = 3,
    circuit_breaker: Optional[CircuitBreaker] = None,
    fallback: Optional[Callable] = None,
    log_errors: bool = True,
    reraise: bool = True,
):
    """
    Comprehensive error handling decorator
    
    Args:
        retry_enabled: Whether to retry on failure
        retry_attempts: Maximum retry attempts
        circuit_breaker: Optional circuit breaker to use
        fallback: Fallback function to call on failure
        log_errors: Whether to log errors
        reraise: Whether to reraise exception after handling
    
    Example:
        @handle_error(retry_attempts=3, fallback=lambda: "default_value")
        def risky_function():
            # Your code here
            pass
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Apply circuit breaker if provided
                if circuit_breaker:
                    return circuit_breaker.call(func, *args, **kwargs)
                
                # Apply retry if enabled
                if retry_enabled:
                    @retry(max_attempts=retry_attempts)
                    def retryable_func():
                        return func(*args, **kwargs)
                    return retryable_func()
                
                # Direct call
                return func(*args, **kwargs)
                
            except Exception as e:
                # Create error context
                context = ErrorContext(
                    exception=e,
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs,
                )
                
                # Log error
                if log_errors:
                    context.log()
                
                # Call fallback if provided
                if fallback:
                    try:
                        logger.info(f"Calling fallback for {func.__name__}")
                        return fallback()
                    except Exception as fallback_error:
                        logger.error(f"Fallback failed: {fallback_error}")
                
                # Reraise or return None
                if reraise:
                    raise
                return None
        
        return wrapper
    
    return decorator


# ── API Error Handler ─────────────────────────────────────────────────────────

class APIErrorHandler:
    """Handles errors for FastAPI endpoints"""
    
    @staticmethod
    def create_error_response(
        exception: Exception,
        status_code: int = 500,
        include_details: bool = True,
    ) -> dict:
        """
        Create a standardized error response
        
        Args:
            exception: The exception that occurred
            status_code: HTTP status code
            include_details: Whether to include exception details (disable in production)
        
        Returns:
            Dictionary suitable for JSON response
        """
        category = classify_error(exception)
        
        response = {
            "error": True,
            "status": status_code,
            "category": category.value,
            "message": str(exception) if include_details else "An error occurred",
            "timestamp": datetime.now().isoformat(),
        }
        
        if include_details:
            response["exception_type"] = type(exception).__name__
        
        return response
    
    @staticmethod
    def get_status_code(exception: Exception) -> int:
        """Determine appropriate HTTP status code for exception"""
        category = classify_error(exception)
        
        status_map = {
            ErrorCategory.VALIDATION: 400,
            ErrorCategory.BAD_REQUEST: 400,
            ErrorCategory.AUTHENTICATION: 401,
            ErrorCategory.AUTHORIZATION: 403,
            ErrorCategory.NOT_FOUND: 404,
            ErrorCategory.TIMEOUT: 504,
            ErrorCategory.SERVER_ERROR: 500,
            ErrorCategory.SERVICE_UNAVAILABLE: 503,
            ErrorCategory.DATABASE_ERROR: 500,
        }
        
        return status_map.get(category, 500)
    
    @staticmethod
    def handle_api_error(exception: Exception, include_details: bool = True) -> tuple[dict, int]:
        """
        Handle API error and return response + status code
        
        Returns:
            Tuple of (response_dict, status_code)
        """
        status_code = APIErrorHandler.get_status_code(exception)
        response = APIErrorHandler.create_error_response(
            exception,
            status_code,
            include_details
        )
        
        # Log error
        context = ErrorContext(
            exception=exception,
            function_name="API_Handler",
        )
        context.log()
        
        return response, status_code


# ── WebSocket Error Handler ───────────────────────────────────────────────────

class WebSocketErrorHandler:
    """Handles errors for WebSocket connections"""
    
    @staticmethod
    async def send_error(websocket, exception: Exception):
        """
        Send error message through WebSocket
        
        Args:
            websocket: WebSocket connection object
            exception: The exception to send
        """
        import json
        
        category = classify_error(exception)
        
        error_message = {
            "type": "error",
            "category": category.value,
            "message": str(exception),
            "timestamp": datetime.now().isoformat(),
        }
        
        try:
            await websocket.send_json(error_message)
        except Exception as send_error:
            logger.error(f"Failed to send error through WebSocket: {send_error}")
    
    @staticmethod
    def should_close_on_error(exception: Exception) -> bool:
        """Determine if WebSocket should close on this error"""
        category = classify_error(exception)
        
        close_on_error = {
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.AUTHORIZATION,
        }
        
        return category in close_on_error


# ── Graceful Degradation ──────────────────────────────────────────────────────

class GracefulDegradation:
    """Provides fallback strategies for service failures"""
    
    @staticmethod
    def with_fallback(primary_func: Callable, fallback_func: Callable) -> Any:
        """
        Try primary function, fall back to secondary on failure
        
        Args:
            primary_func: Primary function to try
            fallback_func: Fallback function if primary fails
        
        Returns:
            Result from primary or fallback function
        """
        try:
            return primary_func()
        except Exception as e:
            logger.warning(
                f"Primary function failed: {type(e).__name__}. "
                f"Using fallback."
            )
            return fallback_func()
    
    @staticmethod
    async def with_fallback_async(
        primary_func: Callable,
        fallback_func: Callable
    ) -> Any:
        """Async version of with_fallback"""
        try:
            return await primary_func()
        except Exception as e:
            logger.warning(
                f"Primary function failed: {type(e).__name__}. "
                f"Using fallback."
            )
            return await fallback_func()
    
    @staticmethod
    def with_default(func: Callable, default_value: Any) -> Any:
        """
        Execute function, return default value on error
        
        Args:
            func: Function to execute
            default_value: Default value to return on error
        
        Returns:
            Function result or default value
        """
        try:
            return func()
        except Exception as e:
            logger.warning(
                f"Function failed: {type(e).__name__}. "
                f"Returning default value: {default_value}"
            )
            return default_value


# ── Error Reporter ────────────────────────────────────────────────────────────

class ErrorReporter:
    """Reports errors for monitoring and alerting"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: list[ErrorContext] = []
        self.max_recent_errors = 100
    
    def report(self, context: ErrorContext):
        """Report an error"""
        # Count errors by type
        error_key = f"{context.exception_type}:{context.function_name}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Store recent errors
        self.recent_errors.append(context)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # Log to monitoring system (extend as needed)
        logger.error(
            f"Error reported: {context.exception_type} in {context.function_name}",
            extra=context.to_dict()
        )
    
    def get_stats(self) -> dict:
        """Get error statistics"""
        return {
            "total_errors": len(self.recent_errors),
            "error_counts": self.error_counts,
            "recent_errors": [ctx.to_dict() for ctx in self.recent_errors[-10:]],
        }


# Global error reporter
error_reporter = ErrorReporter()


# ── Example Usage ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example 1: Basic error handling
    print("Example 1: Basic error handling with retry")
    
    @handle_error(retry_attempts=3)
    def flaky_function():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Network error")
        return "Success!"
    
    try:
        result = flaky_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")
    
    # Example 2: With fallback
    print("\nExample 2: Error handling with fallback")
    
    @handle_error(fallback=lambda: "Fallback value", reraise=False)
    def always_fails():
        raise ValueError("Always fails")
    
    result = always_fails()
    print(f"Result: {result}")
    
    # Example 3: API error handling
    print("\nExample 3: API error handling")
    
    try:
        raise ConnectionError("Database connection failed")
    except Exception as e:
        response, status = APIErrorHandler.handle_api_error(e)
        print(f"Status: {status}")
        print(f"Response: {response}")
    
    # Example 4: Graceful degradation
    print("\nExample 4: Graceful degradation")
    
    def primary_service():
        raise TimeoutError("Service timeout")
    
    def backup_service():
        return "Backup data"
    
    result = GracefulDegradation.with_fallback(primary_service, backup_service)
    print(f"Result: {result}")
    
    # Example 5: Error reporter stats
    print("\nExample 5: Error reporter stats")
    print(f"Error stats: {error_reporter.get_stats()}")
