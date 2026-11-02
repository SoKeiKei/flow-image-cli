import asyncio
import os
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner
from gflow_cli.api.video import Aspect, GenerateVideoRequest, Mode, VideoModel

from flow_cli.new_flow_video import (
    AttachedInputs,
    SettingsSnapshot,
    VideoConfigurationMismatch,
    _count_from_label,
    _duration_from_label,
    _find_asset_option,
    _attach_local_inputs,
    _resolution_from_label,
    _run_r2v_with_project_references,
    _run_video,
    _unported_form,
    _verify_pre_submit,
    expected_submode,
    install_patches,
    requested_project_reference_names,
    requested_resolution,
    validate_settings_snapshot,
)


class _ChipLocator:
    def __init__(self, page):
        self.page = page

    async def count(self):
        return self.page.chips


class _FakePage:
    def __init__(self):
        self.chips = 0

    def locator(self, _selector):
        return _ChipLocator(self)


class _FakeOption:
    def __init__(self, page):
        self.page = page

    async def click(self, timeout):
        self.page.chips += 1


class _FakePicker:
    async def wait_for(self, *, state, timeout):
        return None


class _PromptEditor:
    def __init__(self, value):
        self.value = value

    @property
    def first(self):
        return self

    async def count(self):
        return 1

    async def text_content(self):
        return self.value


def snapshot_for(request, resolution):
    model_labels = {
        VideoModel.OMNI_FLASH: "Omni 1.1 Flash",
        VideoModel.VEO_3_1_LITE: "Veo 3.1 - Lite",
        VideoModel.VEO_3_1_FAST: "Veo 3.1 - Fast",
        VideoModel.VEO_3_1_QUALITY: "Veo 3.1 - Quality",
    }
    return SettingsSnapshot(
        mode="video",
        submode=expected_submode(request.mode),
        model=model_labels[request.model],
        aspect=request.aspect.value,
        resolution=resolution,
        duration=request.duration,
        count=request.count,
    )


