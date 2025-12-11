from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from .models import ProductView, SearchQuery, VendorStats, PlatformStats
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from apps.vendors.permissions import IsApprovedVendor


class VendorStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorStats
        fields = [
            'date', 'orders_count', 'orders_revenue',
            'products_sold', 'product_views', 'new_reviews', 'messages_received'
        ]


class VendorAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for vendor analytics."""
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def list(self, request):
        """Get vendor dashboard stats."""
        vendor = request.user.vendor_profile
        today = timezone.now().date()
        
        # Get order stats
        order_items = OrderItem.objects.filter(vendor=vendor)
        
        # Today's stats
        today_orders = order_items.filter(created_at__date=today)
        
        # This month's stats
        month_start = today.replace(day=1)
        month_orders = order_items.filter(created_at__date__gte=month_start)
        
        return Response({
            'today': {
                'orders': today_orders.values('order').distinct().count(),
                'revenue': sum(item.total_price.amount for item in today_orders),
                'products_sold': today_orders.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            },
            'this_month': {
                'orders': month_orders.values('order').distinct().count(),
                'revenue': sum(item.total_price.amount for item in month_orders),
                'products_sold': month_orders.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            },
            'total': {
                'products': Product.objects.filter(vendor=vendor).count(),
                'total_sales': vendor.total_sales,
                'rating': vendor.rating,
            }
        })
    
    @action(detail=False, methods=['get'])
    def orders_chart(self, request):
        """Get orders chart data for last 30 days."""
        vendor = request.user.vendor_profile
        days = int(request.query_params.get('days', 30))
        
        start_date = timezone.now().date() - timedelta(days=days)
        
        order_items = OrderItem.objects.filter(
            vendor=vendor,
            created_at__date__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('order', distinct=True),
            revenue=Sum('total_price')
        ).order_by('date')
        
        return Response(list(order_items))
    
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """Get top selling products."""
        vendor = request.user.vendor_profile
        
        top_products = OrderItem.objects.filter(
            vendor=vendor
        ).values(
            'product__id', 'product__name'
        ).annotate(
            total_sold=Sum('quantity'),
            revenue=Sum('total_price')
        ).order_by('-total_sold')[:10]
        
        return Response(list(top_products))


class AdminAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for admin analytics."""
    permission_classes = [IsAdminUser]
    
    def list(self, request):
        """Get platform dashboard stats."""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        from apps.users.models import Users
        from apps.vendors.models import Vendor
        
        return Response({
            'users': {
                'total': Users.objects.count(),
                'this_month': Users.objects.filter(date_joined__date__gte=month_start).count(),
            },
            'vendors': {
                'total': Vendor.objects.filter(status='approved').count(),
                'pending': Vendor.objects.filter(status='pending').count(),
            },
            'orders': {
                'total': Order.objects.count(),
                'this_month': Order.objects.filter(created_at__date__gte=month_start).count(),
            },
            'products': {
                'total': Product.objects.count(),
                'published': Product.objects.filter(status='published').count(),
            }
        })
    
    @action(detail=False, methods=['get'])
    def revenue_chart(self, request):
        """Get revenue chart data."""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)
        
        revenue_data = Order.objects.filter(
            created_at__date__gte=start_date,
            payment_status='paid'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id'),
            revenue=Sum('total')
        ).order_by('date')
        
        return Response(list(revenue_data))
