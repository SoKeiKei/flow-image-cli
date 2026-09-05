"""在新版 flow.google.com 页面上生成图片。"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

from PIL import Image
from gflow_cli import auth as gflow_auth
from gflow_cli import profile_store
from gflow_cli.api.client import FlowApiClient

MIGRATED_PROJECT_URL = "https://flow.google.com/project/{project_id}"
READY_ANCHOR = ".settings-trigger-button"
OVERLAY = ".cdk-overlay-pane"
RADIOGROUP = "[role='radiogroup']"
RADIO = "[role='radio']"
MENU_ITEM = "[role='menuitem']"
COMPOSER = "[contenteditable='true']"

MODEL_LABELS = {
    "nano-pro": "Nano Banana Pro",
    "nano2": "Nano Banana 2",
    "nano2-lite": "Nano Banana 2 Lite",
}
ASPECT_ICONS = {
    "16:9": "crop_16_9",
    "4:3": "crop_landscape",
    "1:1": "crop_square",
    "3:4": "crop_portrait",
    "9:16": "crop_9_16",
}
_ALLOWED_IMAGE_HOSTS = {
    "flow.google.com",
    "flow-content.google",
}
_PROJECT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str
    aspect: str
    count: int
    output: Path | None
    out_dir: Path | None
    profile: str | None
    project_id: str
    as_json: bool


def _exact(text: str) -> re.Pattern[str]:
    return re.compile(r"^\s*" + re.escape(text) + r"\s*$")


def _icon(page: Any, name: str) -> Any:
    return page.locator("mat-icon").filter(has_text=_exact(name))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flow-cli image t2i",
        description="在当前 Flow 网页中生成图片",
    )
    parser.add_argument("prompt", help="图片描述提示词")
    parser.add_argument(
        "--model",
        choices=tuple(MODEL_LABELS),
        default="nano2",
        help="图片模型（默认: nano2）",
    )
    parser.add_argument(
        "--aspect",
        choices=tuple(ASPECT_ICONS),
        default="9:16",
        help="图片画幅（默认: 9:16）",
    )
    parser.add_argument("-n", "--count", type=int, choices=range(1, 5), default=1)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--out", dest="out_dir", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--project", required=True, help="已有 Flow 项目 ID")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def parse_t2i_request(arguments: Sequence[str]) -> ImageRequest:
    args = _parser().parse_args(list(arguments))
    if not _PROJECT_ID_PATTERN.fullmatch(args.project):
        raise ValueError("项目 ID 格式不正确")
    if args.output is not None and args.count != 1:
        raise ValueError("使用 -o/--output 时只能生成 1 张；多张请改用 --out")
    return ImageRequest(
        prompt=args.prompt,
        model=args.model,
        aspect=args.aspect,
        count=args.count,
        output=args.output,
        out_dir=args.out_dir,
        profile=args.profile,
        project_id=args.project,
        as_json=args.as_json,
    )


def _profile_dir(profile_name: str | None) -> Path:
    resolved = profile_name or profile_store.get_default_profile()
    if not resolved:
        raise RuntimeError(
            "没有可用的 Flow 登录，请先运行 flow-cli auth login --browser chrome"
        )
    path = gflow_auth.profile_dir(resolved)
    if not path.exists():
        raise RuntimeError(f"Flow 登录资料不存在: {resolved}")
    return path


def _image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "WEBP"
    raise RuntimeError("Flow 返回的内容不是可识别的图片")


def _default_output_dir() -> Path:
    return Path.cwd() / "output" / "images" / time.strftime("%Y-%m-%d")


def _output_paths(request: ImageRequest) -> list[Path]:
    if request.output is not None:
        return [request.output]
    base = request.out_dir or _default_output_dir()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return [
        base / f"flow_{request.model}_{stamp}_{index}.png"
        for index in range(1, request.count + 1)
    ]


def _save_image(data: bytes, output: Path) -> Path:
    source_format = _image_format(data)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    wanted_format = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".webp": "WEBP",
    }.get(suffix)
    if wanted_format is None:
        output = output.with_suffix(
            {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[source_format]
        )
        wanted_format = source_format
    if wanted_format == source_format:
        output.write_bytes(data)
        return output
    with Image.open(io.BytesIO(data)) as image:
        if wanted_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(output, format=wanted_format)
    return output


class MigratedImageComposer:
    async def ensure_editor(self, page: Any, project_id: str) -> None:
        target = MIGRATED_PROJECT_URL.format(project_id=project_id)
        if not str(page.url).startswith(target):
            await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
        try:
            await page.locator(READY_ANCHOR).first.wait_for(
                state="visible", timeout=30_000
            )
        except Exception as error:
            raise RuntimeError("新版 Flow 图片编辑器没有正常打开") from error
        await page.wait_for_timeout(1_000)

    async def apply_settings(self, page: Any, request: ImageRequest) -> None:
        trigger = page.locator(READY_ANCHOR).first
        await trigger.click(timeout=5_000)
        pane = page.locator(OVERLAY).filter(has=page.locator(RADIOGROUP)).last
        try:
            await pane.locator(RADIOGROUP).first.wait_for(
                state="visible", timeout=8_000
            )
        except Exception as error:
            raise RuntimeError("新版 Flow 图片设置面板没有正常打开") from error

        await self._select_radio(page, pane, icon_name="image")
        await self._select_radio(page, pane, icon_name=ASPECT_ICONS[request.aspect])
        await self._select_radio(page, pane, text=f"x{request.count}")
        await self._select_model(page, pane, MODEL_LABELS[request.model])
        await self._close_settings(page, pane)

    async def _select_radio(
        self,
        page: Any,
        pane: Any,
        *,
        icon_name: str | None = None,
        text: str | None = None,
    ) -> None:
        radios = pane.locator(RADIO)
        target = (
            radios.filter(has=_icon(page, icon_name)).first
            if icon_name is not None
            else radios.filter(has_text=_exact(text or "")).first
        )
        if not await target.count():
            raise RuntimeError(f"当前 Flow 页面没有提供设置项: {text or icon_name}")
        if await target.get_attribute("aria-checked") != "true":
            await target.click(timeout=5_000)
            await page.wait_for_timeout(200)
        if await target.get_attribute("aria-checked") != "true":
            raise RuntimeError(f"Flow 没有接受设置项: {text or icon_name}")

    async def _select_model(self, page: Any, pane: Any, label: str) -> None:
        button = pane.locator("button").filter(has=_icon(page, "arrow_drop_down")).first
        if not await button.count():
            raise RuntimeError("新版 Flow 图片模型选择器不存在")
        current = " ".join((await button.inner_text()).split())
        if label.lower() in current.lower():
            return
        await button.click(timeout=5_000)
        items = page.locator(MENU_ITEM)
        try:
            await items.first.wait_for(state="visible", timeout=5_000)
        except Exception as error:
            raise RuntimeError("新版 Flow 图片模型列表没有正常打开") from error
        offered = [" ".join(item.split()) for item in await items.all_text_contents()]
        matching_indexes = [
            index
            for index, item_text in enumerate(offered)
            if label.lower() in item_text.lower()
            and not (label == "Nano Banana 2" and "lite" in item_text.lower())
        ]
        if not matching_indexes:
            raise RuntimeError(
                f"当前账号没有提供 {label}；可用模型: {', '.join(offered)}"
            )
        target = items.nth(matching_indexes[0])
        await target.click(timeout=5_000)

    async def _close_settings(self, page: Any, pane: Any) -> None:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        if await pane.count() and await pane.is_visible():
            await page.locator(READY_ANCHOR).first.click(force=True)
            await page.wait_for_timeout(300)
        if await pane.count() and await pane.is_visible():
            raise RuntimeError("新版 Flow 图片设置面板没有收起")

    async def generate(self, page: Any, request: ImageRequest) -> list[bytes]:
        before = await self._image_sources(page)
        composer = page.locator(COMPOSER).first
        await composer.click(timeout=5_000)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.insert_text(request.prompt)
        await page.wait_for_timeout(300)

        submit = page.locator("button").filter(has=_icon(page, "arrow_forward")).first
        if not await submit.count() or not await submit.is_enabled():
            raise RuntimeError("新版 Flow 图片生成按钮不可用")
        await submit.click(timeout=5_000)

        sources = await self._wait_for_new_sources(page, before, request.count)
        images: list[bytes] = []
        for source in sources:
            response = await page.request.get(source, timeout=120_000, max_redirects=0)
            if response.status >= 300:
                raise RuntimeError(f"图片下载失败: HTTP {response.status}")
            body = await response.body()
            _image_format(body)
            images.append(body)
        return images

    async def _image_sources(self, page: Any) -> set[str]:
        sources: set[str] = set()
        images = page.locator("img")
        for index in range(await images.count()):
            source = await images.nth(index).get_attribute("src") or ""
            if source:
                sources.add(source)
        return sources

    async def _wait_for_new_sources(
        self,
        page: Any,
        before: set[str],
        count: int,
    ) -> list[str]:
        deadline = asyncio.get_running_loop().time() + 240
        while asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(2_000)
            current = await self._image_sources(page)
            candidates = [
                source
                for source in current - before
                if urlsplit(source).scheme == "https"
                and urlsplit(source).hostname in _ALLOWED_IMAGE_HOSTS
            ]
            if len(candidates) >= count:
                return candidates[:count]
        raise RuntimeError(
            "图片生成已提交，但等待结果超时；请到 Flow 项目中查看任务状态"
        )


async def generate_images(request: ImageRequest) -> list[Path]:
    profile_dir = _profile_dir(request.profile)
    outputs = _output_paths(request)
    composer = MigratedImageComposer()
    async with FlowApiClient(profile_dir=profile_dir, headless=True) as client:
        page = client.page
        await composer.ensure_editor(page, request.project_id)
        await composer.apply_settings(page, request)
        image_data = await composer.generate(page, request)
    return [
        _save_image(data, output)
        for data, output in zip(image_data, outputs, strict=True)
    ]


def run_migrated_t2i(arguments: Sequence[str]) -> int:
    try:
        request = parse_t2i_request(arguments)
        paths = asyncio.run(generate_images(request))
    except SystemExit as error:
        return int(error.code or 0)
    except Exception as error:
        print(f"错误: 图片生成失败: {error}")
        return 1

    if request.as_json:
        print(json.dumps({"files": [str(path) for path in paths]}, ensure_ascii=False))
    else:
        print("完成: 图片生成成功")
        for path in paths:
            print(f"  {path}")
    return 0


def print_current_models() -> int:
    print("当前图片模型:")
    print("  nano2-lite  Nano Banana 2 Lite（成本最低）")
    print("  nano2       Nano Banana 2")
    print("  nano-pro    Nano Banana Pro")
    print("\n当前视频模型:")
    print("  omni-flash  Omni 1.1 Flash")
    print("  veo-lite    Veo 3.1 Lite")
    print("  veo-fast    Veo 3.1 Fast")
    print("  veo-quality Veo 3.1 Quality")
    return 0


if __name__ == "__main__":
    sys.exit(run_migrated_t2i(sys.argv[1:]))
