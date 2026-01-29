import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic_settings import BaseSettings
from .models import AppConfig, DNSServer, TestingConfig, LoggingConfig, WebConfig


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # Config file path
    config_file: str = "config.yaml"

    # Environment variable overrides
    dns_test_interval: Optional[float] = None
    dns_test_timeout: Optional[float] = None
    dns_max_concurrent: Optional[int] = None
    log_enabled: Optional[bool] = None
    log_file_path: Optional[str] = None
    web_host: Optional[str] = None
    web_port: Optional[int] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to config.yaml file. If None, uses default path.

    Returns:
        AppConfig instance with loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    # Load settings (includes env vars)
    settings = Settings()

    # Determine config file path
    if config_path is None:
        config_path = settings.config_file

    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please copy config.yaml.example to config.yaml and edit it."
        )

    # Load YAML file
    with open(config_file, 'r') as f:
        try:
            config_dict = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")

    # Apply environment variable overrides
    if settings.dns_test_interval is not None:
        config_dict.setdefault("testing", {})["interval_seconds"] = settings.dns_test_interval

    if settings.dns_test_timeout is not None:
        config_dict.setdefault("testing", {})["timeout_seconds"] = settings.dns_test_timeout

    if settings.dns_max_concurrent is not None:
        config_dict.setdefault("testing", {})["max_concurrent_queries"] = settings.dns_max_concurrent

    if settings.log_enabled is not None:
        config_dict.setdefault("logging", {})["enabled"] = settings.log_enabled

    if settings.log_file_path is not None:
        config_dict.setdefault("logging", {})["file_path"] = settings.log_file_path

    if settings.web_host is not None:
        config_dict.setdefault("web", {})["host"] = settings.web_host

    if settings.web_port is not None:
        config_dict.setdefault("web", {})["port"] = settings.web_port

    # Validate and create AppConfig
    try:
        app_config = AppConfig(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")

    return app_config


def get_default_config() -> AppConfig:
    """
    Get default configuration (useful for testing or when config file doesn't exist).

    Returns:
        AppConfig with sensible defaults
    """
    return AppConfig(
        dns_servers=[
            DNSServer(name="Google DNS Primary", ip="8.8.8.8", port=53),
            DNSServer(name="Cloudflare DNS", ip="1.1.1.1", port=53),
        ],
        domains=[
            "google.com",
            "github.com",
            "stackoverflow.com",
        ],
        testing=TestingConfig(
            interval_seconds=5.0,
            timeout_seconds=3.0,
            max_concurrent_queries=10
        ),
        logging=LoggingConfig(
            enabled=True,
            file_path="/app/logs/dns_results.jsonl",
            max_file_size_mb=100,
            rotation_count=5
        ),
        web=WebConfig(
            host="0.0.0.0",
            port=8000,
            max_websocket_connections=50,
            history_buffer_size=1000
        )
    )
