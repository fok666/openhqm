"""FastAPI application factory."""

from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from openhqm import __version__
from openhqm.api.routes import router
from openhqm.api.models import HealthResponse
from openhqm.api.dependencies import get_queue, get_cache, cleanup_resources
from openhqm.utils.logging import setup_logging
from openhqm.utils.metrics import metrics
from openhqm.config import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging()
    logger.info("Starting OpenHQM API", version=__version__)

    # Initialize queue and cache
    try:
        queue = await get_queue()
        cache = await get_cache()
        logger.info("Resources initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize resources", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down OpenHQM API")
    await cleanup_resources()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="OpenHQM - HTTP Queue Message Handler",
        description="Asynchronous HTTP request processing system using message queues",
        version=__version__,
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(router)

    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check() -> HealthResponse:
        """
        Health check endpoint.

        Returns:
            Health status of the application and components
        """
        components = {"api": "healthy"}

        try:
            queue = await get_queue()
            components["queue"] = "healthy"
        except Exception:
            components["queue"] = "unhealthy"

        try:
            cache = await get_cache()
            components["cache"] = "healthy"
        except Exception:
            components["cache"] = "unhealthy"

        overall_status = "healthy" if all(v == "healthy" for v in components.values()) else "degraded"

        return HealthResponse(
            status=overall_status,
            version=__version__,
            timestamp=datetime.utcnow(),
            components=components,
        )

    # Metrics endpoint
    if settings.monitoring.metrics_enabled:

        @app.get("/metrics", tags=["monitoring"])
        async def metrics_endpoint() -> Response:
            """
            Prometheus metrics endpoint.

            Returns:
                Prometheus metrics in text format
            """
            return Response(
                content=generate_latest(metrics.registry),
                media_type=CONTENT_TYPE_LATEST,
            )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all HTTP requests."""
        log = logger.bind(
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        log.info("Request received")

        # Track in-flight requests
        if settings.monitoring.metrics_enabled:
            metrics.api_requests_in_flight.labels(endpoint=request.url.path).inc()

        try:
            response = await call_next(request)

            log.info("Request completed", status_code=response.status_code)

            # Track request metrics
            if settings.monitoring.metrics_enabled:
                metrics.api_requests_total.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                ).inc()

            return response
        finally:
            if settings.monitoring.metrics_enabled:
                metrics.api_requests_in_flight.labels(endpoint=request.url.path).dec()

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        logger.exception("Unhandled exception occurred", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred"},
        )

    return app
