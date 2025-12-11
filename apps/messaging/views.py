from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from .models import Conversation, Message
from .middleware import create_ws_ticket
from apps.vendors.models import Vendor
from backend.validators import validate_attachment_upload


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'is_mine', 'content', 'attachment', 'is_read', 'created_at']
    
    def get_sender_name(self, obj):
        return obj.sender.full_name or obj.sender.email
    
    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request:
            return obj.sender == request.user
        return False


class ConversationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.shop_name', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'customer', 'customer_name', 'vendor', 'vendor_name',
            'order', 'product', 'last_message', 'unread_count',
            'is_archived', 'created_at', 'updated_at'
        ]
    
    def get_last_message(self, obj):
        last = obj.messages.last()
        if last:
            return MessageSerializer(last, context=self.context).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet for conversations."""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Customer sees their conversations, vendor sees their shop's conversations
        if hasattr(user, 'vendor_profile'):
            return Conversation.objects.filter(
                Q(customer=user) | Q(vendor=user.vendor_profile)
            )
        return Conversation.objects.filter(customer=user)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=False, methods=['post'])
    def start(self, request):
        """Start a new conversation with a vendor."""
        vendor_id = request.data.get('vendor_id')
        product_id = request.data.get('product_id')
        order_id = request.data.get('order_id')
        message = request.data.get('message')
        
        if not vendor_id:
            return Response(
                {'error': 'Vendor ID required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        vendor = get_object_or_404(Vendor, id=vendor_id)
        
        # Check if conversation exists
        conversation = Conversation.objects.filter(
            customer=request.user,
            vendor=vendor,
            is_archived=False
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                customer=request.user,
                vendor=vendor,
                product_id=product_id,
                order_id=order_id
            )
        
        # Create first message if provided
        if message:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=message
            )
        
        return Response(
            ConversationSerializer(conversation, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages in a conversation."""
        conversation = self.get_object()
        messages = conversation.messages.all()
        
        # Mark messages as read
        messages.filter(is_read=False).exclude(sender=request.user).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send a message in a conversation."""
        conversation = self.get_object()
        content = request.data.get('content')
        attachment = request.FILES.get('attachment')
        
        if not content and not attachment:
            return Response(
                {'error': 'Message content or attachment required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate attachment if provided
        if attachment:
            try:
                validate_attachment_upload(attachment)
            except serializers.ValidationError as e:
                return Response(
                    {'error': str(e.detail[0]) if hasattr(e, 'detail') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content or '',
            attachment=attachment
        )
        
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a conversation."""
        conversation = self.get_object()
        conversation.is_archived = True
        conversation.save()
        return Response({'message': 'Conversation archived.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_ws_ticket(request):
    """
    Get a one-time ticket for WebSocket authentication.
    
    This is more secure than passing JWT token in the URL because:
    1. Ticket is one-time use (deleted after first connection)
    2. Ticket expires after 60 seconds
    3. Ticket is not a valid auth token for other API endpoints
    
    Usage:
    1. POST /api/messaging/ws-ticket/
    2. Use ticket in WebSocket URL: ws://domain/ws/chat/123/?ticket=<ticket>
    """
    ticket = create_ws_ticket(request.user.id)
    return Response({
        'ticket': ticket,
        'expires_in': 60  # seconds
    })