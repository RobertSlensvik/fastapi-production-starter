"""Prometheus metrics: request counters, latency histograms, /metrics endpoint.

Metrics exposed:
- `http_requests_total{method,path,status}` — request counts
- `http_request_duration_seconds{method,path}` — latency histogram
- Default Python process metrics (memory, GC, threads)
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Use a dedicated registry to avoid clashing with libraries that mutate the
# default global registry.
_registry = CollectorRegistry()

_requests = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status"),
    registry=_registry,
)

_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    labelnames=("method", "path"),
    registry=_registry,
    # Buckets tuned for typical API latencies (1ms to 10s).
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record per-request counters and latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start
            # Use route path (templated) rather than raw path to avoid label
            # explosion on URLs containing user ids.
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            _requests.labels(request.method, path, str(status)).inc()
            _duration.labels(request.method, path).observe(duration)

        return response


def setup_metrics(app: FastAPI) -> None:
    """Register middleware + /metrics endpoint on the app."""
    app.add_middleware(MetricsMiddleware)

    settings = app.state.settings
    path = settings.metrics_path

    @app.get(path, include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(_registry), media_type=CONTENT_TYPE_LATEST)
