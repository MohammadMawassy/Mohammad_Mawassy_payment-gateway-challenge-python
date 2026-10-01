import logging
import time
from uuid import uuid4

from fastapi import Request, Response

from payment_gateway_api.metrics import http_request_duration, http_requests
from payment_gateway_api.observability import request_id_context

logger = logging.getLogger(__name__)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


async def request_logging_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    token = request_id_context.set(request_id)
    started = time.perf_counter()

    try:
        logger.info("http_request_started method=%s path=%s", request.method, request.url.path)
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        path = _route_label(request)
        http_requests.labels(request.method, path, str(response.status_code)).inc()
        http_request_duration.labels(request.method, path).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request_completed method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        path = _route_label(request)
        http_requests.labels(request.method, path, "500").inc()
        http_request_duration.labels(request.method, path).observe(time.perf_counter() - started)
        logger.exception(
            "http_request_failed method=%s path=%s duration_ms=%s",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    finally:
        request_id_context.reset(token)
