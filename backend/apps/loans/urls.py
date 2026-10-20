from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, LoanViewSet

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("loans", LoanViewSet, basename="loan")
urlpatterns = router.urls
