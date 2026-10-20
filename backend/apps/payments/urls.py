from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PaymentIntentViewSet, WebhookView

router = DefaultRouter()
router.register("payments/intents", PaymentIntentViewSet, basename="payment-intent")
urlpatterns = [path("payments/webhook/", WebhookView.as_view(), name="payment-webhook"), *router.urls]
