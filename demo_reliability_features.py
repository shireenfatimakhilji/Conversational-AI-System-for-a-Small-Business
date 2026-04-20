"""
demo_reliability_features.py — Demonstration of Testing & Reliability Features

This script demonstrates how to use:
1. Retry logic
2. Circuit breaker
3. Error handling
4. Graceful degradation

Run this to see all features in action!

Usage:
    python demo_reliability_features.py
"""

import asyncio
import random
import time
from typing import Optional

# Import our new reliability modules
from retry_utils import retry, async_retry
from circuit_breaker import CircuitBreaker, get_circuit_breaker
from error_handlers import (
    handle_error,
    APIErrorHandler,
    GracefulDegradation,
    ErrorContext
)


# ── ANSI Colors ───────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_section(title: str):
    """Print a section header"""
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}{title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 1: Retry Logic
# ══════════════════════════════════════════════════════════════════════════════

def demo_retry():
    """Demonstrate retry logic with exponential backoff"""
    print_section("Demo 1: Retry Logic with Exponential Backoff")
    
    # Simulate a flaky service that fails 70% of the time
    call_count = {"count": 0}
    
    @retry(max_attempts=5, backoff_base=1.5, jitter=True)
    def flaky_service():
        call_count["count"] += 1
        print(f"  Attempt {call_count['count']}: Calling flaky service...")
        
        if random.random() < 0.7:
            print(f"    {RED}✗ Failed{RESET}")
            raise ConnectionError("Service temporarily unavailable")
        
        print(f"    {GREEN}✓ Success!{RESET}")
        return "Data from service"
    
    try:
        result = flaky_service()
        print(f"\n{GREEN}Final result: {result}{RESET}")
    except Exception as e:
        print(f"\n{RED}All retries exhausted: {e}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 2: Circuit Breaker
# ══════════════════════════════════════════════════════════════════════════════

def demo_circuit_breaker():
    """Demonstrate circuit breaker pattern"""
    print_section("Demo 2: Circuit Breaker Pattern")
    
    # Create circuit breaker with low threshold for demo
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5,
        expected_exception=ConnectionError,
        name="Demo_Service"
    )
    
    call_count = {"count": 0}
    
    @breaker
    def unreliable_service():
        call_count["count"] += 1
        print(f"  Call {call_count['count']}: Attempting call...")
        
        # Fail most of the time
        if random.random() < 0.9:
            print(f"    {RED}✗ Service failed{RESET}")
            raise ConnectionError("Service error")
        
        print(f"    {GREEN}✓ Success{RESET}")
        return "Success"
    
    # Make calls until circuit opens
    print("Making calls until circuit opens...")
    for i in range(10):
        try:
            result = unreliable_service()
            print(f"    Result: {result}")
        except Exception as e:
            error_type = type(e).__name__
            if error_type == "CircuitBreakerError":
                print(f"    {YELLOW}⊗ Circuit is OPEN - call rejected{RESET}")
            else:
                print(f"    {RED}✗ Error: {error_type}{RESET}")
        
        time.sleep(0.5)
    
    # Show metrics
    metrics = breaker.get_metrics()
    print(f"\n{BOLD}Circuit Breaker Metrics:{RESET}")
    print(f"  State: {YELLOW if metrics['state'] == 'OPEN' else GREEN}{metrics['state']}{RESET}")
    print(f"  Total calls: {metrics['total_calls']}")
    print(f"  Successes: {metrics['total_successes']}")
    print(f"  Failures: {metrics['total_failures']}")
    print(f"  Rejected: {metrics['total_rejected']}")
    print(f"  Success rate: {metrics['success_rate']:.2f}%")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 3: Combined Retry + Circuit Breaker
# ══════════════════════════════════════════════════════════════════════════════

def demo_retry_with_circuit_breaker():
    """Demonstrate retry logic combined with circuit breaker"""
    print_section("Demo 3: Retry + Circuit Breaker Combined")
    
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout=3,
        name="Combined_Service"
    )
    
    @breaker
    @retry(max_attempts=3, backoff_base=1.2)
    def protected_service():
        print("    Calling protected service...")
        if random.random() < 0.8:
            raise TimeoutError("Request timeout")
        return "Success"
    
    print("This service has both retry logic AND circuit breaker protection.")
    print("It will retry 3 times, and if failures persist, circuit opens.\n")
    
    for i in range(8):
        try:
            result = protected_service()
            print(f"  Call {i+1}: {GREEN}{result}{RESET}")
        except Exception as e:
            print(f"  Call {i+1}: {RED}{type(e).__name__}{RESET}")
        
        time.sleep(0.3)


# ══════════════════════════════════════════════════════════════════════════════
# Demo 4: Error Handling and Classification
# ══════════════════════════════════════════════════════════════════════════════

def demo_error_handling():
    """Demonstrate error handling and classification"""
    print_section("Demo 4: Error Handling and Classification")
    
    def on_retry_callback(attempt, exception, delay):
        print(f"    Retry callback: Attempt {attempt}, waiting {delay:.2f}s")
    
    @handle_error(
        retry_enabled=True,
        retry_attempts=3,
        fallback=lambda: "Fallback value",
        log_errors=True,
        reraise=False
    )
    def risky_operation():
        print("  Executing risky operation...")
        raise ValueError("Something went wrong!")
    
    result = risky_operation()
    print(f"  {YELLOW}Result (using fallback): {result}{RESET}")
    
    # Test API error handler
    print(f"\n{BOLD}API Error Response Generation:{RESET}")
    try:
        raise ConnectionError("Database connection failed")
    except Exception as e:
        response, status = APIErrorHandler.handle_api_error(e, include_details=True)
        print(f"  Status code: {status}")
        print(f"  Response: {response}")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 5: Graceful Degradation
# ══════════════════════════════════════════════════════════════════════════════

def demo_graceful_degradation():
    """Demonstrate graceful degradation strategies"""
    print_section("Demo 5: Graceful Degradation")
    
    print(f"{BOLD}Scenario: Primary ML model is down, fallback to cached responses{RESET}\n")
    
    def primary_ml_model():
        print("  Trying primary ML model...")
        raise ConnectionError("ML model service unavailable")
    
    def cached_response():
        print("  Using cached response (fallback)...")
        return "Hello! I'm Crochetzies. What would you like to order?"
    
    result = GracefulDegradation.with_fallback(
        primary_ml_model,
        cached_response
    )
    print(f"  {GREEN}Result: {result}{RESET}")
    
    # With default value
    print(f"\n{BOLD}With default value:{RESET}")
    
    def failing_service():
        raise TimeoutError("Service timeout")
    
    result = GracefulDegradation.with_default(
        failing_service,
        "Default response"
    )
    print(f"  Result: {result}")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 6: Async Retry
# ══════════════════════════════════════════════════════════════════════════════

async def demo_async_retry():
    """Demonstrate async retry logic"""
    print_section("Demo 6: Async Retry Logic")
    
    attempt_count = {"count": 0}
    
    @async_retry(max_attempts=4, backoff_base=1.3)
    async def async_flaky_service():
        attempt_count["count"] += 1
        print(f"  Async attempt {attempt_count['count']}: Calling service...")
        
        await asyncio.sleep(0.1)  # Simulate async operation
        
        if random.random() < 0.7:
            print(f"    {RED}✗ Failed{RESET}")
            raise TimeoutError("Request timeout")
        
        print(f"    {GREEN}✓ Success!{RESET}")
        return "Async data"
    
    try:
        result = await async_flaky_service()
        print(f"\n{GREEN}Final result: {result}{RESET}")
    except Exception as e:
        print(f"\n{RED}All retries exhausted: {e}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# Demo 7: Real-World Example
# ══════════════════════════════════════════════════════════════════════════════

def demo_real_world_example():
    """Demonstrate a real-world scenario with all features"""
    print_section("Demo 7: Real-World Example - Chat API Endpoint")
    
    print(f"{BOLD}Simulating a chat API endpoint with:{RESET}")
    print("  - Retry logic for transient failures")
    print("  - Circuit breaker for ML model")
    print("  - Graceful degradation to cached responses")
    print("  - Error handling and classification\n")
    
    # Create circuit breaker for ML model
    ml_breaker = get_circuit_breaker(
        "ML_Model",
        failure_threshold=2,
        recovery_timeout=5
    )
    
    call_count = {"ml": 0, "cache": 0}
    
    def ml_model_inference(message: str) -> str:
        """Simulate ML model that sometimes fails"""
        call_count["ml"] += 1
        
        @ml_breaker
        @retry(max_attempts=2, exceptions=(TimeoutError,))
        def call_model():
            if random.random() < 0.6:  # 60% failure rate
                raise TimeoutError("Model inference timeout")
            return f"ML response to: {message}"
        
        return call_model()
    
    def cached_response(message: str) -> str:
        """Fallback to cached response"""
        call_count["cache"] += 1
        return f"Cached response to: {message}"
    
    def chat_endpoint(message: str) -> str:
        """Chat endpoint with full error handling"""
        print(f"  Processing: '{message}'")
        
        try:
            response = GracefulDegradation.with_fallback(
                lambda: ml_model_inference(message),
                lambda: cached_response(message)
            )
            print(f"    {GREEN}✓ {response}{RESET}")
            return response
            
        except Exception as e:
            error_response, status = APIErrorHandler.handle_api_error(e)
            print(f"    {RED}✗ Error {status}: {error_response['message']}{RESET}")
            return f"Error: {error_response['message']}"
    
    # Simulate multiple requests
    messages = [
        "Hello",
        "I want a cat",
        "What colors?",
        "Pink and white",
        "What size?",
    ]
    
    for msg in messages:
        chat_endpoint(msg)
        time.sleep(0.5)
    
    print(f"\n{BOLD}Statistics:{RESET}")
    print(f"  ML model calls: {call_count['ml']}")
    print(f"  Cache fallbacks: {call_count['cache']}")
    print(f"  ML Breaker state: {ml_breaker.get_state().value}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Run all demos"""
    print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}Crochetzies - Reliability Features Demonstration{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"\nThis demo shows all testing and reliability features in action.")
    print(f"Watch how the system handles failures gracefully!\n")
    
    try:
        # Run synchronous demos
        demo_retry()
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        demo_circuit_breaker()
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        demo_retry_with_circuit_breaker()
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        demo_error_handling()
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        demo_graceful_degradation()
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        # Run async demo
        asyncio.run(demo_async_retry())
        input(f"\n{YELLOW}Press Enter to continue...{RESET}")
        
        demo_real_world_example()
        
        print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"{BOLD}{GREEN}Demo Complete!{RESET}")
        print(f"{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"\nAll reliability features demonstrated successfully.")
        print(f"Check the logs above to see how errors were handled.\n")
        
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Demo interrupted by user{RESET}\n")


if __name__ == "__main__":
    main()
