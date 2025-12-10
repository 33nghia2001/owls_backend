from django.contrib import admin
from django.contrib import messages
from .models import Payment, VNPayTransaction, Refund, Discount, DiscountUsage
from .vnpay import process_vnpay_refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'course', 'amount', 'payment_method', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['transaction_id', 'user__username', 'course__title', 'gateway_transaction_id']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at', 'paid_at']
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('transaction_id', 'user', 'course')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'payment_method', 'status')
        }),
        ('Gateway Info', {
            'fields': ('gateway_transaction_id', 'gateway_response')
        }),
        ('Metadata', {
            'fields': ('description', 'ip_address', 'user_agent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at')
        }),
    )


@admin.register(VNPayTransaction)
class VNPayTransactionAdmin(admin.ModelAdmin):
    list_display = ['vnp_TxnRef', 'payment', 'vnp_Amount', 'vnp_ResponseCode', 'vnp_BankCode', 'created_at']
    list_filter = ['vnp_ResponseCode', 'vnp_BankCode', 'created_at']
    search_fields = ['vnp_TxnRef', 'vnp_TransactionNo', 'payment__transaction_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['payment', 'amount', 'status', 'requested_by', 'requested_at', 'processed_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['payment__transaction_id', 'requested_by__username']
    readonly_fields = ['requested_at', 'processed_at']
    
    def save_model(self, request, obj, form, change):
        """
        SECURITY FIX: Automatically trigger VNPay refund API when status changes to approved.
        Prevents 'Zombie Refunds' - refunds marked as completed in DB but money not returned.
        """
        old_status = None
        if change:
            old_obj = Refund.objects.get(pk=obj.pk)
            old_status = old_obj.status
        
        super().save_model(request, obj, form, change)
        
        # Trigger actual refund if status changed to 'approved'
        if change and old_status != 'approved' and obj.status == 'approved':
            if obj.payment.payment_method == 'vnpay':
                try:
                    # Call VNPay refund API (implement this function in vnpay.py)
                    result = process_vnpay_refund(obj.payment.transaction_id, obj.amount)
                    if result.get('success'):
                        obj.gateway_response = result
                        obj.status = 'completed'
                        obj.save(update_fields=['gateway_response', 'status'])
                        messages.success(request, f'VNPay refund processed successfully: {result.get("message")}')
                    else:
                        obj.status = 'failed'
                        obj.gateway_response = result
                        obj.save(update_fields=['gateway_response', 'status'])
                        messages.error(request, f'VNPay refund failed: {result.get("error")}')
                except Exception as e:
                    messages.error(request, f'Error processing VNPay refund: {str(e)}')
            else:
                messages.warning(request, f'Manual refund required for payment method: {obj.payment.payment_method}')


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'current_uses', 'max_uses', 'is_active', 'valid_from', 'valid_until']
    list_filter = ['discount_type', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['code', 'description']
    filter_horizontal = ['courses']


@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):
    list_display = ['discount', 'user', 'payment', 'amount_saved', 'used_at']
    list_filter = ['used_at']
    search_fields = ['discount__code', 'user__username', 'payment__transaction_id']
    readonly_fields = ['used_at']
