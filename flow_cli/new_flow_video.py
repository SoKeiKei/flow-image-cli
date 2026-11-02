"""Project-owned compatibility layer for Flow's migrated video composer.

The upstream package supplies browser/session management.  This module owns the
new ``flow.google.com`` video contract so fixes live in this repository rather
than in ``site-packages``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from gflow_cli.errors import ConfigurationError

VIDEO_RESOLUTION_ENV = "FLOW_CLI_VIDEO_RESOLUTION"
PROJECT_REFERENCE_NAMES_ENV = "FLOW_CLI_PROJECT_REFERENCE_NAMES"
DEFAULT_VIDEO_RESOLUTION = "720p"
VIDEO_RESOLUTIONS = ("360p", "720p")
MATERIALS_LIGATURE = "chrome_extension"
FRAMES_LIGATURE = "crop_free"


class VideoConfigurationMismatch(ConfigurationError):
    """Raised before submit when Flow does not reflect the requested contract."""


@dataclass(frozen=True)
class SettingsSnapshot:
    mode: str
    submode: str | None
    model: str | None
    aspect: str
    resolution: str
    duration: int
    count: int


@dataclass(frozen=True)
class AttachedInputs:
    media_ids: tuple[str, ...]
    chip_count: int
    project_reference_names: tuple[str, ...] = ()


def requested_resolution() -> str:
    value = os.environ.get(VIDEO_RESOLUTION_ENV, DEFAULT_VIDEO_RESOLUTION).lower()
    if value not in VIDEO_RESOLUTIONS:
        choices = ", ".join(VIDEO_RESOLUTIONS)
        raise ValueError(
            f"unsupported video resolution {value!r}; choose from {choices}"
        )
    return value


def requested_project_reference_names() -> tuple[str, ...]:
    """Return exact in-project material titles captured from the CLI option."""
    raw = os.environ.get(PROJECT_REFERENCE_NAMES_ENV, "[]")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid project reference configuration") from exc
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise ValueError("invalid project reference configuration")
    return tuple(values)


def expected_submode(mode: Any) -> str | None:
    value = getattr(mode, "value", str(mode))
    if value == "r2v":
        return "materials"
    if value == "i2v":
        return "frames"
    return None


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _duration_from_label(label: str) -> int | None:
    match = re.fullmatch(r"\s*(\d+)\s*(?:s|sec(?:ond)?s?|秒)\s*", label, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _count_from_label(label: str) -> int | None:
    match = re.fullmatch(r"\s*(?:x\s*(\d+)|(\d+)\s*x)\s*", label, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def _resolution_from_label(label: str) -> str | None:
    compact = _compact(label)
    match = re.fullmatch(r"(360p|720p)(?:info)?", compact)
    return match.group(1) if match else None


def validate_settings_snapshot(
    request: Any,
    resolution: str,
    snapshot: SettingsSnapshot,
) -> None:
    """Validate every setting represented by the migrated Flow UI."""
    problems: list[str] = []
    if snapshot.mode != "video":
        problems.append(f"mode={snapshot.mode!r}, expected 'video'")

    wanted_submode = expected_submode(request.mode)
    if wanted_submode is not None and snapshot.submode != wanted_submode:
        problems.append(f"submode={snapshot.submode!r}, expected {wanted_submode!r}")

    model = request.model
    if model is None:
        problems.append("model was not explicitly requested")
    else:
        from gflow_cli.api.transports import migrated_composer as migrated

        matcher = migrated.VIDEO_MODEL_MENU_MATCHERS.get(model)
        if matcher is None or not matcher.matches(snapshot.model or ""):
            problems.append(
                f"model={snapshot.model!r}, expected {getattr(model, 'value', model)!r}"
            )

    if snapshot.aspect != request.aspect.value:
        problems.append(
            f"aspect={snapshot.aspect!r}, expected {request.aspect.value!r}"
        )
    if snapshot.resolution != resolution:
        problems.append(f"resolution={snapshot.resolution!r}, expected {resolution!r}")
    if request.duration is None:
        problems.append("duration was not explicitly requested")
    elif snapshot.duration != request.duration:
        problems.append(
            f"duration={snapshot.duration!r}, expected {request.duration!r}"
        )
    if snapshot.count != request.count:
        problems.append(f"count={snapshot.count!r}, expected {request.count!r}")

    if problems:
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: " + "; ".join(problems)
        )


def _capture_resolution(
    _ctx: click.Context,
    _param: click.Parameter,
    value: str,
) -> str:
    normalized = value.lower()
    os.environ[VIDEO_RESOLUTION_ENV] = normalized
    return normalized


def _capture_project_references(
    _ctx: click.Context,
    param: click.Parameter,
    value: tuple[str, ...],
) -> tuple[str, ...]:
    normalized = tuple(name.strip() for name in value)
    if any(not name for name in normalized):
        raise click.BadParameter("project material title cannot be empty", param=param)
    if len(set(normalized)) != len(normalized):
        raise click.BadParameter(
            "each project material title may be supplied only once", param=param
        )
    os.environ[PROJECT_REFERENCE_NAMES_ENV] = json.dumps(normalized, ensure_ascii=False)
    return normalized


def _validate_r2v_sources(command: Any) -> Any:
    """Require at least one local or project material at the Click boundary."""
    if getattr(command, "_flow_cli_project_refs_wrapped", False):
        return command

    original = command.callback

    def callback(*args: Any, **kwargs: Any) -> Any:
        local_refs = tuple(kwargs.get("refs") or ())
        project_refs = requested_project_reference_names()
        if not local_refs and not project_refs:
            raise click.UsageError(
                "video r2v requires at least one --ref or --project-ref material"
            )
        model_name = kwargs.get("model")
        if model_name is not None:
            from gflow_cli.api.video import VideoModel, reference_cap_for

            model = VideoModel.from_cli(model_name)
            if model is not None:
                cap = reference_cap_for(model)
                total = len(local_refs) + len(project_refs)
                if cap == 0:
                    raise click.UsageError(
                        f"{model_name} does not support R2V (reference-to-video)."
                    )
                if total > cap:
                    raise click.UsageError(
                        f"{model_name} allows at most {cap} reference image(s); got {total}."
                    )
        return original(*args, **kwargs)

    command.callback = callback
    command._flow_cli_project_refs_wrapped = True
    return command


def _install_contract_options() -> None:
    from gflow_cli import cli_video

    for command in (cli_video.t2v, cli_video.i2v, cli_video.r2v):
        for param in command.params:
            if not isinstance(param, click.Option):
                continue
            if "--model" in param.opts:
                param.required = True
                param.help = "Video model. Required so the run never inherits Flow's saved model."
            elif "--duration" in param.opts:
                param.default = "4"
                param.show_default = True
                param.help = (
                    "Clip length. Defaults to 4 seconds and is always selected and "
                    "read back before submit."
                )
        if any(
            isinstance(param, click.Option) and "--resolution" in param.opts
            for param in command.params
        ):
            continue
        command.params.append(
            click.Option(
                ["--resolution"],
                type=click.Choice(VIDEO_RESOLUTIONS, case_sensitive=False),
                default=DEFAULT_VIDEO_RESOLUTION,
                show_default=True,
                expose_value=False,
                callback=_capture_resolution,
                help=(
                    "Video resolution. Always selected and read back before submit; "
                    "never inherited from Flow's saved state."
                ),
            )
        )

    for param in cli_video.r2v.params:
        if isinstance(param, click.Option) and "--ref" in param.opts:
            param.required = False
            param.help = (
                "Local material image (repeatable). Use --project-ref for an image "
                "already present in the target Flow project."
            )
    if not any(
        isinstance(param, click.Option) and "--project-ref" in param.opts
        for param in cli_video.r2v.params
    ):
        cli_video.r2v.params.append(
            click.Option(
                ["--project-ref"],
                multiple=True,
                expose_value=False,
                callback=_capture_project_references,
                help=(
                    "Exact title of an existing material in the target Flow project "
                    "(repeatable; may be combined with --ref)."
                ),
            )
        )
    _validate_r2v_sources(cli_video.r2v)
    cli_video.r2v.help = (
        "Reference-to-video in Flow's Materials mode. Use repeatable --ref for "
        "local images, repeatable --project-ref for exact titles already in the "
        "target project, or combine both sources. At least one material is required."
    )


async def _run_r2v_with_project_references(
    *,
    profile_name: str,
    profile_dir: Path,
    prompt: str,
    refs: tuple[str, ...],
    aspect: str,
    out_dir: Path | None,
    model: str | None = None,
    duration: int | None = None,
    count: int = 1,
    output_file: Path | None = None,
    as_json: bool = False,
    reference_entities: tuple[str, ...] = (),
    reference_entity_names: tuple[str, ...] = (),
    original_prompt: str | None = None,
    tool: Any = None,
    project_id: str | None = None,
    project_name: str | None = None,
    tool_specs: tuple[str, ...] = (),
) -> None:
    """Build R2V requests with local files and/or existing project materials."""
    from gflow_cli import cli_video
    from gflow_cli._cli_helpers import slugify_project_name
    from gflow_cli.api.video import Aspect, GenerateVideoRequest, Mode, VideoModel

    effective_title = project_name or slugify_project_name(prompt, prefix="gflow-r2v")
    request = GenerateVideoRequest(
        prompt=prompt,
        mode=Mode.R2V,
        aspect=Aspect.from_cli(aspect),
        model=VideoModel.from_cli(model),
        duration=duration,
        count=count,
        reference_images=tuple(Path(ref) for ref in refs),
        ref_names=requested_project_reference_names(),
        reference_entities=reference_entities,
        reference_entity_names=reference_entity_names,
        original_prompt=original_prompt,
        tool=tool,
    )
    await cli_video._generate_and_report(
        request,
        profile_name=profile_name,
        profile_dir=profile_dir,
        out_dir=out_dir,
        output_file=output_file,
        command="video r2v",
        as_json=as_json,
        project_id=project_id,
        project_name=effective_title,
        tool_specs=tool_specs,
    )


async def _select_text_radio(
    page: Any,
    pane: Any,
    *,
    axis: str,
    parser: Any,
    expected: Any,
) -> None:
    """Select one localized radio by its parsed semantic value."""
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.errors import UiSelectorDriftError

    radios = pane.locator(migrated.RADIO)
    labels = await radios.all_text_contents()
    hits = [index for index, label in enumerate(labels) if parser(label) == expected]
    if len(hits) != 1:
        raise UiSelectorDriftError(
            detail=(
                f"migrated host: expected exactly one {axis} radio for {expected!r}; "
                f"found {len(hits)} among {labels!r}. No credits were spent."
            )
        )
    target = radios.nth(hits[0])
    if await target.get_attribute("aria-checked") != "true":
        await target.click(timeout=4000)
        await asyncio.sleep(0.2)
    if await radios.nth(hits[0]).get_attribute("aria-checked") != "true":
        raise UiSelectorDriftError(
            detail=(
                f"migrated host: the {axis} radio for {expected!r} did not become "
                "aria-checked after the click. No credits were spent."
            )
        )


async def _open_settings_pane(self: Any, page: Any) -> Any:
    """Open the live settings pane, ignoring detached Angular overlays."""
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.errors import UiSelectorDriftError

    trigger = page.locator(migrated.READY_ANCHOR).first
    if not await trigger.count():
        raise UiSelectorDriftError(detail="migrated host: settings trigger is missing")
    for _attempt in range(2):
        await trigger.click(timeout=5000)
        await asyncio.sleep(0.3)
        pane = (
            page.locator(f"{migrated.OVERLAY}:visible")
            .filter(has=page.locator(migrated.RADIOGROUP))
            .last
        )
        if await pane.count() and await pane.locator(migrated.RADIOGROUP).count():
            return pane
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
    raise UiSelectorDriftError(
        detail=(
            "migrated host: settings trigger opened no visible option groups after "
            "two attempts. Nothing was submitted."
        )
    )


async def _checked_ligature(page: Any, pane: Any, ligature: str) -> bool:
    from gflow_cli.api.transports import migrated_composer as migrated

    radios = pane.locator(migrated.RADIO).filter(has=migrated._ligature(page, ligature))
    return (
        await radios.count() == 1
        and await radios.first.get_attribute("aria-checked") == "true"
    )


async def _checked_text_value(pane: Any, parser: Any) -> Any:
    from gflow_cli.api.transports import migrated_composer as migrated

    radios = pane.locator(migrated.RADIO)
    labels = await radios.all_text_contents()
    for index, label in enumerate(labels):
        value = parser(label)
        if value is None:
            continue
        if await radios.nth(index).get_attribute("aria-checked") == "true":
            return value
    return None


async def _collect_settings_snapshot(page: Any, pane: Any) -> SettingsSnapshot:
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.api.video import Aspect

    if await _checked_ligature(page, pane, MATERIALS_LIGATURE):
        submode = "materials"
    elif await _checked_ligature(page, pane, FRAMES_LIGATURE):
        submode = "frames"
    else:
        submode = None

    if await _checked_ligature(page, pane, migrated.ASPECT_LIGATURE[Aspect.LANDSCAPE]):
        aspect = Aspect.LANDSCAPE.value
    elif await _checked_ligature(page, pane, migrated.ASPECT_LIGATURE[Aspect.PORTRAIT]):
        aspect = Aspect.PORTRAIT.value
    else:
        aspect = "unknown"

    model_button = (
        pane.locator("button")
        .filter(has=migrated._ligature(page, "arrow_drop_down"))
        .first
    )
    model_text = (
        (await model_button.text_content() or "").strip()
        if await model_button.count()
        else None
    )
    return SettingsSnapshot(
        mode="video" if await _checked_ligature(page, pane, "videocam") else "unknown",
        submode=submode,
        model=model_text,
        aspect=aspect,
        resolution=await _checked_text_value(pane, _resolution_from_label) or "unknown",
        duration=await _checked_text_value(pane, _duration_from_label) or -1,
        count=await _checked_text_value(pane, _count_from_label) or -1,
    )


async def _apply_video_settings(self: Any, page: Any, request: Any) -> None:
    """Set and immediately read back every migrated-host video setting."""
    from gflow_cli.api.transports import migrated_composer as migrated

    if request.model is None:
        from gflow_cli.errors import ConfigurationError

        raise ConfigurationError(
            detail=(
                "the migrated Flow video chain requires an explicit --model so it "
                "never inherits the account's previously saved model"
            )
        )
    if request.duration is None:
        from gflow_cli.errors import ConfigurationError

        raise ConfigurationError(
            detail=(
                "the migrated Flow video chain requires an explicit --duration so it "
                "never inherits the account's previously saved duration"
            )
        )

    resolution = requested_resolution()
    pane = await self._open_pane(page)
    try:
        await self._select(page, pane, axis="mode", lig="videocam")
        submode = expected_submode(request.mode)
        if submode == "frames":
            await self._select(page, pane, axis="submode", lig=FRAMES_LIGATURE)
        elif submode == "materials":
            await self._select(page, pane, axis="submode", lig=MATERIALS_LIGATURE)
        await self._select_model(page, pane, request.model)
        await self._select(
            page,
            pane,
            axis="aspect",
            lig=migrated.ASPECT_LIGATURE[request.aspect],
        )
        await _select_text_radio(
            page,
            pane,
            axis="resolution",
            parser=_resolution_from_label,
            expected=resolution,
        )
        await _select_text_radio(
            page,
            pane,
            axis="duration",
            parser=_duration_from_label,
            expected=request.duration,
        )
        await _select_text_radio(
            page,
            pane,
            axis="count",
            parser=_count_from_label,
            expected=request.count,
        )
        validate_settings_snapshot(
            request,
            resolution,
            await _collect_settings_snapshot(page, pane),
        )
    except BaseException:
        await self._close_pane(page, strict=False)
        raise
    await self._close_pane(page, strict=True)


async def _find_asset_option(
    page: Any,
    picker: Any,
    *,
    name: str,
    media_id: str,
) -> Any:
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.errors import ReferenceNotFoundError

    search = picker.locator(migrated.PICKER_SEARCH).first
    await search.fill(name, timeout=4000)
    exact_title = page.locator(".asset-title").filter(has_text=migrated._exact(name))
    options = picker.locator(migrated.PICKER_OPTION).filter(has=exact_title)
    try:
        await options.first.wait_for(
            state="visible", timeout=int(migrated.FRAME_PICKER_OPEN_S * 1000)
        )
    except Exception as exc:
        listed = [
            text.strip()
            for text in await picker.locator(migrated.PICKER_OPTION).all_text_contents()
        ]
        raise ReferenceNotFoundError(
            detail=(
                f"migrated host: no picker option with the exact material title "
                f"{name!r} ({media_id}); listed: {listed[:8]!r}. No credits were spent."
            )
        ) from exc
    if await options.count() != 1:
        raise ReferenceNotFoundError(
            detail=(
                f"migrated host: material {media_id} matched "
                f"{await options.count()} picker options; refusing an ambiguous choice."
            )
        )
    return options.first


async def _open_material_picker(page: Any) -> Any:
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.errors import UiSelectorDriftError

    trigger = page.locator("flow-prompt-box button.add-menu-trigger").first
    if not await trigger.count():
        raise UiSelectorDriftError(
            detail="migrated host: prompt material add button is missing"
        )
    await trigger.click(timeout=4000)
    picker = (
        page.locator(f"{migrated.OVERLAY}:visible")
        .filter(has=page.locator(migrated.PICKER))
        .last
    )
    try:
        await picker.locator(migrated.PICKER_SEARCH).first.wait_for(
            state="visible", timeout=int(migrated.FRAME_PICKER_OPEN_S * 1000)
        )
    except Exception as exc:
        raise UiSelectorDriftError(
            detail="migrated host: material picker did not open"
        ) from exc
    return picker


async def _attach_one_material(
    page: Any,
    *,
    name: str,
    media_id: str,
    before_count: int,
) -> None:
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.errors import UiSelectorDriftError

    picker = await _open_material_picker(page)
    option = await _find_asset_option(page, picker, name=name, media_id=media_id)
    await option.click(timeout=4000)
    await asyncio.sleep(0.5)
    chips = page.locator("flow-prompt-box button.chip-container")
    if await chips.count() == before_count + 1:
        return
    picker = (
        page.locator(f"{migrated.OVERLAY}:visible")
        .filter(has=page.locator(migrated.PICKER))
        .last
    )
    commit = picker.locator("button.detail-add-to-prompt-btn").first
    if not await commit.count():
        raise UiSelectorDriftError(
            detail="migrated host: material picker has no Add-to-Prompt action"
        )
    await commit.click(timeout=4000)
    await picker.wait_for(
        state="hidden", timeout=int(migrated.FRAME_COMMIT_HIDDEN_S * 1000)
    )
    if await chips.count() != before_count + 1:
        raise UiSelectorDriftError(
            detail=(
                "migrated host: selected material did not add exactly one prompt chip; "
                "refusing to continue"
            )
        )


async def _attach_local_inputs(
    composer: Any,
    page: Any,
    request: Any,
    project_id: str,
) -> AttachedInputs:
    from gflow_cli.api.client import validate_image_file
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.api.video import Mode
    from gflow_cli.errors import ConfigurationError

    existing = await page.locator("flow-prompt-box button.chip-container").count()
    if existing:
        raise ConfigurationError(
            detail=(
                f"the Flow composer already contains {existing} media chip(s); "
                "refusing to mix a saved draft with this request"
            )
        )

    if request.mode is Mode.I2V:
        paths = [path for path in (request.start_image, request.end_image) if path]
    elif request.mode is Mode.R2V:
        paths = list(request.reference_images)
    else:
        paths = []

    media_ids: list[str] = []
    project_reference_names: list[str] = []
    with tempfile.TemporaryDirectory(prefix="flow-cli-video-") as temp_dir:
        staging_dir = Path(temp_dir)
        for index, image_path in enumerate(paths):
            await validate_image_file(image_path)
            staged_name = (
                f"flow-cli-{index + 1}-{uuid.uuid4().hex}{image_path.suffix.lower()}"
            )
            staged_path = staging_dir / staged_name
            shutil.copyfile(image_path, staged_path)
            media_id = await composer._upload_via_toolbar(page, project_id, staged_path)
            media_ids.append(media_id)
            before = await page.locator("flow-prompt-box button.chip-container").count()
            if request.mode is Mode.I2V:
                picker = await composer._open_frame_picker(page)
                option = await _find_asset_option(
                    page,
                    picker,
                    name=staged_name,
                    media_id=media_id,
                )
                await option.click(timeout=4000)
                await picker.wait_for(
                    state="hidden", timeout=int(migrated.FRAME_COMMIT_HIDDEN_S * 1000)
                )
                after = await page.locator(
                    "flow-prompt-box button.chip-container"
                ).count()
                if after != before + 1:
                    from gflow_cli.errors import UiSelectorDriftError

                    raise UiSelectorDriftError(
                        detail=(
                            f"migrated host: frame slot {index + 1} did not bind exactly "
                            "one image; refusing to continue"
                        )
                    )
            else:
                await _attach_one_material(
                    page,
                    name=staged_name,
                    media_id=media_id,
                    before_count=before,
                )

        if request.mode is Mode.R2V:
            for name in request.ref_names:
                before = await page.locator(
                    "flow-prompt-box button.chip-container"
                ).count()
                await _attach_one_material(
                    page,
                    name=name,
                    media_id=f"existing project material {name!r}",
                    before_count=before,
                )
                project_reference_names.append(name)

    return AttachedInputs(
        media_ids=tuple(media_ids),
        chip_count=await page.locator("flow-prompt-box button.chip-container").count(),
        project_reference_names=tuple(project_reference_names),
    )


async def _verify_pre_submit(
    composer: Any,
    page: Any,
    request: Any,
    attached: AttachedInputs,
) -> None:
    """Final read-back gate.  Any mismatch aborts before the submit click."""
    from gflow_cli.api.transports import migrated_composer as migrated

    await asyncio.sleep(0.5)
    pane = await composer._open_pane(page)
    try:
        snapshot = await _collect_settings_snapshot(page, pane)
        validate_settings_snapshot(request, requested_resolution(), snapshot)
    except BaseException:
        await composer._close_pane(page, strict=False)
        raise
    await composer._close_pane(page, strict=True)

    expected_inputs = 0
    if request.mode.value == "i2v":
        expected_inputs = 1 + int(request.end_image is not None)
    elif request.mode.value == "r2v":
        expected_inputs = len(request.reference_images) + len(request.ref_names)
    if attached.chip_count != expected_inputs:
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: "
            f"bound media chips={attached.chip_count}, expected {expected_inputs}"
        )
    resolved_inputs = len(attached.media_ids) + len(attached.project_reference_names)
    if resolved_inputs != expected_inputs:
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: "
            f"resolved media inputs={resolved_inputs}, expected {expected_inputs}"
        )
    if attached.project_reference_names != tuple(request.ref_names):
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: selected project material titles "
            "differ from the request"
        )

    prompt_editor = page.locator(migrated.COMPOSER).first
    if not await prompt_editor.count():
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: prompt editor is missing"
        )
    actual_prompt = (await prompt_editor.text_content() or "").replace("\r\n", "\n")
    expected_prompt = request.prompt.replace("\r\n", "\n")
    if actual_prompt != expected_prompt:
        raise VideoConfigurationMismatch(
            "Flow pre-submit read-back mismatch: prompt text differs from the request"
        )


def _unported_form(request: Any) -> str | None:
    from gflow_cli.api.video import Mode

    if request.mode is Mode.T2V:
        return None
    if request.mode is Mode.I2V:
        if request.start_image_ref_id:
            return "a frame given by Flow media UUID"
        if request.start_image_ref_name:
            return "a frame given by @Name"
        if request.end_image_ref_id or request.end_image_ref_name:
            return "an end frame not provided as a local file"
        if not isinstance(request.start_image, Path):
            return "image-to-video without a local start frame"
        return None
    if request.mode is Mode.R2V:
        if request.reference_entities or request.reference_audio:
            return "character or audio reference resources"
        if not request.reference_images and not request.ref_names:
            return "reference-to-video without reference materials"
        return None
    return f"unsupported video mode {request.mode!r}"


def _migrated_can_serve(request: Any, project_id: str | None) -> bool:
    from gflow_cli.api.transports import migrated_composer as migrated

    if _unported_form(request) is not None or not project_id:
        return False
    return request.model is None or request.model in migrated.VIDEO_MODEL_MENU_MATCHERS


async def _run_video(
    page: Any,
    request: Any,
    *,
    project_id: str | None,
    out_dir: Path | None,
    poll_timeout_s: float,
    download: bool,
    on_started: Any,
) -> Any:
    from gflow_cli.api.transports import migrated_composer as migrated
    from gflow_cli.api.transports._common import extract_project_id
    from gflow_cli.api.video import Mode, VideoResult, VideoStatus
    from gflow_cli.errors import ConfigurationError, FlowHostMigratedError

    unported = _unported_form(request)
    if unported is not None:
        raise FlowHostMigratedError(
            detail=(
                "this flow.google.com request cannot be represented without changing "
                f"its requested route: {unported}. Nothing was submitted."
            )
        )
    pid = project_id or extract_project_id(page.url)
    if not pid:
        raise ConfigurationError(
            detail="flow.google.com video generation requires an existing --project"
        )

    composer = migrated.MigratedComposer()
    await composer.ensure_editor(page, pid)
    await composer.apply_video_settings(page, request)
    attached = await _attach_local_inputs(composer, page, request, pid)
    await composer.send_prompt(page, request.prompt)
    await _verify_pre_submit(composer, page, request, attached)

    record = await composer.submit_and_observe(
        page,
        poll_timeout_s=poll_timeout_s,
        on_started=on_started,
        project_id=pid,
        expect_media_id=(attached.media_ids[0] if request.mode is Mode.I2V else None),
    )
    status = VideoStatus(
        media_id=record.media_id,
        status=(
            "MEDIA_GENERATION_STATUS_SUCCESSFUL"
            if record.is_done
            else "MEDIA_GENERATION_STATUS_FAILED"
        ),
        error_message=(
            None if record.is_done else f"migrated host reported status {record.status}"
        ),
    )
    local_path = None
    if download and record.is_done:
        local_path = await composer.download(page, record, out_dir)
    return VideoResult(
        status=status,
        local_path=Path(local_path) if local_path is not None else None,
        project_id=pid,
        flow_operation_id=record.workflow_id,
    )


def install_patches() -> None:
    """Install project-owned new-Flow patches in the child CLI process."""
    from gflow_cli.api.transports import migrated_composer as migrated

    from .flow_original_download import download_original_video

    _install_contract_options()
    from gflow_cli import cli_video

    cli_video._run_r2v = _run_r2v_with_project_references
    migrated.MigratedComposer._open_pane = _open_settings_pane
    migrated.MigratedComposer.apply_video_settings = _apply_video_settings
    migrated.MigratedComposer.download = download_original_video
    migrated._unported_form = _unported_form
    migrated.migrated_can_serve = _migrated_can_serve
    migrated.run_video = _run_video
