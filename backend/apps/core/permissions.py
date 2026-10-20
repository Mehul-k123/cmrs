from rest_framework.permissions import SAFE_METHODS, BasePermission


class Role:
    ADMIN = "ADMIN"
    FINANCE = "FINANCE"
    BRANCH_MANAGER = "BRANCH_MANAGER"
    AGENT = "AGENT"

    CHOICES = [
        (ADMIN, "Admin"),
        (FINANCE, "Finance"),
        (BRANCH_MANAGER, "Branch Manager"),
        (AGENT, "Collection Agent"),
    ]
    ORG_WIDE = {ADMIN, FINANCE}


def has_role(*roles: str) -> type[BasePermission]:
    """Permission class factory: allow only authenticated users whose role is in `roles`."""

    class _HasRole(BasePermission):
        message = "Your role is not allowed to perform this action."

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in roles)

    _HasRole.__name__ = f"HasRole_{'_'.join(roles)}"
    return _HasRole


class ReadOnlyOrRoles(BasePermission):
    """Any authenticated user may read; writes require one of `write_roles` declared on the view."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in getattr(view, "write_roles", ())


def scope_queryset(qs, user, *, branch_field: str = "branch", agent_field: str | None = None):
    """Row-level scoping: org-wide roles see all, branch managers their branch, agents their own rows."""
    role = getattr(user, "role", None)  # AnonymousUser (e.g. schema generation) sees nothing
    if role in Role.ORG_WIDE:
        return qs
    if role == Role.BRANCH_MANAGER:
        return qs.filter(**{branch_field: user.branch_id}) if user.branch_id else qs.none()
    if role == Role.AGENT and agent_field:
        return qs.filter(**{agent_field: user.id})
    return qs.none()
