"""Per-request context (request id, user, ip) for structured logs and the audit trail."""

import contextvars
import logging
import uuid

_request_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("request_ctx", default=None)


def get_request_context() -> dict:
    return _request_ctx.get() or {}


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
        token = _request_ctx.set({"request_id": request_id, "ip": ip})
        try:
            response = self.get_response(request)
        finally:
            _request_ctx.reset(token)
        response["X-Request-ID"] = request_id
        return response


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        ctx = get_request_context()
        record.request_id = ctx.get("request_id", "-")
        record.user = ctx.get("user", "-")
        return True
