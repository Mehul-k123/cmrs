"""Uniform error envelope: {"code": str, "message": str, "details": any}."""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("cmrs.errors")


class BusinessRuleError(exceptions.APIException):
    """A request that is well-formed but violates a business rule."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "business_rule_violation"

    def __init__(self, message: str, code: str | None = None, details=None, status_code: int | None = None):
        super().__init__(detail=message, code=code or self.default_code)
        self.error_code = code or self.default_code
        self.details = details
        if status_code:
            self.status_code = status_code


class ConflictError(BusinessRuleError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, (DjangoPermissionDenied, PermissionError)):
        exc = exceptions.PermissionDenied(str(exc) or None)
    elif isinstance(exc, IntegrityError):
        logger.warning("integrity error: %s", exc)
        return Response(
            {"code": "integrity_error", "message": "This record conflicts with existing data.", "details": None},
            status=status.HTTP_409_CONFLICT,
        )

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("unhandled error", exc_info=exc)
        return Response(
            {"code": "server_error", "message": "Something went wrong. Please try again.", "details": None},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, BusinessRuleError):
        payload = {"code": exc.error_code, "message": str(exc.detail), "details": exc.details}
    elif isinstance(exc, exceptions.ValidationError):
        payload = {"code": "validation_error", "message": "Please correct the highlighted fields.",
                   "details": response.data}
    else:
        detail = response.data.get("detail", "") if isinstance(response.data, dict) else response.data
        code = exc.get_codes() if isinstance(exc, exceptions.APIException) else "error"
        payload = {"code": code if isinstance(code, str) else "error", "message": str(detail), "details": None}
    response.data = payload
    return response
