"""
WebSocket consumers for real-time messaging.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat functionality.
    
    URL: ws://domain/ws/chat/<conversation_id>/
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope['user']
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Verify user is part of this conversation
        if not await self.user_in_conversation():
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"User {self.user.email} connected to conversation {self.conversation_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"User {self.user.email} disconnected from conversation {self.conversation_id}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')
            
            if message_type == 'message':
                content = data.get('content', '').strip()
                if not content:
                    return
                
                # Save message to database
                message = await self.save_message(content)
                
                # Broadcast message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': str(message['id']),
                            'content': message['content'],
                            'sender_id': str(message['sender_id']),
                            'sender_name': message['sender_name'],
                            'created_at': message['created_at'],
                        }
                    }
                )
            
            elif message_type == 'typing':
                # Broadcast typing indicator
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': str(self.user.id),
                        'user_name': self.user.get_full_name() or self.user.email,
                        'is_typing': data.get('is_typing', False)
                    }
                )
            
            elif message_type == 'read':
                # Mark messages as read
                await self.mark_messages_read()
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'messages_read',
                        'user_id': str(self.user.id),
                    }
                )
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
    
    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send to the user who is typing
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def messages_read(self, event):
        """Send read receipt to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id']
        }))
    
    @database_sync_to_async
    def user_in_conversation(self):
        """Check if user is a participant in the conversation."""
        from .models import Conversation
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            # User is either the customer or the vendor owner
            return (
                conversation.customer_id == self.user.id or 
                conversation.vendor.user_id == self.user.id
            )
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, content):
        """Save message to database."""
        from .models import Conversation, Message
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content
        )
        
        # Update conversation timestamp
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])
        
        return {
            'id': message.id,
            'content': message.content,
            'sender_id': message.sender_id,
            'sender_name': self.user.get_full_name() or self.user.email,
            'created_at': message.created_at.isoformat()
        }
    
    @database_sync_to_async
    def mark_messages_read(self):
        """Mark all unread messages as read."""
        from .models import Message
        
        Message.objects.filter(
            conversation_id=self.conversation_id,
            is_read=False
        ).exclude(
            sender=self.user
        ).update(
            is_read=True,
            read_at=timezone.now()
        )


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    URL: ws://domain/ws/notifications/
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Each user has their own notification channel
        self.room_group_name = f'notifications_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send unread notification count on connect
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': count
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming messages (e.g., mark as read)."""
        try:
            data = json.loads(text_data)
            
            if data.get('type') == 'mark_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
                    count = await self.get_unread_count()
                    await self.send(text_data=json.dumps({
                        'type': 'unread_count',
                        'count': count
                    }))
                    
        except json.JSONDecodeError:
            pass
    
    async def notification_message(self, event):
        """Send notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications."""
        from apps.notifications.models import Notification
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read."""
        from apps.notifications.models import Notification
        Notification.objects.filter(
            id=notification_id,
            user=self.user
        ).update(is_read=True, read_at=timezone.now())
