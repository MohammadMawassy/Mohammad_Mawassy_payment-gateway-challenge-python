from fastapi import FastAPI, HTTPException, Response, status

from payment_gateway_api.api.errors import register_exception_handlers
from payment_gateway_api.api.middleware import request_logging_middleware
from payment_gateway_api.api.payments import router as payments_router
from payment_gateway_api.dependencies import get_bank_router
from payment_gateway_api.metrics import metrics_payload
from payment_gateway_api.observability import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI()
    app.middleware("http")(request_logging_middleware)
    app.include_router(payments_router)
    register_exception_handlers(app)

    @app.get("/")
    async def ping() -> dict[str, str]:
        return {"app": "payment-gateway-api"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        try:
            get_bank_router()
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        content, media_type = metrics_payload()
        return Response(content=content, media_type=media_type)

    return app


app = create_app()
