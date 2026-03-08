"""
stress_test.py — Stress Testing Tool for Crochetzies Chatbot
Simulates multiple concurrent users to test system performance under load

Features:
- Concurrent user simulation
- Peak load testing
- Sustained load testing
- Ramp-up testing (gradual increase in users)
- Real-time metrics (throughput, error rate, response times)
- Resource monitoring (CPU, memory)
- Detailed HTML report generation

Usage:
    python stress_test.py --users 10 --duration 60      # 10 users for 60 seconds
    python stress_test.py --ramp-up 50 --ramp-time 30   # Ramp from 1 to 50 users over 30s
    python stress_test.py --peak-load 100 --duration 10 # Spike test: 100 users for 10s
    python stress_test.py --report stress_report.html   # Save detailed report
"""

import argparse
import asyncio
import json
import random
import statistics
import time
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any
import sys

import requests
import websockets

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. System metrics will not be available.")
    print("Install with: pip install psutil")


# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"

# Realistic conversation patterns
CONVERSATION_FLOWS = [
    # Quick order
    ["hello", "I want a cat", "pink", "small", "none", "Sara", "Lahore, Pakistan", "yes"],
    # Detailed order
    ["hi", "I want a large blue dinosaur", "Add rainbow stripes", "Ali", "Karachi", "confirm"],
    # Uncertain customer
    ["hello", "not sure what I want", "maybe a bear", "brown", "medium", "no", "Zara", "Islamabad", "yes"],
    # Multi-detail input
    ["hi", "medium green bunny with floppy ears", "Bilal", "Rawalpindi", "yes"],
    # Short conversation
    ["hello", "crochet frog", "green", "small", "none", "Test User", "Test City", "yes"],
]


# ── ANSI Colors ───────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


# ── Virtual User ──────────────────────────────────────────────────────────────

class VirtualUser:
    """Simulates a single user interacting with the chatbot"""
    
    def __init__(self, user_id: int, metrics: 'MetricsCollector'):
        self.user_id = user_id
        self.metrics = metrics
        self.session_id = None
        self.conversation = random.choice(CONVERSATION_FLOWS).copy()
        
    async def run(self):
        """Execute a full conversation"""
        try:
            # Create session
            session_created = await self._create_session()
            if not session_created:
                self.metrics.record_error("session_creation_failed")
                return
            
            # Execute conversation turns
            for message in self.conversation:
                success = await self._send_message(message)
                if not success:
                    break
                    
                # Add random think time (0.5-2 seconds)
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Clean up session
            await self._delete_session()
            
            self.metrics.record_success()
            
        except Exception as e:
            self.metrics.record_error(f"user_error: {str(e)[:50]}")
    
    async def _create_session(self) -> bool:
        """Create a new session"""
        try:
            start = time.perf_counter()
            response = requests.post(f"{API_BASE_URL}/session/new", timeout=10)
            elapsed = time.perf_counter() - start
            
            if response.status_code == 200:
                self.session_id = response.json().get("session_id")
                self.metrics.record_request("session_create", elapsed, True)
                return True
            else:
                self.metrics.record_request("session_create", elapsed, False)
                return False
        except Exception as e:
            self.metrics.record_error(f"session_create_exception: {str(e)[:30]}")
            return False
    
    async def _send_message(self, message: str) -> bool:
        """Send a message and wait for complete response"""
        if not self.session_id:
            return False
            
        try:
            start = time.perf_counter()
            
            async with websockets.connect(f"{WS_BASE_URL}/ws/chat/{self.session_id}", 
                                         close_timeout=5) as ws:
                await ws.send(json.dumps({"message": message}))
                
                # Wait for done signal
                timeout_time = time.time() + 30  # 30 second timeout
                while time.time() < timeout_time:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(msg)
                        
                        if data.get("type") == "done":
                            elapsed = time.perf_counter() - start
                            self.metrics.record_request("message_send", elapsed, True)
                            return True
                        elif data.get("type") == "session_end":
                            elapsed = time.perf_counter() - start
                            self.metrics.record_request("message_send", elapsed, True)
                            return True
                        elif data.get("type") == "error":
                            self.metrics.record_error("ws_error")
                            return False
                            
                    except asyncio.TimeoutError:
                        continue
                
                # If we get here, we timed out
                self.metrics.record_error("message_timeout")
                return False
                
        except Exception as e:
            self.metrics.record_error(f"ws_exception: {str(e)[:30]}")
            return False
    
    async def _delete_session(self):
        """Delete the session"""
        if not self.session_id:
            return
            
        try:
            requests.delete(f"{API_BASE_URL}/session/{self.session_id}", timeout=5)
        except:
            pass


