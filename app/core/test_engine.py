import asyncio
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional, Callable
from .dns_resolver import AsyncDNSResolver


class TestEngine:
    """Main DNS testing engine with continuous loop and result buffer."""

    def __init__(
        self,
        domains: List[str],
        dns_servers: List[Dict],
        interval_seconds: float = 5.0,
        timeout_seconds: float = 3.0,
        max_concurrent_queries: int = 10,
        history_buffer_size: int = 1000
    ):
        """
        Initialize the test engine.

        Args:
            domains: List of domains to test
            dns_servers: List of DNS server configurations
            interval_seconds: Interval between test iterations
            timeout_seconds: Timeout for each DNS query
            max_concurrent_queries: Maximum concurrent DNS queries
            history_buffer_size: Size of the circular result buffer
        """
        self.domains = domains
        self.dns_servers = dns_servers
        self.interval_seconds = interval_seconds
        self.history_buffer_size = history_buffer_size

        # Initialize DNS resolver
        self.resolver = AsyncDNSResolver(
            timeout=timeout_seconds,
            max_concurrent=max_concurrent_queries
        )

        # Circular buffer for recent results
        self.results_buffer: deque = deque(maxlen=history_buffer_size)

        # Iteration counter
        self.iteration_count = 0

        # Running flag
        self.is_running = False

        # Callbacks
        self.on_result_callback: Optional[Callable] = None
        self.logger_callback: Optional[Callable] = None

    def set_result_callback(self, callback: Callable):
        """Set callback function to be called after each test iteration."""
        self.on_result_callback = callback

    def set_logger_callback(self, callback: Callable):
        """Set callback function for logging results."""
        self.logger_callback = callback

    async def run(self):
        """
        Main loop that runs DNS tests continuously.

        This method runs indefinitely until stopped.
        Each iteration:
        1. Resolves all domain×DNS combinations
        2. Stores results in buffer
        3. Calls callbacks (broadcast, logging)
        4. Waits for the next interval
        """
        self.is_running = True

        while self.is_running:
            try:
                # Perform DNS resolution batch
                results = await self.resolver.resolve_batch(
                    domains=self.domains,
                    dns_servers=self.dns_servers
                )

                self.iteration_count += 1

                # Add metadata to results
                timestamp = datetime.utcnow().isoformat() + "Z"
                for result in results:
                    result["timestamp"] = timestamp
                    result["iteration"] = self.iteration_count

                # Store in buffer
                self.results_buffer.extend(results)

                # Prepare broadcast data
                broadcast_data = {
                    "type": "test_result",
                    "timestamp": timestamp,
                    "iteration": self.iteration_count,
                    "results": results
                }

                # Call result callback (WebSocket broadcast)
                if self.on_result_callback:
                    try:
                        await self.on_result_callback(broadcast_data)
                    except Exception as e:
                        print(f"Error in result callback: {e}")

                # Call logger callback
                if self.logger_callback:
                    try:
                        await self.logger_callback(results)
                    except Exception as e:
                        print(f"Error in logger callback: {e}")

                # Wait for next interval
                await asyncio.sleep(self.interval_seconds)

            except Exception as e:
                print(f"Error in test engine loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(self.interval_seconds)

    async def stop(self):
        """Stop the test engine."""
        self.is_running = False

    def get_latest_results(self, limit: int = 100) -> List[Dict]:
        """
        Get the most recent test results.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent result dictionaries
        """
        if limit >= len(self.results_buffer):
            return list(self.results_buffer)
        else:
            # Get last N results from deque
            return list(self.results_buffer)[-limit:]

    def get_statistics(self) -> Dict:
        """
        Calculate aggregate statistics from the buffer.

        Returns:
            Dictionary with statistics:
                - total_queries: int
                - successful_queries: int
                - failed_queries: int
                - success_rate: float
                - avg_response_time_ms: float
                - stats_by_server: dict
                - stats_by_domain: dict
        """
        if not self.results_buffer:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "success_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "stats_by_server": {},
                "stats_by_domain": {}
            }

        results = list(self.results_buffer)
        total = len(results)
        successful = sum(1 for r in results if r["success"])
        failed = total - successful

        # Calculate average response time (only successful queries)
        response_times = [r["response_time_ms"] for r in results if r["response_time_ms"] is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        # Stats by DNS server
        stats_by_server = {}
        for result in results:
            server_name = result["dns_server"]["name"]
            if server_name not in stats_by_server:
                stats_by_server[server_name] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "response_times": []
                }

            stats_by_server[server_name]["total"] += 1
            if result["success"]:
                stats_by_server[server_name]["successful"] += 1
                if result["response_time_ms"]:
                    stats_by_server[server_name]["response_times"].append(result["response_time_ms"])
            else:
                stats_by_server[server_name]["failed"] += 1

        # Calculate averages for each server
        for server_name, stats in stats_by_server.items():
            if stats["response_times"]:
                stats["avg_response_time_ms"] = round(sum(stats["response_times"]) / len(stats["response_times"]), 2)
            else:
                stats["avg_response_time_ms"] = 0.0
            stats["success_rate"] = round(stats["successful"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0.0
            del stats["response_times"]  # Remove raw data

        # Stats by domain
        stats_by_domain = {}
        for result in results:
            domain = result["domain"]
            if domain not in stats_by_domain:
                stats_by_domain[domain] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0
                }

            stats_by_domain[domain]["total"] += 1
            if result["success"]:
                stats_by_domain[domain]["successful"] += 1
            else:
                stats_by_domain[domain]["failed"] += 1

        # Calculate success rate for each domain
        for domain, stats in stats_by_domain.items():
            stats["success_rate"] = round(stats["successful"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0.0

        return {
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": round(successful / total * 100, 2) if total > 0 else 0.0,
            "avg_response_time_ms": round(avg_response_time, 2),
            "stats_by_server": stats_by_server,
            "stats_by_domain": stats_by_domain,
            "iteration_count": self.iteration_count
        }
