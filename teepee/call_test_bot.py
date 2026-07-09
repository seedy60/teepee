#!/usr/bin/env python3
"""Teepee Call Test Bot

A Telegram bot that receives or makes private calls and plays a
fax-machine tone for 25 seconds upon connection.  Uses the same
ntgcalls WebRTC transport as the Teepee client, so both sides speak
an identical protocol -- perfect for end-to-end testing.

Usage
-----
Wait for incoming calls::

    python call_test_bot.py

Call a specific user::

    python call_test_bot.py --call @username
    python call_test_bot.py --call 123456789

Environment variables (prompted if missing)::

    TELEGRAM_API_ID   - Telegram API ID
    TELEGRAM_API_HASH - Telegram API hash

On first run, Telethon will prompt for a phone number and
verification code. The session is cached in
``call_test_user_session.session`` for subsequent runs.

The script also attempts to read API_ID / API_HASH from the
encrypted Teepee credentials store if the env vars are unset.

Note: Telegram restricts phone-call MTProto methods to user
accounts, so this script logs in as a user (not a bot).
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import hashlib
import logging
import math
import os
import struct
import sys
import threading
import time

from ntgcalls import (
    AudioDescription,
    ConnectionNotFound,
    DhConfig as NtgDhConfig,
    MediaDescription,
    MediaSource,
    NTgCalls,
    RTCServer,
    StreamMode,
)
from telethon import TelegramClient, events

log = logging.getLogger("call_test_bot")

SAMPLE_RATE = 48000
CHANNELS = 1
DURATION = 25  # seconds of fax tone playback
TONE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fax_tone.pcm")


# ------------------------------------------------------------------
# Fax tone generator
# ------------------------------------------------------------------

def generate_fax_tone(path: str, duration: int = DURATION,
                      sample_rate: int = SAMPLE_RATE) -> None:
    """Create a raw s16le PCM file with a fax-machine CED tone.

    2100 Hz sine wave with a 180-degree phase reversal every 450 ms --
    the internationally recognised called-station-identification sound.
    """
    total = duration * sample_rate
    reversal = int(0.45 * sample_rate)
    amplitude = 0.75
    freq = 2100.0
    two_pi_f = 2.0 * math.pi * freq

    buf = bytearray(total * 2)
    phase = 0.0
    for i in range(total):
        if i > 0 and i % reversal == 0:
            phase += math.pi
        value = amplitude * math.sin(two_pi_f * i / sample_rate + phase)
        struct.pack_into("<h", buf, i * 2, max(-32768, min(32767, int(value * 32767))))

    with open(path, "wb") as f:
        f.write(buf)
    log.info("Generated %ds fax tone: %s (%d bytes)", duration, path, len(buf))


# ------------------------------------------------------------------
# NTgCalls bridge  (dedicated event-loop thread, same as Teepee)
# ------------------------------------------------------------------

class _NtgBridge:
    _ASYNC = frozenset({
        "connect_p2p", "create_p2p_call", "exchange_keys",
        "init_exchange", "mute", "send_signaling",
        "set_stream_sources", "stop", "unmute",
    })

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._ntg = None
        self._ready = threading.Event()
        threading.Thread(target=self._run_loop, daemon=True).start()
        self._ready.wait()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._ntg = NTgCalls()
        self._ready.set()
        self._loop.run_forever()

    def __getattr__(self, name):
        attr = getattr(self._ntg, name)
        if name not in self._ASYNC:
            return attr

        async def _bridged(*args, **kwargs):
            cf = concurrent.futures.Future()

            async def _run():
                try:
                    cf.set_result(await attr(*args, **kwargs))
                except Exception as exc:
                    cf.set_exception(exc)

            asyncio.run_coroutine_threadsafe(_run(), self._loop)
            return await asyncio.wrap_future(cf)

        return _bridged


# ------------------------------------------------------------------
# Bot
# ------------------------------------------------------------------

class CallTestBot:
    def __init__(self, api_id: int, api_hash: str):
        self.client = TelegramClient(
            "call_test_user_session", api_id, api_hash,
        )
        self._ntg = _NtgBridge()

        self._active_call = None
        self._active_user_id: int | None = None
        self._call_state: str | None = None  # "incoming" / "outgoing"
        self._confirmed_future: asyncio.Future | None = None
        self._connected = asyncio.Event()
        self._actually_connected = False
        self._tg_loop: asyncio.AbstractEventLoop | None = None

        self._ntg.on_signaling(self._on_ntg_signaling)
        self._ntg.on_connection_change(self._on_ntg_connection_change)

    # ---- callbacks (run on ntgcalls thread) -----------------------

    def _on_ntg_signaling(self, user_id, data):
        log.debug("ntgcalls -> Telegram signaling: %d bytes", len(data))
        if self._tg_loop:
            asyncio.run_coroutine_threadsafe(
                self._send_signaling(data), self._tg_loop,
            )

    def _on_ntg_connection_change(self, user_id, network_info):
        from ntgcalls import ConnectionState

        name = (network_info.state.name
                if hasattr(network_info.state, "name")
                else str(network_info.state))
        log.info("Connection state: %s", name)
        if network_info.state == ConnectionState.CONNECTED:
            self._actually_connected = True
            self._connected.set()
        elif name == "TIMEOUT":
            log.error("WebRTC connection timed out (ICE failed)")
            self._actually_connected = False
            self._connected.set()          # unblock waiter
        elif network_info.state == ConnectionState.CLOSED:
            log.info("Connection closed")
            self._actually_connected = False
            self._connected.set()

    # ---- signaling -----------------------------------------------

    async def _send_signaling(self, data: bytes):
        if not self._active_call:
            return
        from telethon.tl.functions.phone import SendSignalingDataRequest
        from telethon.tl.types import InputPhoneCall

        peer = InputPhoneCall(
            id=self._active_call.id,
            access_hash=self._active_call.access_hash,
        )
        try:
            await self.client(SendSignalingDataRequest(peer=peer, data=data))
            log.debug("Signaling sent OK")
        except Exception as e:
            log.error("Signaling send failed: %s", e)

    async def _receive_signaling(self, data: bytes):
        log.debug("Telegram -> ntgcalls signaling: %d bytes", len(data))
        if self._active_user_id is None:
            return
        try:
            await self._ntg.send_signaling(self._active_user_id, data)
        except Exception as e:
            log.error("Signaling forward failed: %s", e)

    # ---- audio ---------------------------------------------------

    @staticmethod
    def _audio_capture_desc():
        return AudioDescription(
            media_source=MediaSource.FILE,
            sample_rate=SAMPLE_RATE,
            channel_count=CHANNELS,
            input=os.path.abspath(TONE_FILE),
        )

    @staticmethod
    def _audio_playback_desc():
        devs = NTgCalls.get_media_devices()
        meta = devs.speaker[0].metadata if devs.speaker else ""
        return AudioDescription(
            media_source=MediaSource.DEVICE,
            sample_rate=SAMPLE_RATE,
            channel_count=CHANNELS,
            input=meta,
        )

    # ---- protocol helpers ----------------------------------------

    @staticmethod
    def _tg_protocol(caller_protocol=None):
        from telethon.tl.types import PhoneCallProtocol

        proto = NTgCalls.get_protocol()
        our = list(proto.library_versions)
        if caller_protocol:
            theirs = list(caller_protocol.library_versions)
            overlap = set(our) & set(theirs)
            versions = our if overlap else list(dict.fromkeys(our + theirs))
            return PhoneCallProtocol(
                min_layer=caller_protocol.min_layer,
                max_layer=caller_protocol.max_layer,
                udp_p2p=True, udp_reflector=True,
                library_versions=versions,
            )
        return PhoneCallProtocol(
            min_layer=proto.min_layer, max_layer=proto.max_layer,
            udp_p2p=True, udp_reflector=True,
            library_versions=our,
        )

    @staticmethod
    def _parse_servers(connections):
        from telethon.tl.types import PhoneConnection, PhoneConnectionWebrtc

        servers = []
        for c in connections:
            if isinstance(c, PhoneConnectionWebrtc):
                servers.append(RTCServer(
                    id=c.id, ipv4=c.ip or "", ipv6=c.ipv6 or "",
                    port=c.port, username=c.username, password=c.password,
                    turn=bool(getattr(c, "turn", False)),
                    stun=bool(getattr(c, "stun", False)),
                    tcp=False,
                ))
            elif isinstance(c, PhoneConnection):
                servers.append(RTCServer(
                    id=c.id, ipv4=c.ip or "", ipv6=c.ipv6 or "",
                    port=c.port, turn=True, stun=False,
                    tcp=bool(getattr(c, "tcp", False)),
                    peer_tag=c.peer_tag,
                ))
        return servers

    # ---- incoming call -------------------------------------------

    async def accept_call(self, phone_call):
        from telethon.tl.functions.phone import AcceptCallRequest
        from telethon.tl.types import InputPhoneCall

        user_id = phone_call.admin_id
        log.info("Incoming call from user %s", user_id)
        self._call_state = "incoming"
        self._connected.clear()

        try:
            await self._ntg.create_p2p_call(user_id)

            capture = MediaDescription(microphone=self._audio_capture_desc())
            playback = MediaDescription(speaker=self._audio_playback_desc())
            await self._ntg.set_stream_sources(user_id, StreamMode.CAPTURE, capture)
            await self._ntg.set_stream_sources(user_id, StreamMode.PLAYBACK, playback)

            dh = await self._get_dh_config()
            ntg_dh = NtgDhConfig(g=dh.g, p=dh.p, random=dh.random)
            g_b = await self._ntg.init_exchange(
                user_id, ntg_dh, phone_call.g_a_hash,
            )

            protocol = self._tg_protocol(phone_call.protocol)
            input_call = InputPhoneCall(
                id=phone_call.id, access_hash=phone_call.access_hash,
            )
            log.info("Sending AcceptCallRequest...")
            result = await self.client(
                AcceptCallRequest(peer=input_call, g_b=g_b, protocol=protocol),
            )
            self._active_call = result.phone_call
            self._active_user_id = user_id
            log.info("Accepted (type=%s), waiting for confirmation...",
                     type(result.phone_call).__name__)

            self._confirmed_future = self._tg_loop.create_future()
            confirmed = await asyncio.wait_for(self._confirmed_future, timeout=30)
            self._active_call = confirmed

            await self._ntg.exchange_keys(
                user_id, confirmed.g_a_or_b, confirmed.key_fingerprint,
            )

            servers = self._parse_servers(confirmed.connections)
            versions = list(confirmed.protocol.library_versions)
            p2p = getattr(confirmed, "p2p_allowed", False)
            log.info("Connecting P2P: %d servers, versions=%s, p2p=%s",
                     len(servers), versions, p2p)
            await self._ntg.connect_p2p(user_id, servers, versions, p2p)

            await self._play_and_hangup(user_id)

        except Exception as e:
            log.error("Accept failed: %s", e, exc_info=True)
            try:
                await self._ntg.stop(user_id)
            except Exception:
                pass
            self._cleanup()

    # ---- outgoing call -------------------------------------------

    async def request_call(self, target_user_id: int):
        from telethon.tl.functions.phone import (
            ConfirmCallRequest,
            RequestCallRequest,
        )
        from telethon.tl.types import InputPhoneCall

        user_id = target_user_id
        log.info("Calling user %s", user_id)
        self._call_state = "outgoing"
        self._connected.clear()

        try:
            dh = await self._get_dh_config()

            await self._ntg.create_p2p_call(user_id)

            capture = MediaDescription(microphone=self._audio_capture_desc())
            playback = MediaDescription(speaker=self._audio_playback_desc())
            await self._ntg.set_stream_sources(user_id, StreamMode.CAPTURE, capture)
            await self._ntg.set_stream_sources(user_id, StreamMode.PLAYBACK, playback)

            ntg_dh = NtgDhConfig(g=dh.g, p=dh.p, random=dh.random)
            g_a_hash = await self._ntg.init_exchange(user_id, ntg_dh, None)

            protocol = self._tg_protocol()
            entity = await self.client.get_input_entity(user_id)
            log.info("Sending RequestCallRequest...")
            result = await self.client(RequestCallRequest(
                user_id=entity,
                random_id=int.from_bytes(os.urandom(4), "big", signed=True),
                g_a_hash=g_a_hash,
                protocol=protocol,
                video=False,
            ))
            self._active_call = result.phone_call
            self._active_user_id = user_id
            log.info("Request sent (type=%s), waiting for acceptance...",
                     type(result.phone_call).__name__)

            self._confirmed_future = self._tg_loop.create_future()
            accepted = await asyncio.wait_for(self._confirmed_future, timeout=60)
            self._active_call = accepted

            auth = await self._ntg.exchange_keys(user_id, accepted.g_b, 0)

            input_call = InputPhoneCall(
                id=self._active_call.id,
                access_hash=self._active_call.access_hash,
            )
            confirm = await self.client(ConfirmCallRequest(
                peer=input_call,
                g_a=auth.g_a_or_b,
                key_fingerprint=auth.key_fingerprint,
                protocol=protocol,
            ))
            confirmed = confirm.phone_call
            self._active_call = confirmed

            servers = self._parse_servers(confirmed.connections)
            versions = list(confirmed.protocol.library_versions)
            p2p = getattr(confirmed, "p2p_allowed", False)
            log.info("Connecting P2P: %d servers, versions=%s, p2p=%s",
                     len(servers), versions, p2p)
            await self._ntg.connect_p2p(user_id, servers, versions, p2p)

            await self._play_and_hangup(user_id)

        except Exception as e:
            log.error("Call failed: %s", e, exc_info=True)
            try:
                await self._ntg.stop(user_id)
            except Exception:
                pass
            self._cleanup()

    # ---- common helpers ------------------------------------------

    async def _get_dh_config(self):
        from telethon.tl.functions.messages import GetDhConfigRequest
        return await self.client(GetDhConfigRequest(version=0, random_length=256))

    async def _play_and_hangup(self, user_id: int):
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=30)
        except asyncio.TimeoutError:
            log.error("Timed out waiting for connection state")
            await self._hangup(user_id)
            return

        if not self._actually_connected:
            log.error("Connection failed (ICE timeout or closed)")
            await self._hangup(user_id)
            return

        log.info("CONNECTED -- playing fax tone for %d seconds", DURATION)
        await asyncio.sleep(DURATION)
        log.info("Playback complete, hanging up")
        await self._hangup(user_id)

    async def _hangup(self, user_id: int):
        from telethon.tl.functions.phone import DiscardCallRequest
        from telethon.tl.types import (
            InputPhoneCall,
            PhoneCallDiscardReasonHangup,
        )

        if self._active_call:
            try:
                peer = InputPhoneCall(
                    id=self._active_call.id,
                    access_hash=self._active_call.access_hash,
                )
                await self.client(DiscardCallRequest(
                    peer=peer,
                    duration=DURATION,
                    reason=PhoneCallDiscardReasonHangup(),
                    connection_id=0,
                ))
                log.info("Call discarded")
            except Exception as e:
                log.error("Discard error: %s", e)

        try:
            await self._ntg.stop(user_id)
        except Exception:
            pass
        self._cleanup()

    def _cleanup(self):
        self._active_call = None
        self._active_user_id = None
        self._call_state = None
        self._confirmed_future = None
        self._connected.clear()
        self._actually_connected = False

    # ---- main entry point ----------------------------------------

    async def run(self, target_user: int | str | None = None):
        self._tg_loop = asyncio.get_running_loop()

        if not os.path.exists(TONE_FILE):
            generate_fax_tone(TONE_FILE, DURATION)

        await self.client.start()
        me = await self.client.get_me()
        log.info("Logged in: %s (id=%s)", me.first_name, me.id)

        # Register raw handler for call events
        @self.client.on(events.Raw)
        async def _on_raw(event):
            from telethon.tl.types import (
                UpdatePhoneCall,
                UpdatePhoneCallSignalingData,
                PhoneCallAccepted,
                PhoneCall,
                PhoneCallDiscarded,
                PhoneCallRequested,
            )

            if isinstance(event, UpdatePhoneCallSignalingData):
                await self._receive_signaling(event.data)
                return

            if not isinstance(event, UpdatePhoneCall):
                return

            pc = event.phone_call
            log.info("Call update: %s", type(pc).__name__)

            if isinstance(pc, PhoneCallRequested):
                if self._active_call is not None:
                    log.warning("Already in a call, ignoring")
                    return
                asyncio.create_task(self.accept_call(pc))

            elif isinstance(pc, PhoneCallAccepted):
                if (self._call_state == "outgoing"
                        and self._confirmed_future
                        and not self._confirmed_future.done()):
                    self._confirmed_future.set_result(pc)

            elif isinstance(pc, PhoneCall):
                if (self._call_state == "incoming"
                        and self._confirmed_future
                        and not self._confirmed_future.done()):
                    self._confirmed_future.set_result(pc)

            elif isinstance(pc, PhoneCallDiscarded):
                log.info("Call discarded by remote")
                if (self._confirmed_future
                        and not self._confirmed_future.done()):
                    self._confirmed_future.set_exception(
                        Exception("Call discarded by remote"),
                    )
                if self._active_user_id:
                    try:
                        await self._ntg.stop(self._active_user_id)
                    except Exception:
                        pass
                self._cleanup()

        if target_user:
            entity = await self.client.get_input_entity(target_user)
            user_id = entity.user_id if hasattr(entity, "user_id") else int(target_user)
            await self.request_call(user_id)
            log.info("Done. Exiting.")
        else:
            log.info("Waiting for incoming calls... (Ctrl+C to stop)")
            await self.client.run_until_disconnected()


# ------------------------------------------------------------------
# Credential helpers
# ------------------------------------------------------------------

def _load_teepee_credentials() -> tuple[str, str] | None:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from teepee.credentials import get_credentials
        return get_credentials()
    except Exception:
        return None


def _resolve(env_key: str, fallback: str | None, prompt: str) -> str:
    value = os.environ.get(env_key, "") or (fallback or "")
    if not value:
        value = input(prompt)
    return value


# ------------------------------------------------------------------
# Entry
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Teepee Call Test Bot")
    parser.add_argument("--call", metavar="USER",
                        help="Call this user (numeric ID or @username)")
    parser.add_argument("--api-id", type=int, default=0)
    parser.add_argument("--api-hash", default="")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("call_test_bot").setLevel(logging.DEBUG)

    # Resolve API credentials
    teepee_creds = _load_teepee_credentials()
    fallback_id = teepee_creds[0] if teepee_creds else None
    fallback_hash = teepee_creds[1] if teepee_creds else None

    api_id = args.api_id or int(
        _resolve("TELEGRAM_API_ID", fallback_id, "Telegram API ID: ")
    )
    api_hash = args.api_hash or _resolve(
        "TELEGRAM_API_HASH", fallback_hash, "Telegram API hash: "
    )

    target = args.call
    if target and target.lstrip("-").isdigit():
        target = int(target)

    bot = CallTestBot(api_id, api_hash)
    try:
        asyncio.run(bot.run(target_user=target))
    except KeyboardInterrupt:
        log.info("Interrupted")


if __name__ == "__main__":
    main()
