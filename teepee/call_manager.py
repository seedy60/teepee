import asyncio
import concurrent.futures
import logging
import os
import threading
import time

import wx
from ntgcalls import (
    AudioDescription,
    ConnectionNotFound,
    DhConfig as NtgDhConfig,
    MediaDescription,
    MediaSource,
    NTgCalls,
    RTCServer,
    StreamDevice,
    StreamMode,
    VideoDescription,
)

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

log = logging.getLogger(__name__)


class _NtgBridge:
    """Proxy that runs NTgCalls on a dedicated event loop thread.

    ntgcalls pybind11 async methods return Futures bound to the event loop
    that was active when the NTgCalls object was created.  Telethon uses
    its own loop, so awaiting those Futures directly raises 'attached to a
    different loop'.  This bridge:

    1. Creates NTgCalls *on* a private loop thread so its Futures bind there.
    2. Dispatches every async call to that loop via run_coroutine_threadsafe.
    3. Bridges the result back through a concurrent.futures.Future (which has
       no loop affinity) wrapped into the caller's asyncio loop.
    """

    _ASYNC = frozenset({
        "connect_p2p",
        "create_p2p_call",
        "exchange_keys",
        "init_exchange",
        "mute",
        "send_signaling",
        "set_stream_sources",
        "stop",
        "unmute",
    })

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._ntg = None
        self._ready = threading.Event()
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()
        self._ready.wait()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._ntg = NTgCalls()
        self._ready.set()
        self._loop.run_forever()

    def get_media_devices(self):
        """Enumerate media devices on the bridge thread (COM-safe).

        Returns plain Python dicts so no pybind11 objects cross threads.
        """
        fut = concurrent.futures.Future()
        def _query():
            try:
                devs = NTgCalls.get_media_devices()
                result = {
                    "microphone": [(d.name, d.metadata) for d in devs.microphone],
                    "speaker": [(d.name, d.metadata) for d in devs.speaker],
                    "camera": [(d.name, d.metadata) for d in devs.camera],
                }
                fut.set_result(result)
            except Exception as exc:
                fut.set_exception(exc)
        self._loop.call_soon_threadsafe(_query)
        return fut.result(timeout=5)

    def shutdown(self):
        """Stop all calls, destroy NTgCalls, and stop the bridge loop."""
        if not self._loop.is_running():
            return
        done = threading.Event()

        async def _teardown():
            try:
                if self._ntg is not None:
                    for call in (self._ntg.calls() or []):
                        chat_id = getattr(call, "chat_id", None)
                        if chat_id is not None:
                            try:
                                await self._ntg.stop(chat_id)
                            except Exception:
                                pass
                    self._ntg = None
            except Exception:
                pass
            finally:
                self._loop.stop()
                done.set()

        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(_teardown(), loop=self._loop)
        )
        done.wait(timeout=2)

    def __getattr__(self, name):
        attr = getattr(self._ntg, name)
        if name not in self._ASYNC:
            return attr

        async def _bridged(*args, **kwargs):
            cf = concurrent.futures.Future()

            async def _run():
                try:
                    result = await attr(*args, **kwargs)
                    cf.set_result(result)
                except Exception as exc:
                    cf.set_exception(exc)

            asyncio.run_coroutine_threadsafe(_run(), self._loop)
            return await asyncio.wrap_future(cf)

        return _bridged


class _CameraFeeder:
    """Captures camera frames via OpenCV and feeds them to ntgcalls."""

    def __init__(self, ntg_bridge, width=1280, height=720, fps=30):
        self._ntg = ntg_bridge
        self._width = width
        self._height = height
        self._fps = fps
        self._user_id = None
        self._thread = None
        self._stop_event = threading.Event()

    def start(self, user_id, device_index=0):
        if not HAS_OPENCV:
            log.warning("opencv-python not installed; video capture unavailable")
            return
        self._user_id = user_id
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, args=(device_index,),
            daemon=True, name="CameraFeeder",
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _capture_loop(self, device_index):
        cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log.error("Failed to open camera index %d", device_index)
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)
        interval = 1.0 / self._fps
        log.info("Camera feeder started: %dx%d@%dfps (device %d)",
                 self._width, self._height, self._fps, device_index)
        try:
            while not self._stop_event.is_set():
                t0 = time.monotonic()
                ok, frame = cap.read()
                if not ok:
                    log.warning("Camera read failed, retrying...")
                    time.sleep(interval)
                    continue
                # Resize if camera didn't honour requested resolution
                h, w = frame.shape[:2]
                if w != self._width or h != self._height:
                    frame = cv2.resize(frame, (self._width, self._height))
                # Convert BGR -> I420 (YUV420p)
                yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
                try:
                    self._ntg.send_external_frame(
                        self._user_id, StreamDevice.CAMERA, yuv.tobytes(),
                    )
                except Exception:
                    if self._stop_event.is_set():
                        break
                # Pace to target FPS
                elapsed = time.monotonic() - t0
                if elapsed < interval:
                    self._stop_event.wait(interval - elapsed)
        except Exception as e:
            log.error("Camera feeder error: %s", e)
        finally:
            cap.release()
            log.info("Camera feeder stopped")


