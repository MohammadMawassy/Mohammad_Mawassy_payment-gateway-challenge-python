from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Prometheus is integrated for local metrics collection. A production deployment
# can scrape /metrics and connect Grafana dashboards and alerts to these metrics.

http_requests = Counter(
    "http_requests",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
bank_authorizations = Counter(
    "bank_authorization",
    "Total bank authorization attempts",
    ["bank", "outcome"],
)
bank_authorization_duration = Histogram(
    "bank_authorization_duration_seconds",
    "Bank authorization duration in seconds",
    ["bank"],
)
payments = Counter(
    "payments",
    "Total completed payments",
    ["currency", "status"],
)
bank_routing = Counter(
    "bank_routing",
    "Total payments routed to each bank",
    ["bank"],
)
validation_failures = Counter(
    "validation_failures",
    "Total request validation failures",
    ["path"],
)
idempotency_replays = Counter(
    "idempotency_replays",
    "Total idempotency replays",
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST