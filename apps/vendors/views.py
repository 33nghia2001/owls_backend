from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from .models import Vendor, VendorBankAccount, VendorPayout
from .serializers import (
    VendorSerializer, VendorRegistrationSerializer, VendorPublicSerializer,
    VendorBankAccountSerializer, VendorPayoutSerializer
)
from .permissions import IsVendorOwner, IsApprovedVendor


class VendorViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor management."""
    queryset = Vendor.objects.filter(status='approved')
    serializer_class = VendorPublicSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['shop_name', 'description']
    ordering_fields = ['rating', 'total_sales', 'created_at']
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'register':
            return VendorRegistrationSerializer
        if self.action in ['me', 'update', 'partial_update']:
            return VendorSerializer
        return VendorPublicSerializer
    
    def get_permissions(self):
        if self.action in ['register', 'me', 'update', 'partial_update']:
            return [IsAuthenticated()]
        return [AllowAny()]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register as a vendor."""
        # Check if user already has a vendor profile
        if hasattr(request.user, 'vendor_profile'):
            vendor = request.user.vendor_profile
            
            # Allow re-registration if previously rejected
            if vendor.status == 'rejected':
                # Delete old profile and allow fresh registration
                vendor.delete()
            elif vendor.status == 'pending':
                return Response(
                    {'error': 'Đơn đăng ký vendor của bạn đang chờ xét duyệt.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # approved or suspended
                return Response(
                    {'error': 'Bạn đã là vendor.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = VendorRegistrationSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current vendor profile."""
        try:
            vendor = request.user.vendor_profile
        except Vendor.DoesNotExist:
            return Response(
                {'error': 'You are not a vendor.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'GET':
            serializer = VendorSerializer(vendor)
            return Response(serializer.data)
        
        serializer = VendorSerializer(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured vendors."""
        vendors = Vendor.objects.filter(status='approved', is_featured=True)[:10]
        serializer = VendorPublicSerializer(vendors, many=True)
        return Response(serializer.data)


class VendorBankAccountViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor bank accounts."""
    serializer_class = VendorBankAccountSerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def get_queryset(self):
        return VendorBankAccount.objects.filter(vendor=self.request.user.vendor_profile)
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set bank account as primary."""
        account = self.get_object()
        account.is_primary = True
        account.save()
        return Response(VendorBankAccountSerializer(account).data)


class VendorPayoutViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for vendor payouts (read-only)."""
    serializer_class = VendorPayoutSerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def get_queryset(self):
        return VendorPayout.objects.filter(vendor=self.request.user.vendor_profile)
