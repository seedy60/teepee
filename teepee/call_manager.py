import logging
import os

import wx

log = logging.getLogger(__name__)


class CallManager:
    def __init__(self, telegram_manager, config):
        self.tg = telegram_manager
        self.config = config
        self.active_call = None
        self.on_call_state_changed = None

    async def request_call(self, user_id):
        from telethon.tl.functions.phone import RequestCallRequest
        from telethon.tl.types import PhoneCallProtocol

        protocol = PhoneCallProtocol(
            min_layer=65,
            max_layer=92,
            udp_p2p=True,
            udp_reflector=True,
            library_versions=["5.0.0"],
        )
        try:
            result = await self.tg.client(
                RequestCallRequest(
                    user_id=user_id,
                    random_id=int.from_bytes(os.urandom(4), "big"),
                    g_a_hash=os.urandom(256),
                    protocol=protocol,
                )
            )
            self.active_call = result.phone_call
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "calling", result)
            return result
        except Exception as e:
            log.error("Failed to request call: %s", e)
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "error", str(e))
            return None

    async def accept_call(self, call):
        from telethon.tl.functions.phone import AcceptCallRequest
        from telethon.tl.types import PhoneCallProtocol

        protocol = PhoneCallProtocol(
            min_layer=65,
            max_layer=92,
            udp_p2p=True,
            udp_reflector=True,
            library_versions=["5.0.0"],
        )
        try:
            result = await self.tg.client(
                AcceptCallRequest(
                    peer=call,
                    g_b=os.urandom(256),
                    protocol=protocol,
                )
            )
            self.active_call = result.phone_call
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "active", result)
            return result
        except Exception as e:
            log.error("Failed to accept call: %s", e)
            return None

    async def discard_call(self):
        if not self.active_call:
            return
        from telethon.tl.functions.phone import DiscardCallRequest
        from telethon.tl.types import (
            InputPhoneCall,
            PhoneCallDiscardReasonHangup,
        )

        try:
            input_call = InputPhoneCall(
                id=self.active_call.id,
                access_hash=self.active_call.access_hash,
            )
            await self.tg.client(
                DiscardCallRequest(
                    peer=input_call,
                    duration=0,
                    reason=PhoneCallDiscardReasonHangup(),
                    connection_id=0,
                )
            )
        except Exception as e:
            log.error("Failed to discard call: %s", e)
        finally:
            self.active_call = None
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "ended", None)

    @property
    def in_call(self):
        return self.active_call is not None
