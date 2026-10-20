from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import Role, has_role, scope_queryset

from .models import User
from .serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "login"


class LogoutView(APIView):
    """Blacklists the refresh token. Possession of the refresh token is the credential here."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request={"application/json": {"type": "object", "properties": {"refresh": {"type": "string"}}}},
                   responses={205: None})
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """Admins manage users; managers/finance can list users (e.g. agents) within their scope."""

    serializer_class = UserSerializer
    filterset_fields = ["role", "branch", "is_active"]
    search_fields = ["username", "first_name", "last_name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [has_role(Role.ADMIN)()]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.select_related("branch")
        if getattr(user, "role", None) == Role.AGENT:
            return qs.filter(pk=user.pk)
        return scope_queryset(qs, user)
