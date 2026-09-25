import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()

ONLINE_COUNTS = {}


def online_user_ids():
    return sorted(uid for uid, n in ONLINE_COUNTS.items() if n > 0)


async def broadcast_presence(channel_layer, group_name="tickets_global"):
    await channel_layer.group_send(
        group_name,
        {"type": "presence", "data": {"type": "presence", "user_ids": online_user_ids()}},
    )

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
        ONLINE_COUNTS[user.id] = ONLINE_COUNTS.get(user.id, 0) + 1
        await self.send(text_data=json.dumps({"type": "connected", "user": str(user)}))
        await broadcast_presence(self.channel_layer, self.group_name)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        user = getattr(self, "user", None)
        if user and not getattr(user, "is_anonymous", True):
            left = ONLINE_COUNTS.get(user.id, 1) - 1
            if left <= 0:
                ONLINE_COUNTS.pop(user.id, None)
            else:
                ONLINE_COUNTS[user.id] = left
            try:
                await broadcast_presence(self.channel_layer, getattr(self, "group_name", "tickets_global"))
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data == "ping":
            await self.send(text_data="pong")

    async def ticket_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def presence(self, event):
        await self.send(text_data=json.dumps(event["data"]))