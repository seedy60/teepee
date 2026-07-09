"""Parallel media download for telethon.

Telethon's ``download_media`` uses one MTProto sender per DC and reads the
file sequentially in ~128 KiB chunks for files under 100 MiB, which is
significantly slower than the official native clients (e.g. Unigram via
TDLib) which open several parallel connections per file.

This module spawns N independent MTProto senders to the file's home DC and
fetches disjoint byte ranges concurrently, then assembles them into the
output file. Sender setup happens in parallel too, so on a high-latency
link the per-sender handshake doesn't add up.

The technique is the one used by Tulir's well-known ``FastTelethon`` snippet,
adapted to telethon's current internals.
"""
import asyncio
import logging
import os

from telethon import utils as tutils
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import upload as upload_types

log = logging.getLogger(__name__)

DEFAULT_WORKERS = 8
# 512 KiB is the largest request size telethon's GetFile allows.
PART_SIZE = 512 * 1024
# Files smaller than this fall back to single-stream download — parallelism
# overhead (sender setup, auth export) costs more than it saves.
MIN_PARALLEL_SIZE = 2 * PART_SIZE


class _CdnRedirect(Exception):
    """Raised when the file lives on a CDN — fall back to single-stream."""


def _resolve_location_and_size(message):
    """Return ``(input_location, file_size, dc_id)`` for a telethon message.

    Returns ``(None, None, None)`` if anything is missing — caller should
    fall back to the standard download path.
    """
    try:
        info = tutils._get_file_info(message)
    except (TypeError, ValueError):
        return None, None, None
    return (
        getattr(info, "location", None),
        getattr(info, "size", None),
        getattr(info, "dc_id", None),
    )


async def _create_senders(client, dc_id, count):
    """Return ``count`` connected, authorised senders for ``dc_id``.

    Uses telethon's private ``_create_exported_sender`` serially. Attempts
    to parallelise sender setup were tried earlier (with a custom helper
    that copied ``client._init_request`` so concurrent calls wouldn't step
    on each other) but they didn't pay off -- on some accounts the burst of
    simultaneous ``ExportAuthorization`` calls either rate-limits or just
    silently destabilises, costing more than it saves. The setup time
    increase from serialising N senders is modest (one extra round-trip per
    additional worker) compared to the download time it enables.
    """
    senders = []
    for _ in range(count):
        senders.append(await client._create_exported_sender(dc_id))
    return senders


async def parallel_download(client, message, output_path,
                            workers=DEFAULT_WORKERS, part_size=PART_SIZE):
    """Download ``message``'s media to ``output_path`` via N parallel senders.

    Returns the output path on success. The caller is responsible for any
    fallback handling.
    """
    location, file_size, file_dc = _resolve_location_and_size(message)
    if not location or not file_size:
        raise ValueError("Media location or size unavailable")

    dc_id = file_dc if file_dc is not None else client.session.dc_id

    def _prealloc():
        with open(output_path, "wb") as f:
            if file_size > 0:
                f.truncate(file_size)
    await asyncio.to_thread(_prealloc)

    total_parts = (file_size + part_size - 1) // part_size
    workers = max(1, min(workers, total_parts))

    senders = await _create_senders(client, dc_id, workers)

    try:
        base_parts = total_parts // workers
        remainder = total_parts % workers

        async def _worker(idx, sender):
            start = idx * base_parts + min(idx, remainder)
            count = base_parts + (1 if idx < remainder else 0)
            if count <= 0:
                return
            offset = start * part_size
            f = await asyncio.to_thread(open, output_path, "r+b")
            try:
                await asyncio.to_thread(f.seek, offset)
                for _ in range(count):
                    result = await sender.send(
                        GetFileRequest(location, offset, part_size)
                    )
                    if isinstance(result, upload_types.FileCdnRedirect):
                        raise _CdnRedirect()
                    chunk = result.bytes
                    if not chunk:
                        break
                    await asyncio.to_thread(f.write, chunk)
                    offset += len(chunk)
                    if len(chunk) < part_size:
                        break  # reached end of file
            finally:
                await asyncio.to_thread(f.close)

        await asyncio.gather(*(_worker(i, s) for i, s in enumerate(senders)))
    finally:
        for s in senders:
            try:
                await s.disconnect()
            except Exception:
                pass

    return output_path


def is_parallel_worthwhile(message, output_path):
    """Return True if ``message``/``output_path`` are suitable for the fast
    path: known file size above the threshold and a real file destination
    (not a directory).
    """
    if not output_path:
        return False
    p = str(output_path)
    if p.endswith(os.sep) or p.endswith("/"):
        return False
    _, size, _ = _resolve_location_and_size(message)
    if not size or size < MIN_PARALLEL_SIZE:
        return False
    return True
