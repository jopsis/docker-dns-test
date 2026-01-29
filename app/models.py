from typing import List, Optional
from pydantic import BaseModel, Field


class DNSServer(BaseModel):
    """DNS server configuration."""
    name: str = Field(..., description="Human-readable name for the DNS server")
    ip: str = Field(..., description="IP address of the DNS server")
    port: int = Field(default=53, description="Port number (default: 53)")


class TestingConfig(BaseModel):
    """Testing parameters configuration."""
    interval_seconds: float = Field(default=5.0, ge=1.0, description="Interval between test iterations")
    timeout_seconds: float = Field(default=3.0, ge=0.5, description="Timeout for each DNS query")
    max_concurrent_queries: int = Field(default=10, ge=1, description="Maximum concurrent queries")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    enabled: bool = Field(default=True, description="Enable/disable logging")
    file_path: str = Field(default="/app/logs/dns_results.jsonl", description="Path to log file")
    max_file_size_mb: int = Field(default=100, ge=1, description="Maximum log file size in MB")
    rotation_count: int = Field(default=5, ge=1, description="Number of rotated log files to keep")


class WebConfig(BaseModel):
    """Web server configuration."""
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, ge=1, le=65535, description="Port to listen on")
    max_websocket_connections: int = Field(default=50, ge=1, description="Maximum WebSocket connections")
    history_buffer_size: int = Field(default=1000, ge=100, description="Size of result history buffer")


class AppConfig(BaseModel):
    """Complete application configuration."""
    dns_servers: List[DNSServer] = Field(..., description="List of DNS servers to test")
    domains: List[str] = Field(..., description="List of domains to resolve")
    testing: TestingConfig = Field(default_factory=TestingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    web: WebConfig = Field(default_factory=WebConfig)