class NewFlowVideoContractTests(unittest.TestCase):
    def test_pre_submit_prompt_mismatch_stops(self):
        request = GenerateVideoRequest(
            prompt="用户原文",
            mode=Mode.T2V,
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.LANDSCAPE,
            duration=4,
            count=1,
        )
        composer = SimpleNamespace(
            _open_pane=AsyncMock(),
            _close_pane=AsyncMock(),
        )
        page = SimpleNamespace(locator=lambda _selector: _PromptEditor("网页中被改写"))

        with patch(
            "flow_cli.new_flow_video._collect_settings_snapshot",
            new=AsyncMock(return_value=snapshot_for(request, "720p")),
        ):
            with self.assertRaises(VideoConfigurationMismatch):
                asyncio.run(
                    _verify_pre_submit(
                        composer,
                        page,
                        request,
                        AttachedInputs((), 0),
                    )
                )

    def test_pre_submit_mismatch_never_calls_submit(self):
        request = GenerateVideoRequest(
            prompt="提交前停止",
            mode=Mode.R2V,
            reference_images=(Path("ref.png"),),
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.LANDSCAPE,
            duration=4,
            count=1,
        )
        composer = SimpleNamespace(
            ensure_editor=AsyncMock(),
            apply_video_settings=AsyncMock(),
            send_prompt=AsyncMock(),
            submit_and_observe=AsyncMock(),
        )
        page = SimpleNamespace(url="https://flow.google.com/project/project-id")

        with (
            patch(
                "gflow_cli.api.transports.migrated_composer.MigratedComposer",
                return_value=composer,
            ),
            patch(
                "flow_cli.new_flow_video._attach_local_inputs",
                new=AsyncMock(return_value=AttachedInputs(("media-id",), 1)),
            ),
            patch(
                "flow_cli.new_flow_video._verify_pre_submit",
                new=AsyncMock(side_effect=VideoConfigurationMismatch("count mismatch")),
            ),
        ):
            with self.assertRaises(VideoConfigurationMismatch):
                asyncio.run(
                    _run_video(
                        page,
                        request,
                        project_id="project-id",
                        out_dir=None,
                        poll_timeout_s=1,
                        download=False,
                        on_started=None,
                    )
                )

        composer.submit_and_observe.assert_not_awaited()

    def test_single_and_multiple_materials_are_attached_as_r2v_chips(self):
        for refs in ((Path("one.png"),), (Path("one.png"), Path("two.png"))):
            with self.subTest(reference_count=len(refs)):
                page = _FakePage()
                composer = SimpleNamespace(
                    _upload_via_toolbar=AsyncMock(
                        side_effect=[f"media-{index}" for index in range(len(refs))]
                    )
                )
                request = GenerateVideoRequest(
                    prompt="素材",
                    mode=Mode.R2V,
                    reference_images=refs,
                    model=VideoModel.OMNI_FLASH,
                    aspect=Aspect.LANDSCAPE,
                    duration=4,
                    count=1,
                )

                async def attach_material(_page, **_kwargs):
                    page.chips += 1

                with (
                    patch("gflow_cli.api.client.validate_image_file", new=AsyncMock()),
                    patch("flow_cli.new_flow_video.shutil.copyfile"),
                    patch(
                        "flow_cli.new_flow_video._attach_one_material",
                        new=AsyncMock(side_effect=attach_material),
                    ) as attach,
                ):
                    result = asyncio.run(
                        _attach_local_inputs(composer, page, request, "project-id")
                    )

                self.assertEqual(result.chip_count, len(refs))
                self.assertEqual(len(result.media_ids), len(refs))
                self.assertEqual(attach.await_count, len(refs))

    def test_single_and_multiple_project_materials_are_selected_without_upload(self):
        for names in (("首张横版场景图",), ("角色甲", "雨夜街道")):
            with self.subTest(reference_count=len(names)):
                page = _FakePage()
                composer = SimpleNamespace(_upload_via_toolbar=AsyncMock())
                request = GenerateVideoRequest(
                    prompt="复用项目素材",
                    mode=Mode.R2V,
                    ref_names=names,
                    model=VideoModel.OMNI_FLASH,
                    aspect=Aspect.LANDSCAPE,
                    duration=10,
                    count=2,
                )

                async def attach_material(_page, **_kwargs):
                    page.chips += 1

                with patch(
                    "flow_cli.new_flow_video._attach_one_material",
                    new=AsyncMock(side_effect=attach_material),
                ) as attach:
                    result = asyncio.run(
                        _attach_local_inputs(composer, page, request, "project-id")
                    )

                self.assertEqual(result.chip_count, len(names))
                self.assertEqual(result.media_ids, ())
                self.assertEqual(result.project_reference_names, names)
                self.assertEqual(attach.await_count, len(names))
                composer._upload_via_toolbar.assert_not_awaited()

    def test_local_and_project_materials_can_be_mixed(self):
        page = _FakePage()
        composer = SimpleNamespace(
            _upload_via_toolbar=AsyncMock(return_value="local-id")
        )
        request = GenerateVideoRequest(
            prompt="混合素材",
            mode=Mode.R2V,
            reference_images=(Path("local.png"),),
            ref_names=("项目场景",),
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.PORTRAIT,
            duration=6,
            count=3,
        )

        async def attach_material(_page, **_kwargs):
            page.chips += 1

        with (
            patch("gflow_cli.api.client.validate_image_file", new=AsyncMock()),
            patch("flow_cli.new_flow_video.shutil.copyfile"),
            patch(
                "flow_cli.new_flow_video._attach_one_material",
                new=AsyncMock(side_effect=attach_material),
            ),
        ):
            result = asyncio.run(
                _attach_local_inputs(composer, page, request, "project-id")
            )

        self.assertEqual(result.media_ids, ("local-id",))
        self.assertEqual(result.project_reference_names, ("项目场景",))
        self.assertEqual(result.chip_count, 2)

    def test_duplicate_project_material_title_stops_as_ambiguous(self):
        from gflow_cli.api.transports import migrated_composer as migrated
        from gflow_cli.errors import ReferenceNotFoundError

        search = MagicMock()
        search.first.fill = AsyncMock()
        options = MagicMock()
        options.first.wait_for = AsyncMock()
        options.count = AsyncMock(return_value=2)
        option_base = MagicMock()
        option_base.filter.return_value = options
        option_base.all_text_contents = AsyncMock(return_value=["重复标题", "重复标题"])
        picker = MagicMock()
        picker.locator.side_effect = lambda selector: (
            search if selector == migrated.PICKER_SEARCH else option_base
        )
        exact_title = MagicMock()
        title_base = MagicMock()
        title_base.filter.return_value = exact_title
        page = MagicMock()
        page.locator.return_value = title_base

        with self.assertRaises(ReferenceNotFoundError) as caught:
            asyncio.run(
                _find_asset_option(
                    page,
                    picker,
                    name="重复标题",
                    media_id="existing project material",
                )
            )

        self.assertIn("ambiguous", caught.exception.detail)

    def test_first_and_first_last_frames_fill_only_frame_slots(self):
        for end_image in (None, Path("last.png")):
            with self.subTest(has_end=end_image is not None):
                page = _FakePage()
                composer = SimpleNamespace(
                    _upload_via_toolbar=AsyncMock(side_effect=["first-id", "last-id"]),
                    _open_frame_picker=AsyncMock(return_value=_FakePicker()),
                )
                request = GenerateVideoRequest(
                    prompt="帧",
                    mode=Mode.I2V,
                    start_image=Path("first.png"),
                    end_image=end_image,
                    model=VideoModel.OMNI_FLASH,
                    aspect=Aspect.PORTRAIT,
                    duration=4,
                    count=1,
                )

                async def find_option(*_args, **_kwargs):
                    return _FakeOption(page)

                with (
                    patch("gflow_cli.api.client.validate_image_file", new=AsyncMock()),
                    patch("flow_cli.new_flow_video.shutil.copyfile"),
                    patch(
                        "flow_cli.new_flow_video._find_asset_option",
                        new=AsyncMock(side_effect=find_option),
                    ) as find,
                ):
                    result = asyncio.run(
                        _attach_local_inputs(composer, page, request, "project-id")
                    )

                expected = 2 if end_image else 1
                self.assertEqual(result.chip_count, expected)
                self.assertEqual(len(result.media_ids), expected)
                self.assertEqual(find.await_count, expected)

    def test_single_reference_uses_materials_with_independent_output_aspect(self):
        request = GenerateVideoRequest(
            prompt="单张素材",
            mode=Mode.R2V,
            reference_images=(Path("portrait-source.png"),),
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.LANDSCAPE,
            duration=10,
            count=2,
        )

        self.assertEqual(expected_submode(request.mode), "materials")
        self.assertIsNone(_unported_form(request))
        self.assertEqual(request.aspect, Aspect.LANDSCAPE)
        validate_settings_snapshot(request, "720p", snapshot_for(request, "720p"))

    def test_project_reference_uses_materials_with_independent_output_aspect(self):
        request = GenerateVideoRequest(
            prompt="项目素材",
            mode=Mode.R2V,
            ref_names=("横版源图",),
            model=VideoModel.VEO_3_1_FAST,
            aspect=Aspect.PORTRAIT,
            duration=8,
            count=1,
        )

        self.assertEqual(expected_submode(request.mode), "materials")
        self.assertIsNone(_unported_form(request))
        validate_settings_snapshot(request, "360p", snapshot_for(request, "360p"))

    def test_multiple_references_use_materials_with_parameter_combination(self):
        request = GenerateVideoRequest(
            prompt="多张素材",
            mode=Mode.R2V,
            reference_images=(Path("wide.png"), Path("square.png")),
            model=VideoModel.VEO_3_1_LITE,
            aspect=Aspect.PORTRAIT,
            duration=6,
            count=3,
        )

        self.assertEqual(expected_submode(request.mode), "materials")
        self.assertIsNone(_unported_form(request))
        validate_settings_snapshot(request, "360p", snapshot_for(request, "360p"))

    def test_explicit_first_frame_uses_frames(self):
        request = GenerateVideoRequest(
            prompt="首帧",
            mode=Mode.I2V,
            start_image=Path("first.png"),
            model=VideoModel.VEO_3_1_FAST,
            aspect=Aspect.LANDSCAPE,
            duration=4,
            count=1,
        )

        self.assertEqual(expected_submode(request.mode), "frames")
        self.assertIsNone(_unported_form(request))
        validate_settings_snapshot(request, "720p", snapshot_for(request, "720p"))

    def test_explicit_first_and_last_frames_use_frames(self):
        request = GenerateVideoRequest(
            prompt="首尾帧",
            mode=Mode.I2V,
            start_image=Path("first.png"),
            end_image=Path("last.png"),
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.PORTRAIT,
            duration=10,
            count=4,
        )

        self.assertEqual(expected_submode(request.mode), "frames")
        self.assertIsNone(_unported_form(request))
        validate_settings_snapshot(request, "360p", snapshot_for(request, "360p"))

    def test_readback_mismatch_stops_instead_of_changing_route(self):
        request = GenerateVideoRequest(
            prompt="素材",
            mode=Mode.R2V,
            reference_images=(Path("ref.png"),),
            model=VideoModel.OMNI_FLASH,
            aspect=Aspect.LANDSCAPE,
            duration=10,
            count=2,
        )
        wrong = SettingsSnapshot(
            mode="video",
            submode="frames",
            model="Veo 3.1 - Lite",
            aspect="portrait",
            resolution="360p",
            duration=8,
            count=1,
        )

        with self.assertRaises(VideoConfigurationMismatch) as caught:
            validate_settings_snapshot(request, "720p", wrong)

        detail = caught.exception.detail
        for field in ("submode", "model", "aspect", "resolution", "duration", "count"):
            self.assertIn(field, detail)

    def test_bilingual_duration_and_control_labels(self):
        self.assertEqual(_duration_from_label("10s"), 10)
        self.assertEqual(_duration_from_label("10 秒"), 10)
        self.assertEqual(_duration_from_label("10 seconds"), 10)
        self.assertEqual(_duration_from_label(" 6  秒 "), 6)
        self.assertEqual(_count_from_label("x3"), 3)
        self.assertEqual(_count_from_label("3x"), 3)
        self.assertEqual(_resolution_from_label(" 720P "), "720p")
        self.assertEqual(_resolution_from_label("360pinfo"), "360p")

    def test_resolution_is_explicit_and_validated(self):
        with patch.dict(os.environ, {"FLOW_CLI_VIDEO_RESOLUTION": "360P"}):
            self.assertEqual(requested_resolution(), "360p")
        with patch.dict(os.environ, {"FLOW_CLI_VIDEO_RESOLUTION": "1080p"}):
            with self.assertRaises(ValueError):
                requested_resolution()

    def test_cli_exposes_resolution_and_deterministic_defaults(self):
        install_patches()
        from gflow_cli.cli import main

        result = CliRunner().invoke(main, ["video", "r2v", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--resolution [360p|720p]", result.output)
        self.assertIn("[default: 720p]", result.output)
        self.assertIn("[default: 4]", result.output)
        self.assertIn("required", result.output.lower())

    def test_cli_accepts_project_material_without_local_file(self):
        install_patches()
        from gflow_cli.cli import main

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("gflow_cli.cli_video._resolve_profile", return_value="default"),
            patch("gflow_cli.cli_video._make_provider_dir", return_value=Path(".")),
            patch("gflow_cli.cli_video.run_with_handlers") as run,
        ):
            result = CliRunner().invoke(
                main,
                [
                    "video",
                    "r2v",
                    "沿用现有场景",
                    "--project-ref",
                    "首张横版场景图",
                    "--model",
                    "omni-flash",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(requested_project_reference_names(), ("首张横版场景图",))
            run.assert_called_once()

    def test_r2v_runner_carries_project_materials_into_request(self):
        with (
            patch.dict(
                os.environ,
                {"FLOW_CLI_PROJECT_REFERENCE_NAMES": '["项目场景", "项目角色"]'},
            ),
            patch(
                "gflow_cli.cli_video._generate_and_report", new=AsyncMock()
            ) as generate,
        ):
            asyncio.run(
                _run_r2v_with_project_references(
                    profile_name="default",
                    profile_dir=Path("."),
                    prompt="混合引用",
                    refs=("local.png",),
                    aspect="16:9",
                    out_dir=None,
                    model="omni-flash",
                    duration=10,
                    count=2,
                    project_id="project-id",
                )
            )

        request = generate.await_args.args[0]
        self.assertEqual(request.reference_images, (Path("local.png"),))
        self.assertEqual(request.ref_names, ("项目场景", "项目角色"))
        self.assertEqual(request.aspect, Aspect.LANDSCAPE)
        self.assertEqual(request.duration, 10)
        self.assertEqual(request.count, 2)

    def test_cli_requires_local_or_project_material(self):
        install_patches()
        from gflow_cli.cli import main

        result = CliRunner().invoke(
            main,
            ["video", "r2v", "没有素材", "--model", "omni-flash"],
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("--ref or --project-ref", result.output)

    def test_cli_help_explains_both_material_sources(self):
        install_patches()
        from gflow_cli.cli import main

        result = CliRunner().invoke(main, ["video", "r2v", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--project-ref TEXT", result.output)
        self.assertIn("target Flow project", result.output)


if __name__ == "__main__":
    unittest.main()
