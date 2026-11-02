"""Download Flow videos through the migrated UI's original-file export path."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from gflow_cli.api.transports.batchexecute import parse_frames
from gflow_cli.errors import (
    ReferenceNotFoundError,
    TransportTimeoutError,
    UiSelectorDriftError,
    WireFormatError,
)

MEDIA_DETAILS_RPC = "as29s"
ORIGINAL_EXPORT_RPC = "GjQLTd"
ORIGINAL_EXPORT_STATUS_RPC = "IxdSwd"
ORIGINAL_EXPORT_TIMEOUT_S = 180.0
VIDEO_TILE = "flow-video-tile"
SUPPRESS_BLOB_DOWNLOAD = """() => {
    const key = '__flowCliOriginalAnchorClick';
    if (!window[key]) {
        window[key] = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function() {
            if (this.hasAttribute('download') && this.href.startsWith('blob:')) {
                return;
            }
            return window[key].call(this);
        };
    }
}"""
RESTORE_BLOB_DOWNLOAD = """() => {
    const key = '__flowCliOriginalAnchorClick';
    if (window[key]) {
        HTMLAnchorElement.prototype.click = window[key];
        delete window[key];
    }
}"""


def _rpcid(url: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get("rpcids", [])
    return values[0] if values else None


def _request_call(request: Any) -> tuple[str, Any] | None:
    """Decode one batchexecute request without retaining auth/query values."""
    try:
        form = parse_qs(str(request.post_data or ""), keep_blank_values=True)
        envelope = json.loads(form["f.req"][0])
        call = envelope[0][0]
        if not isinstance(call, list) or len(call) < 2 or not isinstance(call[0], str):
            return None
        payload = json.loads(call[1]) if isinstance(call[1], str) else call[1]
        return call[0], payload
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _selected_workflow_id(request: Any) -> str | None:
    if _rpcid(str(getattr(request, "url", ""))) != MEDIA_DETAILS_RPC:
        return None
    call = _request_call(request)
    if call is None or call[0] != MEDIA_DETAILS_RPC:
        return None
    payload = call[1]
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return payload[0]
    return None


def _contains_string(value: Any, expected: str) -> bool:
    if value == expected:
        return True
    if isinstance(value, list):
        return any(_contains_string(item, expected) for item in value)
    if isinstance(value, dict):
        return any(_contains_string(item, expected) for item in value.values())
    return False


def _decode_original_video_payload(payload: Any) -> bytes | None:
    """Return original MP4 bytes from a terminal IxdSwd payload."""
    if not isinstance(payload, list) or not payload:
        raise WireFormatError(
            detail="migrated host: original video export returned a malformed status",
            route=f"batchexecute:{ORIGINAL_EXPORT_STATUS_RPC}",
        )
    status = payload[0]
    if status == 2:
        return None
    if status != 3:
        raise WireFormatError(
            detail=f"migrated host: original video export failed with status {status!r}",
            route=f"batchexecute:{ORIGINAL_EXPORT_STATUS_RPC}",
        )
    encoded = payload[4] if len(payload) > 4 else None
    if not isinstance(encoded, str) or not encoded:
        raise WireFormatError(
            detail="migrated host: completed original video export contained no MP4 data",
            route=f"batchexecute:{ORIGINAL_EXPORT_STATUS_RPC}",
        )
    try:
        body = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise WireFormatError(
            detail="migrated host: original video export contained invalid base64 data",
            route=f"batchexecute:{ORIGINAL_EXPORT_STATUS_RPC}",
        ) from error
    if body[4:8] != b"ftyp":
        raise WireFormatError(
            detail="migrated host: original video export did not contain an MP4",
            route=f"batchexecute:{ORIGINAL_EXPORT_STATUS_RPC}",
        )
    return body


async def _open_matching_video_detail(page: Any, record: Any) -> Any:
    """Open the exact generated tile, verified by Flow's media-details request."""
    project_url = f"https://flow.google.com/project/{record.project_id}"
    await page.goto(project_url, wait_until="domcontentloaded", timeout=60_000)
    tiles = page.locator(VIDEO_TILE)
    try:
        await tiles.first.wait_for(state="visible", timeout=15_000)
    except Exception as error:
        raise ReferenceNotFoundError(
            detail="migrated host: no completed video tile was visible for original download"
        ) from error
    await page.wait_for_timeout(500)

    visible_count = await tiles.count()
    for index in range(visible_count):
        if index:
            await page.goto(project_url, wait_until="domcontentloaded", timeout=60_000)
            tiles = page.locator(VIDEO_TILE)
            await tiles.first.wait_for(state="visible", timeout=15_000)

        selected: asyncio.Future[str | None] = (
            asyncio.get_running_loop().create_future()
        )

        def on_request(request: Any) -> None:
            workflow_id = _selected_workflow_id(request)
            if workflow_id is not None and not selected.done():
                selected.set_result(workflow_id)

        page.on("request", on_request)
        try:
            await tiles.nth(index).click(force=True, position={"x": 20, "y": 20})
            try:
                workflow_id = await asyncio.wait_for(selected, timeout=10.0)
            except TimeoutError:
                workflow_id = None
        finally:
            page.remove_listener("request", on_request)

        if workflow_id == record.workflow_id:
            from gflow_cli.api.transports import migrated_composer as migrated

            download = page.locator("button:visible").filter(
                has=migrated._ligature(page, "download")
            )
            if await download.count() != 1:
                raise UiSelectorDriftError(
                    detail=(
                        "migrated host: the matching video detail did not expose exactly "
                        "one original download button"
                    )
                )
            return download.first

    raise ReferenceNotFoundError(
        detail=(
            "migrated host: could not match a visible video tile to completed workflow "
            f"{record.workflow_id}; refusing to download another result"
        )
    )


