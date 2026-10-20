from django.contrib import admin

from .models import Customer, Loan, RepaymentInstallment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_code", "name", "branch", "assigned_agent")
    list_filter = ("branch",)
    search_fields = ("name", "customer_code")


class InstallmentInline(admin.TabularInline):
    model = RepaymentInstallment
    extra = 0
    readonly_fields = ("number", "due_date", "amount_due", "amount_paid", "status")
    can_delete = False


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("loan_number", "customer", "branch", "principal", "status")
    list_filter = ("branch", "status")
    inlines = [InstallmentInline]
