import asyncio
import time
from typing import Dict, List, Optional
from dns import asyncresolver, exception as dns_exception


class AsyncDNSResolver:
    """Async DNS resolver with timeout and concurrency control."""

    def __init__(self, timeout: float = 3.0, max_concurrent: int = 10):
        """
        Initialize the DNS resolver.

        Args:
            timeout: Query timeout in seconds
            max_concurrent: Maximum concurrent queries
        """
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.resolver = asyncresolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = timeout

    async def resolve_single(
        self,
        domain: str,
        dns_server_ip: str,
        dns_server_name: str,
        dns_server_port: int = 53
    ) -> Dict:
        """
        Resolve a single domain using a specific DNS server.

        Args:
            domain: Domain name to resolve
            dns_server_ip: DNS server IP address
            dns_server_name: DNS server name for identification
            dns_server_port: DNS server port (default 53)

        Returns:
            Dictionary with resolution results:
                - domain: str
                - dns_server: dict
                - success: bool
                - response_time_ms: float or None
                - resolved_ips: list of str
                - error: str or None
        """
        result = {
            "domain": domain,
            "dns_server": {
                "name": dns_server_name,
                "ip": dns_server_ip,
                "port": dns_server_port
            },
            "success": False,
            "response_time_ms": None,
            "resolved_ips": [],
            "error": None
        }

        async with self.semaphore:
            try:
                # Create a resolver instance for this specific DNS server
                resolver = asyncresolver.Resolver()
                resolver.nameservers = [dns_server_ip]
                resolver.port = dns_server_port
                resolver.timeout = self.timeout
                resolver.lifetime = self.timeout

                # Measure query time
                start_time = time.perf_counter()

                # Perform the DNS query with timeout
                try:
                    answer = await asyncio.wait_for(
                        resolver.resolve(domain, 'A'),
                        timeout=self.timeout
                    )

                    end_time = time.perf_counter()
                    response_time = (end_time - start_time) * 1000  # Convert to ms

                    # Extract IP addresses
                    ips = [str(rdata) for rdata in answer]

                    result.update({
                        "success": True,
                        "response_time_ms": round(response_time, 2),
                        "resolved_ips": ips
                    })

                except asyncio.TimeoutError:
                    result["error"] = "TIMEOUT"

            except dns_exception.NXDOMAIN:
                result["error"] = "NXDOMAIN"
            except dns_exception.NoAnswer:
                result["error"] = "NOANSWER"
            except dns_exception.NoNameservers:
                result["error"] = "NO_NAMESERVERS"
            except Exception as e:
                result["error"] = f"ERROR: {type(e).__name__}"

        return result

    async def resolve_batch(
        self,
        domains: List[str],
        dns_servers: List[Dict]
    ) -> List[Dict]:
        """
        Resolve multiple domains against multiple DNS servers.

        Args:
            domains: List of domain names
            dns_servers: List of DNS server dicts with 'name', 'ip', and optionally 'port'

        Returns:
            List of result dictionaries from resolve_single()
        """
        tasks = []

        for domain in domains:
            for dns_server in dns_servers:
                task = self.resolve_single(
                    domain=domain,
                    dns_server_ip=dns_server["ip"],
                    dns_server_name=dns_server["name"],
                    dns_server_port=dns_server.get("port", 53)
                )
                tasks.append(task)

        # Execute all queries concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return results
