from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.middleware import get_request_context


class ContextJWTAuthentication(JWTAuthentication):
    """JWT auth that also tags the request context with the user for logs/audit."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            get_request_context()["user"] = result[0].username
        return result


class ContextJWTScheme(SimpleJWTScheme):
    """Tell drf-spectacular to document our subclass as a bearer JWT scheme."""

    target_class = ContextJWTAuthentication
    name = "jwtAuth"
