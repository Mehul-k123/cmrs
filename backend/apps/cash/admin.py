from django.contrib import admin

from .models import CashSubmission, Collection, Discrepancy


class ReadOnlyAdmin(admin.ModelAdmin):
    """Financial records are viewable in admin but only changeable through the API's business rules."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Collection)
class CollectionAdmin(ReadOnlyAdmin):
    list_display = ("receipt_number", "loan", "agent", "amount", "mode", "status", "collected_at")
    list_filter = ("status", "mode", "branch")
    search_fields = ("receipt_number",)


@admin.register(CashSubmission)
class CashSubmissionAdmin(ReadOnlyAdmin):
    list_display = ("submission_number", "agent", "branch", "expected_amount", "received_amount", "status")
    list_filter = ("status", "branch")


@admin.register(Discrepancy)
class DiscrepancyAdmin(ReadOnlyAdmin):
    list_display = ("type", "branch", "difference", "status", "created_at")
    list_filter = ("type", "status", "branch")