async def _export_original_video(
    page: Any,
    download_button: Any,
    workflow_id: str,
) -> bytes:
    loop = asyncio.get_running_loop()
    body_future: asyncio.Future[bytes] = loop.create_future()
    export_request: asyncio.Future[bool] = loop.create_future()
    response_tasks: set[asyncio.Task[None]] = set()

    def on_request(request: Any) -> None:
        if _rpcid(str(getattr(request, "url", ""))) != ORIGINAL_EXPORT_RPC:
            return
        call = _request_call(request)
        matches = bool(
            call is not None
            and call[0] == ORIGINAL_EXPORT_RPC
            and _contains_string(call[1], workflow_id)
        )
        if not export_request.done():
            export_request.set_result(matches)
        if not matches and not body_future.done():
            body_future.set_exception(
                WireFormatError(
                    detail=(
                        "migrated host: original download targeted a different video; "
                        "refusing the result"
                    ),
                    route=f"batchexecute:{ORIGINAL_EXPORT_RPC}",
                )
            )

    async def capture_response(response: Any) -> None:
        if _rpcid(str(getattr(response, "url", ""))) != ORIGINAL_EXPORT_STATUS_RPC:
            return
        try:
            text = await response.text()
            for rpcid, payload in parse_frames(text):
                if rpcid != ORIGINAL_EXPORT_STATUS_RPC:
                    continue
                body = _decode_original_video_payload(payload)
                if body is not None and not body_future.done():
                    body_future.set_result(body)
                    return
        except Exception as error:
            if not body_future.done():
                body_future.set_exception(error)

    def on_response(response: Any) -> None:
        task = asyncio.create_task(capture_response(response))
        response_tasks.add(task)
        task.add_done_callback(response_tasks.discard)

    page.on("request", on_request)
    page.on("response", on_response)
    try:
        await page.evaluate(SUPPRESS_BLOB_DOWNLOAD)
        await download_button.click(timeout=5_000)
        try:
            matched = await asyncio.wait_for(export_request, timeout=10.0)
        except TimeoutError as error:
            raise UiSelectorDriftError(
                detail="migrated host: original download button started no export request"
            ) from error
        if not matched:
            return await body_future
        try:
            return await asyncio.wait_for(
                body_future,
                timeout=ORIGINAL_EXPORT_TIMEOUT_S,
            )
        except TimeoutError as error:
            raise TransportTimeoutError(
                detail=(
                    "migrated host: original 720p video export did not finish within "
                    f"{ORIGINAL_EXPORT_TIMEOUT_S:.0f}s"
                )
            ) from error
    finally:
        try:
            await page.evaluate(RESTORE_BLOB_DOWNLOAD)
        except Exception:
            pass
        page.remove_listener("request", on_request)
        page.remove_listener("response", on_response)
        if response_tasks:
            await asyncio.gather(*response_tasks, return_exceptions=True)


async def download_original_video(
    self: Any,
    page: Any,
    record: Any,
    out_dir: Path | None,
) -> Path:
    """Use Flow's detail-view download action and never fall back to preview media."""
    del self
    button = await _open_matching_video_detail(page, record)
    body = await _export_original_video(page, button, record.workflow_id)
    target_dir = out_dir or Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{record.media_id}.mp4"
    path.write_bytes(body)
    return path