class CallManager:
    def __init__(self, telegram_manager, config):
        self.tg = telegram_manager
        self.config = config
        self.active_call = None
        self.on_call_state_changed = None

        self._ntg = _NtgBridge()
        self._active_user_id = None
        self._call_start_time = None
        self._camera_feeder = _CameraFeeder(self._ntg)
        self._video_active = False

        # Pending incoming-call data:  user_id -> {g_a_hash, dh_config}
        self._pending_incoming = {}

        # Future resolved when PhoneCall / PhoneCallAccepted arrives
        self._call_confirmed_future = None

        # Wire ntgcalls signaling callback
        self._ntg.on_signaling(self._on_ntg_signaling)
        self._ntg.on_connection_change(self._on_ntg_connection_change)

    def shutdown(self):
        """Stop the ntgcalls bridge so the process can exit."""
        try:
            self._stop_camera_feeder()
        except Exception:
            pass
        try:
            self._ntg.shutdown()
        except Exception as e:
            log.debug("NTgBridge shutdown error: %s", e)

    # ----------------------------------------------------------
    # Protocol helpers
    # ----------------------------------------------------------

    def _tg_protocol(self, caller_protocol=None):
        from telethon.tl.types import PhoneCallProtocol

        proto = self._ntg.get_protocol()
        our_versions = list(proto.library_versions)
        if caller_protocol is not None:
            caller_versions = list(caller_protocol.library_versions)
            overlap = set(our_versions) & set(caller_versions)
            log.info(
                "Protocol negotiation: ours=%s, caller=%s, overlap=%s, layers=%s-%s",
                our_versions, caller_versions, sorted(overlap) or "NONE",
                caller_protocol.min_layer, caller_protocol.max_layer,
            )
            if not overlap:
                log.warning(
                    "No library_versions overlap! Merging sets so Telegram "
                    "accepts the call, but WebRTC may fail."
                )
                merged = list(dict.fromkeys(our_versions + caller_versions))
            else:
                merged = our_versions
            return PhoneCallProtocol(
                min_layer=caller_protocol.min_layer,
                max_layer=caller_protocol.max_layer,
                udp_p2p=True,
                udp_reflector=True,
                library_versions=merged,
            )
        return PhoneCallProtocol(
            min_layer=proto.min_layer,
            max_layer=proto.max_layer,
            udp_p2p=True,
            udp_reflector=True,
            library_versions=our_versions,
        )

    @staticmethod
    def _parse_servers(connections):
        from telethon.tl.types import PhoneConnection, PhoneConnectionWebrtc

        servers = []
        for c in connections:
            ctype = type(c).__name__
            if isinstance(c, PhoneConnectionWebrtc):
                is_turn = bool(getattr(c, "turn", False))
                is_stun = bool(getattr(c, "stun", False))
                srv = RTCServer(
                    id=c.id,
                    ipv4=c.ip or "",
                    ipv6=c.ipv6 or "",
                    port=c.port,
                    username=c.username,
                    password=c.password,
                    turn=is_turn,
                    stun=is_stun,
                    tcp=False,
                )
            elif isinstance(c, PhoneConnection):
                # Old-style Telegram relay identified by peer_tag
                srv = RTCServer(
                    id=c.id,
                    ipv4=c.ip or "",
                    ipv6=c.ipv6 or "",
                    port=c.port,
                    turn=True,
                    stun=False,
                    tcp=bool(getattr(c, "tcp", False)),
                    peer_tag=c.peer_tag,
                )
            else:
                log.warning("Unknown connection type: %s", ctype)
                continue
            ip = c.ip or c.ipv6 or "?"
            has_tag = bool(getattr(c, "peer_tag", None))
            is_turn = isinstance(c, PhoneConnection) or bool(getattr(c, "turn", False))
            is_stun = not isinstance(c, PhoneConnection) and bool(getattr(c, "stun", False))
            is_tcp = bool(getattr(c, "tcp", False))
            log.debug(
                "Server %s: %s:%s (turn=%s stun=%s tcp=%s peer_tag=%s)",
                ctype, ip, c.port, is_turn, is_stun, is_tcp,
                "yes" if has_tag else "no",
            )
            servers.append(srv)
        return servers

    def _get_default_devices(self):
        devs = self._ntg.get_media_devices()
        mic_meta = ""
        spk_meta = ""
        if devs["microphone"]:
            mic_meta = devs["microphone"][0][1]
        if devs["speaker"]:
            spk_meta = devs["speaker"][0][1]
        log.debug("Default devices: mic=%r spk=%r", mic_meta[:40] if mic_meta else "", spk_meta[:40] if spk_meta else "")
        return mic_meta, spk_meta

    def _get_camera_metadata(self):
        devs = self._ntg.get_media_devices()
        cameras = devs["camera"]
        if not cameras:
            log.debug("No camera devices found")
            return ""
        cam_idx = self.config.get("camera_device_index", -1)
        if 0 <= cam_idx < len(cameras):
            name, meta = cameras[cam_idx]
            log.debug("Camera[%d]: name=%r meta=%r", cam_idx, name, meta[:60] if meta else "")
            return meta
        name, meta = cameras[0]
        log.debug("Camera[0] (default): name=%r meta=%r", name, meta[:60] if meta else "")
        return meta

    def _audio_capture_desc(self, video=False):
        mic_meta, _ = self._get_default_devices()
        kwargs = {
            "microphone": AudioDescription(
                media_source=MediaSource.DEVICE,
                sample_rate=48000,
                channel_count=1,
                input=mic_meta,
            ),
        }
        if video and HAS_OPENCV:
            kwargs["camera"] = VideoDescription(
                media_source=MediaSource.EXTERNAL,
                width=1280,
                height=720,
                fps=30,
                input="",
            )
        return MediaDescription(**kwargs)

    def _audio_playback_desc(self):
        _, spk_meta = self._get_default_devices()
        return MediaDescription(
            speaker=AudioDescription(
                media_source=MediaSource.DEVICE,
                sample_rate=48000,
                channel_count=1,
                input=spk_meta,
            ),
        )

    def _start_camera_feeder(self, user_id):
        cam_idx = self.config.get("camera_device_index", -1)
        device_index = cam_idx if cam_idx >= 0 else 0
        self._camera_feeder.start(user_id, device_index=device_index)

    def _stop_camera_feeder(self):
        self._camera_feeder.stop()
        self._video_active = False

    # ----------------------------------------------------------
    # Signaling bridge
    # ----------------------------------------------------------

    def _on_ntg_signaling(self, user_id, data):
        log.debug("ntgcalls -> Telegram signaling: %d bytes", len(data))
        asyncio.run_coroutine_threadsafe(
            self._send_signaling(user_id, data), self.tg._loop,
        )

    async def _send_signaling(self, user_id, data):
        from telethon.tl.functions.phone import SendSignalingDataRequest

        if self.active_call is None:
            log.warning("Signaling dropped: no active_call")
            return
        from telethon.tl.types import InputPhoneCall

        peer = InputPhoneCall(
            id=self.active_call.id,
            access_hash=self.active_call.access_hash,
        )
        try:
            await self.tg.client(SendSignalingDataRequest(peer=peer, data=data))
            log.debug("Signaling sent to Telegram OK")
        except Exception as e:
            log.error("Failed to send signaling data: %s", e)

    async def receive_signaling(self, data):
        log.debug("Telegram -> ntgcalls signaling: %d bytes", len(data))
        if self._active_user_id is None:
            log.warning("Signaling dropped: no active_user_id")
            return
        try:
            await self._ntg.send_signaling(self._active_user_id, data)
            log.debug("Signaling forwarded to ntgcalls OK")
        except (ConnectionNotFound, Exception) as e:
            log.error("Failed to forward signaling to ntgcalls: %s", e)

    # ----------------------------------------------------------
    # Connection state callback
    # ----------------------------------------------------------

    def _on_ntg_connection_change(self, user_id, network_info):
        from ntgcalls import ConnectionState

        state_name = network_info.state.name if hasattr(network_info.state, "name") else str(network_info.state)
        log.info("NTgCalls connection change: user=%s state=%s", user_id, state_name)
        if network_info.state == ConnectionState.CONNECTED:
            self._call_start_time = time.monotonic()
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "active", None)
        elif network_info.state == ConnectionState.CLOSED:
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "ended", None)
        elif state_name == "TIMEOUT":
            log.error("WebRTC connection timed out (ICE negotiation failed)")
            self._cleanup()
            if self.on_call_state_changed:
                wx.CallAfter(
                    self.on_call_state_changed, "error",
                    "Connection timed out. The caller may need to update their Telegram app.",
                )

    # ----------------------------------------------------------
    # Incoming call: store pending data from PhoneCallRequested
    # ----------------------------------------------------------

    async def prepare_incoming(self, phone_call):
        from telethon.tl.functions.messages import GetDhConfigRequest

        user_id = phone_call.admin_id
        dh_config = await self.tg.client(
            GetDhConfigRequest(version=0, random_length=256)
        )
        self._pending_incoming[user_id] = {
            "g_a_hash": phone_call.g_a_hash,
            "dh_config": dh_config,
            "phone_call": phone_call,
            "protocol": phone_call.protocol,
        }

    # ----------------------------------------------------------
    # Accept an incoming call (full audio)
    # ----------------------------------------------------------

    async def accept_call(self, phone_call, video=False):
        from telethon.tl.functions.phone import AcceptCallRequest
        from telethon.tl.types import InputPhoneCall

        user_id = phone_call.admin_id
        pending = self._pending_incoming.pop(user_id, None)
        if pending is None:
            log.error("No pending incoming call data for user %s", user_id)
            return None

        dh_config = pending["dh_config"]
        g_a_hash = pending["g_a_hash"]
        caller_protocol = pending.get("protocol")

        # If the caller requested video, accept with video when possible
        caller_video = getattr(phone_call, "video", False)
        use_video = video or caller_video

        input_call = InputPhoneCall(
            id=phone_call.id,
            access_hash=phone_call.access_hash,
        )

        try:
            # 1. Create P2P WebRTC connection
            await self._ntg.create_p2p_call(user_id)

            # 2. Set audio (+ optional video) streams
            capture_desc = self._audio_capture_desc(video=use_video)
            try:
                await self._ntg.set_stream_sources(
                    user_id, StreamMode.CAPTURE, capture_desc,
                )
            except Exception as cam_err:
                if use_video:
                    log.warning(
                        "Video capture failed (%s), falling back to audio-only",
                        cam_err,
                    )
                    use_video = False
                    capture_desc = self._audio_capture_desc(video=False)
                    await self._ntg.set_stream_sources(
                        user_id, StreamMode.CAPTURE, capture_desc,
                    )
                else:
                    raise
            await self._ntg.set_stream_sources(
                user_id, StreamMode.PLAYBACK, self._audio_playback_desc(),
            )

            # 3. Init DH exchange (incoming: g_a_hash is not None -> returns g_b)
            ntg_dh = NtgDhConfig(
                g=dh_config.g,
                p=dh_config.p,
                random=dh_config.random,
            )
            g_b = await self._ntg.init_exchange(user_id, ntg_dh, g_a_hash)

            # 4. Send AcceptCallRequest to Telegram
            protocol = self._tg_protocol(caller_protocol)
            log.info("Sending AcceptCallRequest with layers %s-%s...", protocol.min_layer, protocol.max_layer)
            result = await self.tg.client(
                AcceptCallRequest(peer=input_call, g_b=g_b, protocol=protocol)
            )
            self.active_call = result.phone_call
            self._active_user_id = user_id
            log.info(
                "Call accepted (id=%s, type=%s)",
                result.phone_call.id,
                type(result.phone_call).__name__,
            )

            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "connecting", result)

            # 5. Wait for PhoneCall (confirmed) via _call_confirmed_future
            self._call_confirmed_future = asyncio.get_event_loop().create_future()
            confirmed = await asyncio.wait_for(
                self._call_confirmed_future, timeout=30,
            )

            # 6. Exchange keys
            auth_params = await self._ntg.exchange_keys(
                user_id, confirmed.g_a_or_b, confirmed.key_fingerprint,
            )

            # 7. Connect P2P with relay servers
            servers = self._parse_servers(confirmed.connections)
            lib_versions = list(confirmed.protocol.library_versions)
            p2p_allowed = getattr(confirmed, "p2p_allowed", False)
            log.info(
                "Connecting P2P: %d servers, lib_versions=%s, p2p_allowed=%s",
                len(servers), lib_versions, p2p_allowed,
            )
            await self._ntg.connect_p2p(user_id, servers, lib_versions, p2p_allowed)

            if use_video:
                self._video_active = True
                self._start_camera_feeder(user_id)

            log.info("P2P connect dispatched, waiting for CONNECTED state...")
            return result

        except asyncio.TimeoutError:
            log.error("Timed out waiting for call confirmation")
            try:
                await self._ntg.stop(user_id)
            except ConnectionNotFound:
                pass
            await self._discard_by_peer(input_call)
            self._cleanup()
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "error", "Timed out")
            return None
        except Exception as e:
            log.error("Failed to accept call: %s", e, exc_info=True)
            try:
                await self._ntg.stop(user_id)
            except (ConnectionNotFound, Exception):
                pass
            self._cleanup()
            msg = str(e)
            if "CALL_PROTOCOL_COMPAT_LAYER_INVALID" in msg:
                msg = (
                    "The caller's Telegram app uses an incompatible call "
                    "protocol. They need to update to a newer version."
                )
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "error", msg)
            return None

    # ----------------------------------------------------------
    # Outgoing call
    # ----------------------------------------------------------

    async def request_call(self, user_id, video=False):
        from telethon.tl.functions.phone import (
            ConfirmCallRequest,
            RequestCallRequest,
        )
        from telethon.tl.types import InputPhoneCall
        from telethon.tl.functions.messages import GetDhConfigRequest

        # Ensure user_id is a plain int (callers may pass a User object)
        if hasattr(user_id, "id"):
            user_id = user_id.id

        try:
            dh_config = await self.tg.client(
                GetDhConfigRequest(version=0, random_length=256)
            )

            # 1. Create P2P WebRTC connection
            await self._ntg.create_p2p_call(user_id)

            # 2. Set audio (+ optional video) streams
            capture_desc = self._audio_capture_desc(video=video)
            try:
                await self._ntg.set_stream_sources(
                    user_id, StreamMode.CAPTURE, capture_desc,
                )
            except Exception as cam_err:
                if video:
                    log.warning(
                        "Video capture failed (%s), falling back to audio-only",
                        cam_err,
                    )
                    video = False
                    capture_desc = self._audio_capture_desc(video=False)
                    await self._ntg.set_stream_sources(
                        user_id, StreamMode.CAPTURE, capture_desc,
                    )
                else:
                    raise
            await self._ntg.set_stream_sources(
                user_id, StreamMode.PLAYBACK, self._audio_playback_desc(),
            )

            # 3. Init DH exchange (outgoing: g_a_hash is None -> returns g_a_hash)
            ntg_dh = NtgDhConfig(
                g=dh_config.g,
                p=dh_config.p,
                random=dh_config.random,
            )
            g_a_hash = await self._ntg.init_exchange(user_id, ntg_dh, None)

            # 4. Send RequestCallRequest
            protocol = self._tg_protocol()
            result = await self.tg.client(
                RequestCallRequest(
                    user_id=user_id,
                    random_id=int.from_bytes(os.urandom(4), "big", signed=True),
                    g_a_hash=g_a_hash,
                    protocol=protocol,
                    video=video,
                )
            )
            self.active_call = result.phone_call
            self._active_user_id = user_id

            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "calling", result)

            # 5. Wait for PhoneCallAccepted
            self._call_confirmed_future = asyncio.get_event_loop().create_future()
            accepted = await asyncio.wait_for(
                self._call_confirmed_future, timeout=60,
            )

            # 6. Exchange keys (fingerprint is 0 for outgoing; ntgcalls computes it)
            auth_params = await self._ntg.exchange_keys(
                user_id, accepted.g_b, 0,
            )

            # 7. Confirm call
            input_call = InputPhoneCall(
                id=self.active_call.id,
                access_hash=self.active_call.access_hash,
            )
            confirm_result = await self.tg.client(
                ConfirmCallRequest(
                    peer=input_call,
                    g_a=auth_params.g_a_or_b,
                    key_fingerprint=auth_params.key_fingerprint,
                    protocol=protocol,
                )
            )
            confirmed_call = confirm_result.phone_call
            self.active_call = confirmed_call

            # 8. Connect P2P
            servers = self._parse_servers(confirmed_call.connections)
            lib_versions = list(confirmed_call.protocol.library_versions)
            p2p_allowed = getattr(confirmed_call, "p2p_allowed", False)
            await self._ntg.connect_p2p(user_id, servers, lib_versions, p2p_allowed)

            if video:
                self._video_active = True
                self._start_camera_feeder(user_id)

            self._call_start_time = time.monotonic()
            log.info("P2P audio connection established for outgoing call")
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "active", None)
            return result

        except asyncio.TimeoutError:
            log.error("Timed out waiting for call to be accepted")
            try:
                await self._ntg.stop(user_id)
            except ConnectionNotFound:
                pass
            if self.active_call:
                input_call = InputPhoneCall(
                    id=self.active_call.id,
                    access_hash=self.active_call.access_hash,
                )
                await self._discard_by_peer(input_call, missed=True)
            self._cleanup()
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "ended", None)
            return None
        except Exception as e:
            log.error("Failed to request call: %s", e, exc_info=True)
            try:
                await self._ntg.stop(user_id)
            except (ConnectionNotFound, Exception):
                pass
            self._cleanup()
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "error", str(e))
            return None

    # ----------------------------------------------------------
    # Call update handler (fed from telegram_manager Raw handler)
    # ----------------------------------------------------------

    async def handle_call_update(self, phone_call):
        from telethon.tl.types import (
            PhoneCall,
            PhoneCallAccepted,
            PhoneCallDiscarded,
        )

        if isinstance(phone_call, PhoneCallAccepted):
            # Outgoing call was accepted by remote
            if self._call_confirmed_future and not self._call_confirmed_future.done():
                self._call_confirmed_future.set_result(phone_call)

        elif isinstance(phone_call, PhoneCall):
            # Incoming call confirmed by caller
            self.active_call = phone_call
            if self._call_confirmed_future and not self._call_confirmed_future.done():
                self._call_confirmed_future.set_result(phone_call)

        elif isinstance(phone_call, PhoneCallDiscarded):
            log.info("Call discarded by remote")
            if self._call_confirmed_future and not self._call_confirmed_future.done():
                self._call_confirmed_future.set_exception(
                    Exception("Call discarded by remote")
                )
            if self._active_user_id is not None:
                try:
                    await self._ntg.stop(self._active_user_id)
                except (ConnectionNotFound, Exception):
                    pass
            self._cleanup()
            if self.on_call_state_changed:
                wx.CallAfter(self.on_call_state_changed, "ended", None)

    # ----------------------------------------------------------
    # Hang up / Discard
    # ----------------------------------------------------------

    async def discard_call(self):
        if not self.active_call:
            return
        from telethon.tl.types import InputPhoneCall

        input_call = InputPhoneCall(
            id=self.active_call.id,
            access_hash=self.active_call.access_hash,
        )
        if self._active_user_id is not None:
            try:
                await self._ntg.stop(self._active_user_id)
            except (ConnectionNotFound, Exception):
                pass
        await self._discard_by_peer(input_call)
        self._cleanup()
        if self.on_call_state_changed:
            wx.CallAfter(self.on_call_state_changed, "ended", None)

    async def _discard_by_peer(self, input_call, missed=False):
        from telethon.tl.functions.phone import DiscardCallRequest
        from telethon.tl.types import (
            PhoneCallDiscardReasonHangup,
            PhoneCallDiscardReasonMissed,
        )

        reason = PhoneCallDiscardReasonMissed() if missed else PhoneCallDiscardReasonHangup()
        duration = 0
        if self._call_start_time is not None:
            duration = int(time.monotonic() - self._call_start_time)
        try:
            await self.tg.client(
                DiscardCallRequest(
                    peer=input_call,
                    duration=duration,
                    reason=reason,
                    connection_id=0,
                )
            )
        except Exception as e:
            log.error("Failed to discard call: %s", e)

    def _cleanup(self):
        self._stop_camera_feeder()
        self.active_call = None
        self._active_user_id = None
        self._call_start_time = None
        self._call_confirmed_future = None
        self._pending_incoming.clear()

    # ----------------------------------------------------------
    # Mute / Unmute
    # ----------------------------------------------------------

    async def mute(self):
        if self._active_user_id is not None:
            await self._ntg.mute(self._active_user_id)

    async def unmute(self):
        if self._active_user_id is not None:
            await self._ntg.unmute(self._active_user_id)

    # ----------------------------------------------------------
    # Properties
    # ----------------------------------------------------------

    @property
    def in_call(self):
        return self.active_call is not None
