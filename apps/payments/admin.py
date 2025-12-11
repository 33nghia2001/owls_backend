from django.contrib import admin
from .models import Payment, PaymentLog


class PaymentLogInline(admin.TabularInline):
    model = PaymentLog
    extra = 0
    readonly_fields = ('action', 'is_success', 'error_message', 'created_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'user', 'method', 'status', 'amount', 'created_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('order__order_number', 'user__email', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    inlines = [PaymentLogInline]


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ('payment', 'action', 'is_success', 'created_at')
    list_filter = ('action', 'is_success', 'created_at')
    search_fields = ('payment__order__order_number',)
    readonly_fields = ('created_at',)
