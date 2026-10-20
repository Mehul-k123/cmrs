from django.contrib import admin

from apps.cash.admin import ReadOnlyAdmin

from .models import PaymentIntent, WebhookEvent


@admin.register(PaymentIntent)
class PaymentIntentAdmin(ReadOnlyAdmin):
    list_display = ("intent_number", "loan", "amount", "status", "created_at")


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdmin):
    list_display = ("event_id", "event_type", "received_at")
