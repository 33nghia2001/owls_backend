from rest_framework import serializers
from .models import Vendor, VendorBankAccount, VendorPayout
from apps.users.serializers import UserSerializer


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for vendor details."""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'user', 'shop_name', 'slug', 'description', 'logo', 'banner',
            'business_email', 'business_phone', 'address', 'city', 'state',
            'country', 'postal_code', 'status', 'is_featured', 'rating',
            'total_sales', 'total_products', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'status', 'rating', 'total_sales', 'total_products']


class VendorRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for vendor registration."""
    
    class Meta:
        model = Vendor
        fields = [
            'shop_name', 'description', 'logo', 'banner', 'business_email',
            'business_phone', 'business_name', 'tax_id', 'business_license',
            'address', 'city', 'state', 'country', 'postal_code'
        ]
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        
        # NOTE: Do NOT change user.role here!
        # Role should only be changed to 'vendor' when admin approves the vendor.
        # This prevents unauthorized access to vendor-only features before approval.
        # The role change is handled in VendorAdmin.approve_vendors action.
        
        return super().create(validated_data)


class VendorPublicSerializer(serializers.ModelSerializer):
    """Public serializer for vendor (limited info)."""
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'shop_name', 'slug', 'description', 'logo', 'banner',
            'city', 'rating', 'total_sales', 'total_products', 'is_featured'
        ]


class VendorBankAccountSerializer(serializers.ModelSerializer):
    """Serializer for vendor bank accounts."""
    
    class Meta:
        model = VendorBankAccount
        fields = [
            'id', 'bank_name', 'account_name', 'account_number',
            'branch_name', 'swift_code', 'is_primary', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def create(self, validated_data):
        vendor = self.context['request'].user.vendor_profile
        validated_data['vendor'] = vendor
        return super().create(validated_data)


class VendorPayoutSerializer(serializers.ModelSerializer):
    """Serializer for vendor payouts."""
    bank_account = VendorBankAccountSerializer(read_only=True)
    
    class Meta:
        model = VendorPayout
        fields = [
            'id', 'bank_account', 'amount', 'fee', 'net_amount',
            'status', 'reference_id', 'notes', 'created_at', 'processed_at'
        ]
        read_only_fields = ['id', 'fee', 'net_amount', 'status', 'reference_id', 'processed_at']
