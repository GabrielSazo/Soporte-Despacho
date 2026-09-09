import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_str):
    try:
        token = AccessToken(token_str)
        user_id = token.get("user_id")
        return User.objects.get(id=user_id)
    except (TokenError, User.DoesNotExist, Exception):
        return AnonymousUser()

class TicketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])
        token = token_list[0] if token_list else None
        user = self.scope.get("user")
        if (not user or user.is_anonymous) and token:
            user = await get_user_from_token(token)
        # Allow anon for debug if token fails, but log
        if not user or user.is_anonymous:
            self.user = AnonymousUser()
            self.group_name = "tickets_global"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print("WSCONNECT /ws/tickets/ - anon")
            await self.send(text_data=json.dumps({"type": "connected", "user": "anon"}))
            return
        self.user = user
        self.group_name = "tickets_global"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"WSCONNECT /ws/tickets/ - {user} ({getattr(user, 'id', 'anon')})")
        await self.send(text_data=json.dumps({"type": "connected", "user": str(user)}))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Keepalive ping
        if text_data == "ping":
            await self.send(text_data="pong")

    async def ticket_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
