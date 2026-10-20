from rest_framework.routers import DefaultRouter

from .views import CollectionViewSet, DiscrepancyViewSet, SubmissionViewSet

router = DefaultRouter()
router.register("collections", CollectionViewSet, basename="collection")
router.register("submissions", SubmissionViewSet, basename="submission")
router.register("discrepancies", DiscrepancyViewSet, basename="discrepancy")
urlpatterns = router.urls
