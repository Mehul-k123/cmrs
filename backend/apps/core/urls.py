from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, BranchViewSet

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
urlpatterns = router.urls
