from rest_framework.routers import DefaultRouter

from .views import DepositViewSet

router = DefaultRouter()
router.register("deposits", DepositViewSet, basename="deposit")
urlpatterns = router.urls
