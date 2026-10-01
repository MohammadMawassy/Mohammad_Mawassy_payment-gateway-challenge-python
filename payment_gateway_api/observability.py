from contextvars import ContextVar
import logging

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
payment_id_context: ContextVar[str] = ContextVar("payment_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        record.payment_id = payment_id_context.get()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "request_id=%(request_id)s payment_id=%(payment_id)s %(message)s"
        )
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