# ── Metrics Collector ─────────────────────────────────────────────────────────

class MetricsCollector:
    """Collects and aggregates metrics from all virtual users"""
    
    def __init__(self):
        self.start_time = time.time()
        self.request_times = defaultdict(list)
        self.request_counts = defaultdict(int)
        self.success_count = 0
        self.error_counts = defaultdict(int)
        self.total_requests = 0
        self.failed_requests = 0
        self.completed_conversations = 0
        self.lock = asyncio.Lock()
        
    def record_request(self, endpoint: str, elapsed: float, success: bool):
        """Record a request"""
        self.request_times[endpoint].append(elapsed * 1000)  # Convert to ms
        self.request_counts[endpoint] += 1
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
    
    def record_success(self):
        """Record a successful conversation"""
        self.completed_conversations += 1
        self.success_count += 1
    
    def record_error(self, error_type: str):
        """Record an error"""
        self.error_counts[error_type] += 1
        self.failed_requests += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        elapsed_time = time.time() - self.start_time
        
        summary = {
            "duration_seconds": round(elapsed_time, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.total_requests - self.failed_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round((self.total_requests - self.failed_requests) / max(self.total_requests, 1) * 100, 2),
            "completed_conversations": self.completed_conversations,
            "requests_per_second": round(self.total_requests / max(elapsed_time, 1), 2),
            "error_breakdown": dict(self.error_counts),
        }
        
        # Add per-endpoint stats
        endpoint_stats = {}
        for endpoint, times in self.request_times.items():
            if times:
                sorted_times = sorted(times)
                n = len(sorted_times)
                endpoint_stats[endpoint] = {
                    "count": len(times),
                    "min_ms": round(min(times), 2),
                    "max_ms": round(max(times), 2),
                    "mean_ms": round(statistics.mean(times), 2),
                    "median_ms": round(statistics.median(times), 2),
                    "p95_ms": round(sorted_times[int(n * 0.95)], 2) if n > 0 else 0,
                    "p99_ms": round(sorted_times[int(n * 0.99)], 2) if n > 0 else 0,
                }
        
        summary["endpoint_stats"] = endpoint_stats
        
        return summary
    
    def print_summary(self):
        """Print formatted summary"""
        summary = self.get_summary()
        
        print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
        print(f"{BOLD}{CYAN}Stress Test Results{RESET}")
        print(f"{BOLD}{CYAN}{'='*70}{RESET}")
        
        print(f"\n{BOLD}Overall Performance:{RESET}")
        print(f"  Duration:                {summary['duration_seconds']:.2f} seconds")
        print(f"  Total Requests:          {summary['total_requests']}")
        print(f"  Successful:              {GREEN}{summary['successful_requests']}{RESET}")
        print(f"  Failed:                  {RED if summary['failed_requests'] > 0 else GREEN}{summary['failed_requests']}{RESET}")
        print(f"  Success Rate:            {GREEN if summary['success_rate'] >= 95 else YELLOW if summary['success_rate'] >= 80 else RED}{summary['success_rate']:.2f}%{RESET}")
        print(f"  Throughput:              {summary['requests_per_second']:.2f} req/s")
        print(f"  Completed Conversations: {summary['completed_conversations']}")
        
        if summary['error_breakdown']:
            print(f"\n{BOLD}Errors:{RESET}")
            for error_type, count in sorted(summary['error_breakdown'].items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {RED}{count}{RESET}")
        
        if summary['endpoint_stats']:
            print(f"\n{BOLD}Response Times by Endpoint:{RESET}")
            for endpoint, stats in summary['endpoint_stats'].items():
                print(f"\n  {CYAN}{endpoint}{RESET} ({stats['count']} requests)")
                print(f"    Min:    {stats['min_ms']:.2f} ms")
                print(f"    Mean:   {stats['mean_ms']:.2f} ms")
                print(f"    Median: {stats['median_ms']:.2f} ms")
                print(f"    P95:    {stats['p95_ms']:.2f} ms")
                print(f"    P99:    {stats['p99_ms']:.2f} ms")
                print(f"    Max:    {stats['max_ms']:.2f} ms")


# ── System Monitor ────────────────────────────────────────────────────────────

class SystemMonitor:
    """Monitors system resource usage during stress test"""
    
    def __init__(self):
        self.cpu_samples = []
        self.memory_samples = []
        self.running = False
        
    async def start(self):
        """Start monitoring"""
        if not HAS_PSUTIL:
            return
            
        self.running = True
        
        while self.running:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                
                self.cpu_samples.append(cpu_percent)
                self.memory_samples.append(memory_info.percent)
                
                await asyncio.sleep(2)
            except:
                break
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system stats summary"""
        if not self.cpu_samples:
            return {}
            
        return {
            "cpu_mean": round(statistics.mean(self.cpu_samples), 2),
            "cpu_max": round(max(self.cpu_samples), 2),
            "memory_mean": round(statistics.mean(self.memory_samples), 2),
            "memory_max": round(max(self.memory_samples), 2),
        }
    
    def print_stats(self):
        """Print system stats"""
        stats = self.get_stats()
        
        if not stats:
            return
            
        print(f"\n{BOLD}System Resources:{RESET}")
        print(f"  CPU Usage (mean):    {stats['cpu_mean']:.1f}%")
        print(f"  CPU Usage (peak):    {stats['cpu_max']:.1f}%")
        print(f"  Memory Usage (mean): {stats['memory_mean']:.1f}%")
        print(f"  Memory Usage (peak): {stats['memory_max']:.1f}%")


# ── Test Scenarios ────────────────────────────────────────────────────────────

async def sustained_load_test(num_users: int, duration: int, metrics: MetricsCollector):
    """Run sustained load test with constant number of users"""
    print(f"\n{BOLD}Running sustained load test:{RESET}")
    print(f"  Users: {num_users}")
    print(f"  Duration: {duration} seconds")
    print(f"\n{YELLOW}Test in progress...{RESET}\n")
    
    monitor = SystemMonitor()
    monitor_task = asyncio.create_task(monitor.start())
    
    end_time = time.time() + duration
    tasks = []
    user_id = 0
    
    try:
        while time.time() < end_time:
            # Maintain constant number of active users
            while len(tasks) < num_users and time.time() < end_time:
                user = VirtualUser(user_id, metrics)
                task = asyncio.create_task(user.run())
                tasks.append(task)
                user_id += 1
            
            # Remove completed tasks
            tasks = [t for t in tasks if not t.done()]
            
            # Print progress
            elapsed = time.time() - metrics.start_time
            print(f"\r  Elapsed: {elapsed:.0f}s | Active users: {len(tasks)} | "
                  f"Requests: {metrics.total_requests} | "
                  f"Errors: {RED if metrics.failed_requests > 0 else GREEN}{metrics.failed_requests}{RESET}",
                  end="", flush=True)
            
            await asyncio.sleep(0.1)
        
        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    finally:
        monitor.stop()
        await monitor_task
    
    print(f"\n\n{GREEN}Test complete!{RESET}")
    
    metrics.print_summary()
    monitor.print_stats()


async def ramp_up_test(target_users: int, ramp_time: int, hold_time: int, metrics: MetricsCollector):
    """Gradually ramp up from 1 user to target_users"""
    print(f"\n{BOLD}Running ramp-up test:{RESET}")
    print(f"  Target users: {target_users}")
    print(f"  Ramp-up time: {ramp_time} seconds")
    print(f"  Hold time: {hold_time} seconds")
    print(f"\n{YELLOW}Test in progress...{RESET}\n")
    
    monitor = SystemMonitor()
    monitor_task = asyncio.create_task(monitor.start())
    
    start_time = time.time()
    tasks = []
    user_id = 0
    
    try:
        # Ramp-up phase
        ramp_end = start_time + ramp_time
        while time.time() < ramp_end:
            elapsed = time.time() - start_time
            current_target = int((elapsed / ramp_time) * target_users)
            
            # Add users to reach current target
            while len(tasks) < current_target:
                user = VirtualUser(user_id, metrics)
                task = asyncio.create_task(user.run())
                tasks.append(task)
                user_id += 1
            
            # Remove completed tasks
            tasks = [t for t in tasks if not t.done()]
            
            print(f"\r  Ramp-up: {len(tasks)}/{target_users} users | "
                  f"Requests: {metrics.total_requests} | "
                  f"Errors: {RED if metrics.failed_requests > 0 else GREEN}{metrics.failed_requests}{RESET}",
                  end="", flush=True)
            
            await asyncio.sleep(0.5)
        
        # Hold phase
        print(f"\n\n{BOLD}  Holding at {target_users} users for {hold_time} seconds...{RESET}\n")
        hold_end = time.time() + hold_time
        
        while time.time() < hold_end:
            # Maintain target users
            while len(tasks) < target_users and time.time() < hold_end:
                user = VirtualUser(user_id, metrics)
                task = asyncio.create_task(user.run())
                tasks.append(task)
                user_id += 1
            
            tasks = [t for t in tasks if not t.done()]
            
            remaining = hold_end - time.time()
            print(f"\r  Hold: {len(tasks)} users | Remaining: {remaining:.0f}s | "
                  f"Requests: {metrics.total_requests} | "
                  f"Errors: {RED if metrics.failed_requests > 0 else GREEN}{metrics.failed_requests}{RESET}",
                  end="", flush=True)
            
            await asyncio.sleep(0.1)
        
        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    finally:
        monitor.stop()
        await monitor_task
    
    print(f"\n\n{GREEN}Test complete!{RESET}")
    
    metrics.print_summary()
    monitor.print_stats()


async def spike_test(peak_users: int, duration: int, metrics: MetricsCollector):
    """Sudden spike to peak_users"""
    print(f"\n{BOLD}Running spike test:{RESET}")
    print(f"  Peak users: {peak_users}")
    print(f"  Duration: {duration} seconds")
    print(f"\n{YELLOW}Launching {peak_users} users simultaneously...{RESET}\n")
    
    monitor = SystemMonitor()
    monitor_task = asyncio.create_task(monitor.start())
    
    # Launch all users at once
    tasks = []
    for i in range(peak_users):
        user = VirtualUser(i, metrics)
        task = asyncio.create_task(user.run())
        tasks.append(task)
    
    # Monitor progress
    start_time = time.time()
    end_time = start_time + duration
    
    try:
        while time.time() < end_time:
            active = len([t for t in tasks if not t.done()])
            print(f"\r  Active users: {active}/{peak_users} | "
                  f"Requests: {metrics.total_requests} | "
                  f"Errors: {RED if metrics.failed_requests > 0 else GREEN}{metrics.failed_requests}{RESET}",
                  end="", flush=True)
            
            await asyncio.sleep(0.1)
        
        # Wait for all to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
    finally:
        monitor.stop()
        await monitor_task
    
    print(f"\n\n{GREEN}Test complete!{RESET}")
    
    metrics.print_summary()
    monitor.print_stats()


# ── HTML Report Generator ─────────────────────────────────────────────────────

def generate_html_report(metrics: MetricsCollector, monitor: SystemMonitor, filename: str):
    """Generate a detailed HTML report"""
    summary = metrics.get_summary()
    sys_stats = monitor.get_stats()
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Stress Test Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ font-weight: bold; color: #666; }}
        .metric-value {{ font-size: 1.2em; color: #333; }}
        .success {{ color: #4CAF50; }}
        .warning {{ color: #FF9800; }}
        .error {{ color: #F44336; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .chart {{ margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧶 Crochetzies Chatbot - Stress Test Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Overall Performance</h2>
        <div class="metric">
            <span class="metric-label">Duration:</span>
            <span class="metric-value">{summary['duration_seconds']:.2f}s</span>
        </div>
        <div class="metric">
            <span class="metric-label">Total Requests:</span>
            <span class="metric-value">{summary['total_requests']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Success Rate:</span>
            <span class="metric-value {'success' if summary['success_rate'] >= 95 else 'warning' if summary['success_rate'] >= 80 else 'error'}">
                {summary['success_rate']:.2f}%
            </span>
        </div>
        <div class="metric">
            <span class="metric-label">Throughput:</span>
            <span class="metric-value">{summary['requests_per_second']:.2f} req/s</span>
        </div>
        <div class="metric">
            <span class="metric-label">Completed Conversations:</span>
            <span class="metric-value">{summary['completed_conversations']}</span>
        </div>
        
        <h2>Response Time Statistics</h2>
        <table>
            <tr>
                <th>Endpoint</th>
                <th>Requests</th>
                <th>Min (ms)</th>
                <th>Mean (ms)</th>
                <th>Median (ms)</th>
                <th>P95 (ms)</th>
                <th>P99 (ms)</th>
                <th>Max (ms)</th>
            </tr>
"""
    
    for endpoint, stats in summary.get('endpoint_stats', {}).items():
        html += f"""            <tr>
                <td><strong>{endpoint}</strong></td>
                <td>{stats['count']}</td>
                <td>{stats['min_ms']:.2f}</td>
                <td>{stats['mean_ms']:.2f}</td>
                <td>{stats['median_ms']:.2f}</td>
                <td>{stats['p95_ms']:.2f}</td>
                <td>{stats['p99_ms']:.2f}</td>
                <td>{stats['max_ms']:.2f}</td>
            </tr>
"""
    
    html += """        </table>
        
"""
    
    if sys_stats:
        html += f"""        <h2>System Resources</h2>
        <div class="metric">
            <span class="metric-label">CPU (mean):</span>
            <span class="metric-value">{sys_stats['cpu_mean']:.1f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">CPU (peak):</span>
            <span class="metric-value">{sys_stats['cpu_max']:.1f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Memory (mean):</span>
            <span class="metric-value">{sys_stats['memory_mean']:.1f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Memory (peak):</span>
            <span class="metric-value">{sys_stats['memory_max']:.1f}%</span>
        </div>
"""
    
    if summary.get('error_breakdown'):
        html += """        
        <h2>Error Breakdown</h2>
        <table>
            <tr>
                <th>Error Type</th>
                <th>Count</th>
            </tr>
"""
        for error_type, count in sorted(summary['error_breakdown'].items(), key=lambda x: -x[1]):
            html += f"""            <tr>
                <td>{error_type}</td>
                <td class="error">{count}</td>
            </tr>
"""
        html += """        </table>
"""
    
    html += """    </div>
</body>
</html>"""
    
    with open(filename, 'w') as f:
        f.write(html)
    
    print(f"\n{GREEN}HTML report saved to: {filename}{RESET}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Stress test Crochetzies chatbot")
    parser.add_argument("--users", type=int, help="Number of concurrent users (sustained load test)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--ramp-up", type=int, help="Target users for ramp-up test")
    parser.add_argument("--ramp-time", type=int, default=30, help="Ramp-up duration in seconds")
    parser.add_argument("--hold-time", type=int, default=60, help="Hold time after ramp-up")
    parser.add_argument("--peak-load", type=int, help="Number of users for spike test")
    parser.add_argument("--report", type=str, help="Generate HTML report to file")
    
    args = parser.parse_args()
    
    if not any([args.users, args.ramp_up, args.peak_load]):
        print(f"{RED}Error: Please specify --users, --ramp-up, or --peak-load{RESET}")
        parser.print_help()
        return
    
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}Crochetzies Chatbot - Stress Test Suite{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"Target: {API_BASE_URL}")
    
    metrics = MetricsCollector()
    monitor = SystemMonitor()
    
    try:
        if args.users:
            await sustained_load_test(args.users, args.duration, metrics)
        elif args.ramp_up:
            await ramp_up_test(args.ramp_up, args.ramp_time, args.hold_time, metrics)
        elif args.peak_load:
            await spike_test(args.peak_load, args.duration, metrics)
        
        if args.report:
            generate_html_report(metrics, monitor, args.report)
            
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Test interrupted by user{RESET}")
        metrics.print_summary()
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
