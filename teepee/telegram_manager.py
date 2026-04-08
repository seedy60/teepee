import asyncio
import logging
import threading

import wx
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError  # noqa: F401

log = logging.getLogger(__name__)


class TelegramManager:
    def __init__(self, config):
        self.config = config
        self.client = None
        self._loop = None
        self._thread = None

        self.on_new_message = None
        self.on_message_sent = None
        self.on_incoming_call = None

    def start(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="TelegramThread"
        )
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def submit_wait(self, coro, timeout=60):
        future = self.submit(coro)
        return future.result(timeout=timeout)

    async def connect(self):
        api_id = int(self.config["api_id"])
        api_hash = str(self.config["api_hash"])
        session = self.config.session_path
        self.client = TelegramClient(session, api_id, api_hash)
        await self.client.connect()
        self._register_handlers()
        return await self.client.is_user_authorized()

    async def send_code(self, phone):
        return await self.client.send_code_request(phone)

    async def sign_in_code(self, phone, code, phone_code_hash):
        return await self.client.sign_in(
            phone, code, phone_code_hash=phone_code_hash
        )

    async def sign_in_password(self, password):
        return await self.client.sign_in(password=password)

    async def get_dialogs(self, limit=100):
        return await self.client.get_dialogs(limit=limit)

    async def get_messages(self, entity, limit=50):
        return await self.client.get_messages(entity, limit=limit)

    async def mark_as_read(self, entity):
        return await self.client.send_read_acknowledge(entity)

    async def send_message(self, entity, text, reply_to=None):
        return await self.client.send_message(entity, text, reply_to=reply_to)

    async def send_voice(self, entity, file_path, reply_to=None):
        return await self.client.send_file(
            entity, file_path, voice_note=True, reply_to=reply_to
        )

    async def download_media(self, message, path):
        return await self.client.download_media(message, file=str(path))

    async def delete_messages(self, entity, message_ids, revoke=True):
        return await self.client.delete_messages(entity, message_ids, revoke=revoke)

    async def delete_dialog(self, entity, revoke=True):
        return await self.client.delete_dialog(entity, revoke=revoke)

    async def click_inline_button(self, msg, button_data):
        return await msg.click(data=button_data)

    async def join_channel(self, entity):
        from telethon.tl.functions.channels import JoinChannelRequest

        return await self.client(JoinChannelRequest(entity))

    async def leave_channel(self, entity):
        from telethon.tl.functions.channels import LeaveChannelRequest

        return await self.client(LeaveChannelRequest(entity))

    async def get_participants(self, entity, limit=200):
        return await self.client.get_participants(entity, limit=limit)

    async def kick_participant(self, entity, user):
        from telethon.tl.functions.channels import EditBannedRequest
        from telethon.tl.types import ChatBannedRights

        rights = ChatBannedRights(until_date=None, view_messages=True)
        return await self.client(EditBannedRequest(entity, user, rights))

    async def edit_chat_title(self, entity, title):
        from telethon.tl.functions.channels import EditTitleRequest

        return await self.client(EditTitleRequest(entity, title))

    async def get_entity(self, username):
        return await self.client.get_entity(username)

    async def get_me(self):
        return await self.client.get_me()

    async def get_full_me(self):
        from telethon.tl.functions.users import GetFullUserRequest
        from telethon.tl.types import InputUserSelf

        result = await self.client(GetFullUserRequest(InputUserSelf()))
        return result

    async def update_profile(self, first_name=None, last_name=None, about=None):
        from telethon.tl.functions.account import UpdateProfileRequest

        kwargs = {}
        if first_name is not None:
            kwargs["first_name"] = first_name
        if last_name is not None:
            kwargs["last_name"] = last_name
        if about is not None:
            kwargs["about"] = about
        return await self.client(UpdateProfileRequest(**kwargs))

    async def mute_chat(self, entity, mute_until):
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

        peer = await self.client.get_input_entity(entity)
        return await self.client(
            UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(peer=peer),
                settings=InputPeerNotifySettings(mute_until=mute_until),
            )
        )

    async def unmute_chat(self, entity):
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

        peer = await self.client.get_input_entity(entity)
        return await self.client(
            UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(peer=peer),
                settings=InputPeerNotifySettings(mute_until=0),
            )
        )

    async def disconnect(self):
        if self.client and self.client.is_connected():
            try:
                await self.client.disconnect()
            except Exception as e:
                log.debug("Disconnect error (expected during shutdown): %s", e)

    def _register_handlers(self):
        @self.client.on(events.NewMessage(incoming=True))
        async def _on_incoming(event):
            if not self.on_new_message:
                return
            msg = event.message
            sender = await event.get_sender()
            chat = await event.get_chat()
            sender_name = (
                getattr(sender, "first_name", None)
                or getattr(sender, "title", None)
                or "Unknown"
            )
            from telethon.tl.types import Channel, Chat

            is_group = isinstance(chat, Chat) or (
                isinstance(chat, Channel)
                and getattr(chat, "megagroup", False)
            )
            is_channel = (
                isinstance(chat, Channel)
                and not getattr(chat, "megagroup", False)
            )
            data = {
                "message": msg,
                "sender_name": sender_name,
                "chat_id": event.chat_id,
                "text": msg.text or "",
                "date": msg.date,
                "is_voice": bool(msg.voice),
                "is_media": bool(msg.media),
                "out": False,
                "is_group": is_group,
                "is_channel": is_channel,
                "reply_to_msg_id": (
                    msg.reply_to.reply_to_msg_id
                    if msg.reply_to
                    else None
                ),
            }
            wx.CallAfter(self.on_new_message, data)

        @self.client.on(events.NewMessage(outgoing=True))
        async def _on_outgoing(event):
            if not self.on_message_sent:
                return
            msg = event.message
            data = {
                "message": msg,
                "sender_name": "You",
                "chat_id": event.chat_id,
                "text": msg.text or "",
                "date": msg.date,
                "is_voice": bool(msg.voice),
                "is_media": bool(msg.media),
                "out": True,
                "reply_to_msg_id": (
                    msg.reply_to.reply_to_msg_id
                    if msg.reply_to
                    else None
                ),
            }
            wx.CallAfter(self.on_message_sent, data)

    def stop(self):
        if self._loop and self._loop.is_running():
            if self.client and self.client.is_connected():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.disconnect(), self._loop
                    )
                    future.result(timeout=5)
                except Exception as e:
                    log.debug("Shutdown disconnect error: %s", e)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
