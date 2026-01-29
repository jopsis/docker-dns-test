import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .config import load_config, get_default_config
from .core.test_engine import TestEngine
from .core.logger import JSONLLogger
from .api import routes, websocket


# Global variables for test engine and logger
test_engine: TestEngine = None
logger: JSONLLogger = None
app_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    global test_engine, logger, app_config

    # Startup
    print("Starting DNS Test System...")

    try:
        # Load configuration
        try:
            app_config = load_config()
            print(f"Configuration loaded from config.yaml")
        except FileNotFoundError:
            print("Warning: config.yaml not found, using default configuration")
            app_config = get_default_config()

        # Initialize logger
        logger = JSONLLogger(
            file_path=app_config.logging.file_path,
            max_file_size_mb=app_config.logging.max_file_size_mb,
            rotation_count=app_config.logging.rotation_count,
            enabled=app_config.logging.enabled
        )
        print(f"Logger initialized: {app_config.logging.file_path}")

        # Initialize test engine
        test_engine = TestEngine(
            domains=app_config.domains,
            dns_servers=[server.model_dump() for server in app_config.dns_servers],
            interval_seconds=app_config.testing.interval_seconds,
            timeout_seconds=app_config.testing.timeout_seconds,
            max_concurrent_queries=app_config.testing.max_concurrent_queries,
            history_buffer_size=app_config.web.history_buffer_size
        )

        # Set callbacks
        test_engine.set_result_callback(websocket.ws_manager.broadcast)
        test_engine.set_logger_callback(logger.log)

        # Start test engine in background
        asyncio.create_task(test_engine.run())
        print(f"Test engine started: testing {len(app_config.domains)} domains against {len(app_config.dns_servers)} DNS servers")
        print(f"Interval: {app_config.testing.interval_seconds}s, Timeout: {app_config.testing.timeout_seconds}s")

        yield

    except Exception as e:
        print(f"Error during startup: {e}")
        raise

    # Shutdown
    print("Shutting down DNS Test System...")
    if test_engine:
        await test_engine.stop()
    print("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="DNS Test System",
    description="Continuous DNS testing with real-time WebSocket updates",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(routes.router)
app.include_router(websocket.router)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    else:
        return JSONResponse(
            content={
                "message": "DNS Test System API",
                "docs": "/docs",
                "websocket": "/ws",
                "status": "/api/status"
            }
        )


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {
        "status": "healthy",
        "engine_running": test_engine.is_running if test_engine else False
    }


# Make test_engine and logger accessible to other modules
def get_test_engine() -> TestEngine:
    """Get the global test engine instance."""
    return test_engine


def get_logger() -> JSONLLogger:
    """Get the global logger instance."""
    return logger


def get_config():
    """Get the global configuration."""
    return app_config
