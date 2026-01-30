from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/status")
async def get_status():
    """
    Get current system status and statistics.

    Returns:
        Dictionary with:
        - engine_running: bool
        - iteration_count: int
        - active_websocket_connections: int
        - statistics: aggregated test statistics
        - log_info: logging file information
    """
    from ..main import get_test_engine, get_logger, get_config

    engine = get_test_engine()
    logger = get_logger()
    config = get_config()

    if not engine:
        raise HTTPException(status_code=503, detail="Test engine not initialized")

    statistics = engine.get_statistics()
    global_statistics = engine.get_global_statistics()

    from .websocket import ws_manager

    return {
        "engine_running": engine.is_running,
        "iteration_count": engine.iteration_count,
        "active_websocket_connections": ws_manager.get_connection_count(),
        "statistics": statistics,
        "global_statistics": global_statistics,
        "log_info": logger.get_file_info() if logger else None,
        "config_loaded": config is not None
    }


@router.get("/config")
async def get_config_endpoint():
    """
    Get current configuration.

    Returns:
        Dictionary with current configuration settings
    """
    from ..main import get_config

    config = get_config()

    if not config:
        raise HTTPException(status_code=503, detail="Configuration not loaded")

    return {
        "domains": config.domains,
        "dns_servers": [server.model_dump() for server in config.dns_servers],
        "testing": {
            "interval_seconds": config.testing.interval_seconds,
            "timeout_seconds": config.testing.timeout_seconds,
            "max_concurrent_queries": config.testing.max_concurrent_queries
        },
        "logging": {
            "enabled": config.logging.enabled,
            "file_path": config.logging.file_path,
            "max_file_size_mb": config.logging.max_file_size_mb,
            "rotation_count": config.logging.rotation_count
        },
        "web": {
            "host": config.web.host,
            "port": config.web.port,
            "max_websocket_connections": config.web.max_websocket_connections,
            "history_buffer_size": config.web.history_buffer_size
        }
    }


@router.get("/results")
async def get_results(limit: int = 100):
    """
    Get recent test results.

    Args:
        limit: Maximum number of results to return (default: 100)

    Returns:
        List of recent test result dictionaries
    """
    from ..main import get_test_engine

    engine = get_test_engine()

    if not engine:
        raise HTTPException(status_code=503, detail="Test engine not initialized")

    if limit < 1 or limit > 10000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 10000")

    results = engine.get_latest_results(limit=limit)

    return {
        "count": len(results),
        "limit": limit,
        "results": results
    }


@router.get("/logs")
async def get_logs(lines: int = 100):
    """
    Get recent log entries from JSONL file.

    Args:
        lines: Number of recent lines to return (default: 100)

    Returns:
        List of recent log entries
    """
    from ..main import get_logger

    logger = get_logger()

    if not logger or not logger.enabled:
        raise HTTPException(status_code=404, detail="Logging is not enabled")

    if lines < 1 or lines > 10000:
        raise HTTPException(status_code=400, detail="Lines must be between 1 and 10000")

    logs = await logger.read_recent(lines=lines)

    return {
        "count": len(logs),
        "lines": lines,
        "entries": logs
    }
