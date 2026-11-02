import asyncio
import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import AsyncMock, patch

from gflow_cli.errors import WireFormatError

from flow_cli.flow_original_download import (
    _decode_original_video_payload,
    _request_call,
    _selected_workflow_id,
    download_original_video,
)
from flow_cli.new_flow_video import install_patches


def request_for(rpcid, payload):
    envelope = [[[rpcid, json.dumps(payload), None, "generic"]]]
    post_data = f"f.req={quote(json.dumps(envelope))}&at=redacted&"
    return SimpleNamespace(
        url=f"https://flow.google.com/_/data/batchexecute?rpcids={rpcid}",
        post_data=post_data,
    )


class FlowOriginalDownloadTests(unittest.TestCase):
    def test_project_patch_replaces_preview_downloader(self):
        from gflow_cli.api.transports.migrated_composer import MigratedComposer

        install_patches()

        self.assertIs(MigratedComposer.download, download_original_video)

    def test_observed_media_request_resolves_workflow_id(self):
        request = request_for("as29s", ["workflow-id"])

        self.assertEqual(_request_call(request), ("as29s", ["workflow-id"]))
        self.assertEqual(_selected_workflow_id(request), "workflow-id")

    def test_running_export_waits_for_terminal_payload(self):
        self.assertIsNone(_decode_original_video_payload([2, "", "", 0]))

    def test_terminal_export_decodes_original_mp4(self):
        body = b"\x00\x00\x00\x18ftypisom" + b"high-bitrate-video"
        encoded = base64.b64encode(body).decode("ascii")

        self.assertEqual(
            _decode_original_video_payload([3, "", "", 2, encoded]),
            body,
        )

    def test_terminal_export_rejects_non_mp4_data(self):
        encoded = base64.b64encode(b"not an mp4").decode("ascii")

        with self.assertRaises(WireFormatError):
            _decode_original_video_payload([3, "", "", 2, encoded])

    def test_download_writes_export_bytes_without_fetching_preview_url(self):
        body = b"\x00\x00\x00\x18ftypisom" + b"original"
        record = SimpleNamespace(
            workflow_id="workflow-id",
            media_id="media-id",
            project_id="project-id",
            video_url="https://flow-content.google/video/preview",
        )
        button = object()
        page = SimpleNamespace(request=SimpleNamespace(get=AsyncMock()))

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "flow_cli.flow_original_download._open_matching_video_detail",
                    new=AsyncMock(return_value=button),
                ),
                patch(
                    "flow_cli.flow_original_download._export_original_video",
                    new=AsyncMock(return_value=body),
                ),
            ):
                path = asyncio.run(
                    download_original_video(object(), page, record, Path(temp_dir))
                )

            self.assertEqual(path.read_bytes(), body)
            page.request.get.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
