"""
Celery tasks for vendor management.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .models import VendorBalance, VendorPayout

logger = logging.getLogger(__name__)


@shared_task
def release_held_vendor_balances():
    """
    Release vendor balances that have passed their hold period.
    
    This task should run daily to automatically change status from HELD to AVAILABLE
    for balances where available_at <= now.
    
    Hold period protects against refund requests after vendor payout.
    """
    now = timezone.now()
    
    # Find all held balances that should be released
    held_balances = VendorBalance.objects.filter(
        status=VendorBalance.Status.HELD,
        available_at__lte=now
    ).select_related('vendor', 'order_item')
    
    released_count = 0
    
    for balance in held_balances:
        try:
            with transaction.atomic():
                # Lock the balance record
                locked_balance = VendorBalance.objects.select_for_update().get(pk=balance.pk)
                
                # Double-check status (may have changed)
                if locked_balance.status != VendorBalance.Status.HELD:
                    continue
                
                # Release the balance
                locked_balance.status = VendorBalance.Status.AVAILABLE
                locked_balance.released_at = now
                locked_balance.save()
                
                released_count += 1
                logger.info(
                    f"Released vendor balance {balance.pk} for vendor {balance.vendor.shop_name}: "
                    f"{balance.net_amount}"
                )
                
        except Exception as e:
            logger.error(f"Failed to release vendor balance {balance.pk}: {str(e)}")
    
    return f"Released {released_count} vendor balances"


@shared_task
def calculate_vendor_available_balance(vendor_id):
    """
    Calculate total available balance for a vendor.
    
    Returns the sum of all AVAILABLE (not yet paid out) balances.
    """
    from decimal import Decimal
    
    available_total = VendorBalance.objects.filter(
        vendor_id=vendor_id,
        status=VendorBalance.Status.AVAILABLE
    ).aggregate(
        total=models.Sum('net_amount')
    )['total'] or Decimal('0.00')
    
    return str(available_total)


@shared_task
def process_vendor_payout(payout_id):
    """
    Process a vendor payout request.
    
    This task handles the actual payout processing:
    1. Validates payout amount against available balance
    2. Links balance entries to the payout
    3. Updates payout status
    """
    from django.db.models import Sum
    from decimal import Decimal
    
    try:
        with transaction.atomic():
            payout = VendorPayout.objects.select_for_update().get(pk=payout_id)
            
            if payout.status != VendorPayout.Status.PENDING:
                logger.warning(f"Payout {payout_id} is not pending, skipping")
                return f"Payout {payout_id} already processed"
            
            # Get available balance entries for this vendor
            available_balances = VendorBalance.objects.filter(
                vendor=payout.vendor,
                status=VendorBalance.Status.AVAILABLE
            ).select_for_update().order_by('created_at')
            
            # Calculate total available
            total_available = available_balances.aggregate(
                total=Sum('net_amount')
            )['total'] or Decimal('0.00')
            
            if total_available < payout.amount:
                payout.status = VendorPayout.Status.FAILED
                payout.notes = f"Insufficient balance. Available: {total_available}, Requested: {payout.amount}"
                payout.save()
                return f"Payout {payout_id} failed: insufficient balance"
            
            # Mark balance entries as paid out
            remaining_amount = payout.amount
            for balance in available_balances:
                if remaining_amount <= 0:
                    break
                
                balance.status = VendorBalance.Status.PAID_OUT
                balance.payout = payout
                balance.save()
                remaining_amount -= balance.net_amount
            
            # Update payout status
            payout.status = VendorPayout.Status.PROCESSING
            payout.save()
            
            logger.info(f"Payout {payout_id} processing for vendor {payout.vendor.shop_name}")
            return f"Payout {payout_id} is now processing"
            
    except VendorPayout.DoesNotExist:
        logger.error(f"Payout {payout_id} not found")
        return f"Payout {payout_id} not found"
    except Exception as e:
        logger.error(f"Failed to process payout {payout_id}: {str(e)}")
        raise
