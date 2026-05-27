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
        self.on_message_edited = None
        self.on_message_read = None
        self.on_incoming_call = None
        self.call_manager = None

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

    async def get_message_by_id(self, entity, msg_id):
        return await self.client.get_messages(entity, ids=msg_id)

    async def search_files(self, entity, query="", limit=50, offset_id=0):
        from telethon.tl.types import InputMessagesFilterDocument
        return await self.client.get_messages(
            entity,
            limit=limit,
            search=query or None,
            filter=InputMessagesFilterDocument,
            offset_id=offset_id,
        )

    async def search_links(self, entity, limit=50, offset_id=0):
        from telethon.tl.types import InputMessagesFilterUrl
        return await self.client.get_messages(
            entity,
            limit=limit,
            filter=InputMessagesFilterUrl,
            offset_id=offset_id,
        )

    async def mark_as_read(self, entity):
        return await self.client.send_read_acknowledge(entity)

    async def send_message(self, entity, text, reply_to=None):
        return await self.client.send_message(entity, text, reply_to=reply_to)

    async def send_voice(self, entity, file_path, reply_to=None):
        return await self.client.send_file(
            entity, file_path, voice_note=True, reply_to=reply_to
        )

    async def send_file(self, entity, file_path, reply_to=None, caption="", force_document=True):
        return await self.client.send_file(
            entity, file_path, caption=caption, reply_to=reply_to,
            force_document=force_document,
        )

    async def send_sticker(self, entity, sticker, reply_to=None):
        return await self.client.send_file(entity, sticker, reply_to=reply_to)

    async def get_sticker_set(self, short_name):
        from telethon.tl.functions.messages import GetStickerSetRequest
        from telethon.tl.types import InputStickerSetShortName

        result = await self.client(
            GetStickerSetRequest(
                stickerset=InputStickerSetShortName(short_name=short_name),
                hash=0,
            )
        )
        return result

    async def search_stickers(self, query):
        """Search stickers by emoji character or by text keyword.

        If the query contains emoji characters, searches stickers for that emoji.
        Otherwise, searches sticker sets by name and returns stickers from matches.
        """
        if not query or not query.strip():
            return type("Empty", (), {"stickers": []})()

        # Detect if input contains emoji (non-ASCII characters in common emoji ranges)
        has_emoji = any(
            ord(ch) > 0x2000 for ch in query
        )

        if has_emoji:
            from telethon.tl.functions.messages import GetStickersRequest

            result = await self.client(GetStickersRequest(emoticon=query, hash=0))
            return result

        # Text search: find sticker sets by name, then collect their stickers
        from telethon.tl.functions.messages import (
            GetStickerSetRequest,
            SearchStickerSetsRequest,
        )
        from telethon.tl.types import InputStickerSetID

        found = await self.client(
            SearchStickerSetsRequest(q=query, hash=0)
        )
        sets = getattr(found, "sets", [])
        all_stickers = []
        # Collect stickers from up to 5 matching sets
        for covered in sets[:5]:
            sticker_set = getattr(covered, "set", None)
            if not sticker_set:
                continue
            # Get full sticker set with all documents
            try:
                full = await self.client(
                    GetStickerSetRequest(
                        stickerset=InputStickerSetID(
                            id=sticker_set.id,
                            access_hash=sticker_set.access_hash,
                        ),
                        hash=0,
                    )
                )
                docs = getattr(full, "documents", [])
                all_stickers.extend(docs)
            except Exception:
                # Fall back to cover documents if full set fetch fails
                covers = getattr(covered, "covers", None)
                if covers:
                    all_stickers.extend(covers)
                else:
                    cover = getattr(covered, "cover", None)
                    if cover:
                        all_stickers.append(cover)

        return type("TextResult", (), {"stickers": all_stickers})()

    async def get_read_outbox_max_id(self, entity):
        from telethon.tl.functions.messages import GetPeerDialogsRequest

        peer = await self.client.get_input_entity(entity)
        result = await self.client(GetPeerDialogsRequest(peers=[peer]))
        if result.dialogs:
            return result.dialogs[0].read_outbox_max_id
        return 0

    async def download_media(self, message, path):
        return await self.client.download_media(message, file=str(path))

    async def edit_message(self, entity, message_id, new_text):
        return await self.client.edit_message(entity, message_id, new_text)

    async def delete_messages(self, entity, message_ids, revoke=True):
        return await self.client.delete_messages(entity, message_ids, revoke=revoke)

    async def delete_dialog(self, entity, revoke=True):
        from telethon.errors import ChatAdminRequiredError

        try:
            return await self.client.delete_dialog(entity, revoke=revoke)
        except ChatAdminRequiredError:
            # Some chats/channels disallow revoke-history delete unless admin.
            # Fall back to local-only deletion to avoid false failure.
            if revoke:
                return await self.client.delete_dialog(entity, revoke=False)
            raise

    async def click_inline_button(self, msg, button_data):
        return await msg.click(data=button_data)

    async def join_channel(self, entity):
        from telethon.tl.functions.channels import JoinChannelRequest

        return await self.client(JoinChannelRequest(entity))

    async def leave_channel(self, entity):
        from telethon.tl.functions.channels import LeaveChannelRequest
        from telethon.tl.functions.messages import DeleteChatUserRequest
        from telethon.tl.types import Chat

        peer = await self.client.get_entity(entity)

        # Basic groups (Chat) and channels/supergroups (Channel)
        # use different MTProto requests.
        if isinstance(peer, Chat):
            me = await self.client.get_input_entity("me")
            return await self.client(
                DeleteChatUserRequest(
                    chat_id=peer.id,
                    user_id=me,
                    revoke_history=False,
                )
            )

        return await self.client(LeaveChannelRequest(peer))

    async def get_participants(self, entity, limit=200):
        return await self.client.get_participants(entity, limit=limit)

    async def kick_participant(self, entity, user):
        from telethon.tl.functions.channels import EditBannedRequest
        from telethon.tl.functions.messages import DeleteChatUserRequest
        from telethon.tl.types import ChatBannedRights
        from telethon.tl.types import Chat

        peer = await self.client.get_entity(entity)

        # Basic groups (Chat) and channels/supergroups (Channel)
        # use different MTProto requests.
        if isinstance(peer, Chat):
            return await self.client(
                DeleteChatUserRequest(
                    chat_id=peer.id,
                    user_id=user,
                    revoke_history=True,
                )
            )

        rights = ChatBannedRights(until_date=None, view_messages=True)
        return await self.client(EditBannedRequest(peer, user, rights))

    async def edit_chat_title(self, entity, title):
        from telethon.tl.functions.channels import EditTitleRequest

        return await self.client(EditTitleRequest(entity, title))

    async def create_group(
        self,
        title,
        users,
        is_public=False,
        public_username="",
    ):
        from telethon.tl.functions.messages import CreateChatRequest

        if is_public:
            created = await self.create_channel(
                title,
                about="",
                megagroup=True,
                is_public=True,
                public_username=public_username,
            )
            if users:
                await self.invite_to_channel(created, users)
            return created

        return await self.client(CreateChatRequest(title=title, users=users))

    async def create_channel(
        self,
        title,
        about="",
        megagroup=False,
        is_public=False,
        public_username="",
    ):
        from telethon.tl.functions.channels import CreateChannelRequest
        from telethon.tl.functions.channels import UpdateUsernameRequest
        from telethon.errors import RPCError
        from telethon.errors import (
            ChannelsAdminPublicTooMuchError,
            UsernameInvalidError,
            UsernameOccupiedError,
        )
        from telethon.tl.types import InputChannel

        created = await self.client(
            CreateChannelRequest(
                title=title,
                about=about,
                megagroup=megagroup,
            )
        )

        chats = getattr(created, "chats", None) or []
        created_peer = chats[0] if chats else created
        if is_public and public_username:
            # UpdateUsernameRequest needs InputChannel with integer ids.
            if isinstance(created_peer, InputChannel):
                channel_input = created_peer
            else:
                channel_id = int(getattr(created_peer, "id", 0))
                access_hash = int(getattr(created_peer, "access_hash", 0))
                if not channel_id or not access_hash:
                    resolved = await self.client.get_entity(created_peer)
                    channel_id = int(getattr(resolved, "id", 0))
                    access_hash = int(getattr(resolved, "access_hash", 0))
                channel_input = InputChannel(
                    channel_id=channel_id,
                    access_hash=access_hash,
                )

            try:
                await self.client(
                    UpdateUsernameRequest(
                        channel=channel_input,
                        username=public_username,
                    )
                )
            except UsernameInvalidError as e:
                raise RuntimeError(
                    "Invalid public username. Use 5-32 letters, numbers, and underscores."
                ) from e
            except UsernameOccupiedError as e:
                raise RuntimeError(
                    "That public username is already taken."
                ) from e
            except ChannelsAdminPublicTooMuchError as e:
                raise RuntimeError(
                    "You already have too many public channels/groups."
                ) from e
            except RPCError as e:
                if type(e).__name__ == "UsernamePurchaseAvailableError":
                    raise RuntimeError(
                        "That public username is a purchasable collectible on Telegram and cannot be assigned for free. Choose a different username."
                    ) from e
                raise RuntimeError(
                    f"Telegram rejected public username setup: {type(e).__name__}: {e!r}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Telegram rejected public username setup: {type(e).__name__}: {e!r}"
                ) from e

        return created_peer

    async def invite_to_channel(self, entity, users):
        from telethon.tl.functions.channels import InviteToChannelRequest
        from telethon.tl.functions.messages import AddChatUserRequest
        from telethon.tl.types import Chat

        peer = await self.client.get_entity(entity)

        # Basic groups (Chat) and channels/supergroups (Channel)
        # use different MTProto requests.
        if isinstance(peer, Chat):
            result = None
            for user in users:
                result = await self.client(
                    AddChatUserRequest(
                        chat_id=peer.id,
                        user_id=user,
                        fwd_limit=0,
                    )
                )
            return result

        return await self.client(
            InviteToChannelRequest(channel=peer, users=users)
        )

    async def export_invite_link(self, entity):
        from telethon.tl.functions.messages import ExportChatInviteRequest

        peer = await self.client.get_input_entity(entity)
        result = await self.client(ExportChatInviteRequest(peer=peer))
        return getattr(result, "link", "")

    async def set_member_permissions(self, entity, user, permissions):
        from telethon.tl.functions.channels import EditBannedRequest
        from telethon.tl.types import Chat
        from telethon.tl.types import ChatBannedRights

        peer = await self.client.get_entity(entity)
        if isinstance(peer, Chat):
            raise RuntimeError(
                "Per-member permissions are only supported for channels and supergroups."
            )

        allow_send_messages = bool(permissions.get("send_messages", True))
        allow_send_media = bool(permissions.get("send_media", True))
        allow_send_stickers = bool(permissions.get("send_stickers", True))
        allow_send_polls = bool(permissions.get("send_polls", True))
        allow_change_info = bool(permissions.get("change_info", True))
        allow_invite_users = bool(permissions.get("invite_users", True))
        allow_pin_messages = bool(permissions.get("pin_messages", True))

        rights = ChatBannedRights(
            until_date=None,
            view_messages=False,
            send_messages=not allow_send_messages,
            send_media=not allow_send_media,
            send_stickers=not allow_send_stickers,
            send_gifs=not allow_send_stickers,
            send_games=not allow_send_stickers,
            send_inline=not allow_send_stickers,
            embed_links=not allow_send_media,
            send_polls=not allow_send_polls,
            change_info=not allow_change_info,
            invite_users=not allow_invite_users,
            pin_messages=not allow_pin_messages,
        )
        return await self.client(EditBannedRequest(peer, user, rights))

    async def set_member_admin_role(self, entity, user, make_admin, rank="Admin"):
        from telethon.tl.functions.channels import EditAdminRequest
        from telethon.tl.functions.messages import EditChatAdminRequest
        from telethon.tl.types import Chat
        from telethon.tl.types import ChatAdminRights

        peer = await self.client.get_entity(entity)

        # Basic groups (Chat) use EditChatAdminRequest.
        if isinstance(peer, Chat):
            return await self.client(
                EditChatAdminRequest(
                    chat_id=peer.id,
                    user_id=user,
                    is_admin=bool(make_admin),
                )
            )

        # Channels/supergroups use EditAdminRequest and ChatAdminRights.
        if make_admin:
            rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True,
                manage_topics=True,
                post_stories=True,
                edit_stories=True,
                delete_stories=True,
            )
            role_rank = rank or "Admin"
        else:
            rights = ChatAdminRights(
                change_info=False,
                post_messages=False,
                edit_messages=False,
                delete_messages=False,
                ban_users=False,
                invite_users=False,
                pin_messages=False,
                add_admins=False,
                anonymous=False,
                manage_call=False,
                other=False,
                manage_topics=False,
                post_stories=False,
                edit_stories=False,
                delete_stories=False,
            )
            role_rank = ""

        return await self.client(
            EditAdminRequest(
                channel=peer,
                user_id=user,
                admin_rights=rights,
                rank=role_rank,
            )
        )

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

    async def update_username(self, username):
        from telethon.tl.functions.account import UpdateUsernameRequest

        return await self.client(UpdateUsernameRequest(username))

    async def get_privacy_setting(self, key):
        from telethon.tl.functions.account import GetPrivacyRequest
        from telethon.tl.types import (
            PrivacyValueAllowAll,
            PrivacyValueAllowContacts,
            PrivacyValueDisallowAll,
        )

        result = await self.client(GetPrivacyRequest(key))
        for rule in result.rules:
            if isinstance(rule, PrivacyValueAllowAll):
                return 0
            if isinstance(rule, PrivacyValueAllowContacts):
                return 1
            if isinstance(rule, PrivacyValueDisallowAll):
                return 2
        return 0

    async def set_privacy_setting(self, key, value):
        from telethon.tl.functions.account import SetPrivacyRequest
        from telethon.tl.types import (
            InputPrivacyValueAllowAll,
            InputPrivacyValueAllowContacts,
            InputPrivacyValueDisallowAll,
        )

        rules_map = {
            0: [InputPrivacyValueAllowAll()],
            1: [InputPrivacyValueAllowContacts()],
            2: [InputPrivacyValueDisallowAll()],
        }
        return await self.client(
            SetPrivacyRequest(
                key=key,
                rules=rules_map.get(value, [InputPrivacyValueAllowAll()]),
            )
        )

    async def get_account_ttl(self):
        from telethon.tl.functions.account import GetAccountTTLRequest

        result = await self.client(GetAccountTTLRequest())
        return result.days

    async def set_account_ttl(self, days):
        from telethon.tl.functions.account import SetAccountTTLRequest
        from telethon.tl.types import AccountDaysTTL

        return await self.client(
            SetAccountTTLRequest(AccountDaysTTL(days=days))
        )

    async def get_authorizations(self):
        from telethon.tl.functions.account import GetAuthorizationsRequest

        return await self.client(GetAuthorizationsRequest())

    async def reset_authorization(self, auth_hash):
        from telethon.tl.functions.account import ResetAuthorizationRequest

        return await self.client(ResetAuthorizationRequest(auth_hash))

    async def get_password_info(self):
        from telethon.tl.functions.account import GetPasswordRequest

        return await self.client(GetPasswordRequest())

    async def set_password(
        self,
        current_password=None,
        new_password=None,
        hint="",
        email=None,
        email_code_callback=None,
    ):
        kwargs = {
            "current_password": current_password,
            "new_password": new_password,
            "hint": hint or "",
        }
        if email:
            kwargs["email"] = email
            kwargs["email_code_callback"] = email_code_callback
        return await self.client.edit_2fa(**kwargs)

    async def set_birthday(self, day, month, year=None):
        from telethon.tl.functions.account import UpdateBirthdayRequest
        from telethon.tl.types import Birthday

        kwargs = {"day": day, "month": month}
        if year:
            kwargs["year"] = year
        return await self.client(
            UpdateBirthdayRequest(birthday=Birthday(**kwargs))
        )

    async def clear_birthday(self):
        from telethon.tl.functions.account import UpdateBirthdayRequest

        return await self.client(UpdateBirthdayRequest(birthday=None))

    async def upload_profile_photo(self, file_path):
        from telethon.tl.functions.photos import UploadProfilePhotoRequest

        file = await self.client.upload_file(file_path)
        return await self.client(UploadProfilePhotoRequest(file=file))

    async def get_profile_photos(self):
        from telethon.tl.functions.photos import GetUserPhotosRequest
        from telethon.tl.types import InputUserSelf

        result = await self.client(
            GetUserPhotosRequest(
                user_id=InputUserSelf(),
                offset=0,
                max_id=0,
                limit=100,
            )
        )
        return result.photos

    async def delete_profile_photo(self, photo):
        from telethon.tl.functions.photos import DeletePhotosRequest
        from telethon.tl.types import InputPhoto

        return await self.client(
            DeletePhotosRequest(
                id=[
                    InputPhoto(
                        id=photo.id,
                        access_hash=photo.access_hash,
                        file_reference=photo.file_reference,
                    )
                ]
            )
        )

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

    async def get_blocked_users(self):
        from telethon.tl.functions.contacts import GetBlockedRequest

        result = await self.client(GetBlockedRequest(offset=0, limit=100))
        return {getattr(u, "id", None) for u in result.users}

    async def block_user(self, entity):
        from telethon.tl.functions.contacts import BlockRequest

        peer = await self.client.get_input_entity(entity)
        return await self.client(BlockRequest(id=peer))

    async def unblock_user(self, entity):
        from telethon.tl.functions.contacts import UnblockRequest

        peer = await self.client.get_input_entity(entity)
        return await self.client(UnblockRequest(id=peer))

    async def report_user(self, entity, reason, message=""):
        from telethon.tl.functions.messages import ReportRequest

        peer = await self.client.get_input_entity(entity)
        return await self.client(
            ReportRequest(peer=peer, id=[], reason=reason, message=message)
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
            first = getattr(sender, "first_name", None) or ""
            last = getattr(sender, "last_name", None) or ""
            full = f"{first} {last}".strip()
            sender_name = (
                full
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

        @self.client.on(events.MessageEdited)
        async def _on_edited(event):
            if not self.on_message_edited:
                return
            msg = event.message
            data = {
                "message": msg,
                "chat_id": event.chat_id,
                "text": msg.text or "",
            }
            wx.CallAfter(self.on_message_edited, data)

        @self.client.on(events.MessageRead(inbox=False))
        async def _on_read(event):
            if not self.on_message_read:
                return
            data = {
                "chat_id": event.chat_id,
                "max_id": event.max_id,
            }
            wx.CallAfter(self.on_message_read, data)

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

        @self.client.on(events.Raw)
        async def _on_raw(event):
            from telethon.tl.types import (
                UpdatePhoneCall,
                UpdatePhoneCallSignalingData,
            )

            # Forward signaling data to ntgcalls
            if isinstance(event, UpdatePhoneCallSignalingData):
                if self.call_manager:
                    await self.call_manager.receive_signaling(event.data)
                return

            if not isinstance(event, UpdatePhoneCall):
                return

            phone_call = event.phone_call
            from telethon.tl.types import PhoneCallRequested

            if isinstance(phone_call, PhoneCallRequested):
                # Prepare DH data in call_manager before showing dialog
                if self.call_manager:
                    await self.call_manager.prepare_incoming(phone_call)
                if not self.on_incoming_call:
                    return
                caller_id = phone_call.admin_id
                try:
                    caller = await self.client.get_entity(caller_id)
                    first = getattr(caller, "first_name", None) or ""
                    last = getattr(caller, "last_name", None) or ""
                    caller_name = f"{first} {last}".strip() or "Unknown"
                except Exception:
                    caller_name = "Unknown"
                wx.CallAfter(
                    self.on_incoming_call, phone_call, caller_name
                )
            else:
                # Forward PhoneCallAccepted, PhoneCall, PhoneCallDiscarded
                # to call_manager for the connect flow
                if self.call_manager:
                    await self.call_manager.handle_call_update(phone_call)

    def stop(self):
        if self._loop and self._loop.is_running():
            if self.client and self.client.is_connected():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.disconnect(), self._loop
                    )
                    future.result(timeout=2)
                except Exception as e:
                    log.debug("Shutdown disconnect error: %s", e)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)
