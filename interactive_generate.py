#!/usr/bin/env python3
"""
Flow 菜单式交互生图脚本（支持中文/英文/双语）。
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flow_cli.client import ImageGenerator
from flow_cli.config import get_config
from flow_cli.models import DEFAULT_MODEL, IMAGE_MODELS

ASPECT_OPTIONS: List[Tuple[str, str, str]] = [
    ("landscape", "横屏 16:9", "Landscape 16:9"),
    ("portrait", "竖屏 9:16", "Portrait 9:16"),
    ("square", "方图 1:1", "Square 1:1"),
    ("four-three", "横屏 4:3", "Landscape 4:3"),
    ("three-four", "竖屏 3:4", "Portrait 3:4"),
]

# 默认画幅 16:9
DEFAULT_ASPECT = "landscape"

# 分辨率选项，none 放在最前面作为默认
RESOLUTION_OPTIONS: List[Tuple[str, str, str]] = [
    ("none", "原图", "Original"),
    ("2k", "2K", "2K"),
    ("4k", "4K", "4K"),
]

# 默认分辨率（显示原图）
DEFAULT_RESOLUTION = "none"

LANGUAGE_OPTIONS: List[Tuple[str, str]] = [
    ("zh", "中文"),
    ("en", "English"),
    ("bi", "双语 / Bilingual"),
]

DEFAULT_OUTPUT_TEMPLATE = "output/flow_{timestamp}.png"


class InputClosed(Exception):
    """输入流结束时用于中断交互流程。"""


def _text(zh: str, en: str, lang: str) -> str:
    if lang == "en":
        return en
    if lang == "bi":
        return f"{zh} / {en}"
    return zh


def _ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError as exc:
        raise InputClosed() from exc
    if value:
        return value
    return default or ""


def _safe_print(zh: str, en: str, lang: str) -> None:
    print(_text(zh, en, lang))


def _bootstrap_language() -> str:
    # 默认使用中文
    return "zh"


def _choose_language(current_lang: str) -> str:
    print()
    _safe_print("切换语言:", "Switch Language:", current_lang)
    for idx, (_, label) in enumerate(LANGUAGE_OPTIONS, 1):
        mark = " *" if LANGUAGE_OPTIONS[idx - 1][0] == current_lang else ""
        print(f"  {idx}. {label}{mark}")
    print("  (* 当前 / * current)")

    raw = _ask(_text("选择", "Select", current_lang), default="")
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(LANGUAGE_OPTIONS):
            return LANGUAGE_OPTIONS[idx - 1][0]
    _safe_print("输入无效，保持不变", "Invalid input, keeping current", current_lang)
    return current_lang


def _ensure_st(lang: str) -> bool:
    config = get_config()
    if config.token.st:
        return True

    print()
    _safe_print("未检测到 Session Token(ST)", "Session Token (ST) not found", lang)
    st = _ask(_text("请输入 ST（留空退出）", "Please input ST (empty to exit)", lang), default="")
    if not st:
        return False
    config.token.st = st
    config.save_token()
    _safe_print(
        "完成: ST 已保存到 ~/.flow-cli/token.json",
        "Done: ST saved to ~/.flow-cli/token.json",
        lang,
    )
    return True


def _parse_model_catalog() -> Dict[str, List[str]]:
    families: Dict[str, List[str]] = {}
    suffixes = [x[0] for x in ASPECT_OPTIONS]
    suffixes.sort(key=len, reverse=True)

    for model_id in IMAGE_MODELS:
        matched = None
        for suffix in suffixes:
            tail = f"-{suffix}"
            if model_id.endswith(tail):
                matched = suffix
                family = model_id[: -len(tail)]
                families.setdefault(family, [])
                if suffix not in families[family]:
                    families[family].append(suffix)
                break
        if not matched:
            families.setdefault(model_id, [])

    suffix_order = [x[0] for x in ASPECT_OPTIONS]
    for family in families:
        families[family].sort(key=lambda s: suffix_order.index(s) if s in suffix_order else 999)
    return families


def _model_to_family_aspect(model_id: str) -> Tuple[str, str]:
    for suffix, _, _ in sorted(ASPECT_OPTIONS, key=lambda x: len(x[0]), reverse=True):
        tail = f"-{suffix}"
        if model_id.endswith(tail):
            return model_id[: -len(tail)], suffix
    return model_id, DEFAULT_ASPECT


def _build_model_id(family: str, aspect: str, families: Dict[str, List[str]]) -> str:
    if family in families and aspect in families[family]:
        model_id = f"{family}-{aspect}"
        if model_id in IMAGE_MODELS:
            return model_id

    if family in families and families[family]:
        fallback_aspect = families[family][0]
        model_id = f"{family}-{fallback_aspect}"
        if model_id in IMAGE_MODELS:
            return model_id
    return DEFAULT_MODEL


def _choose_family(current: str, families: Dict[str, List[str]], lang: str) -> str:
    family_list = list(families.keys())
    print()
    _safe_print("可选模型族:", "Model families:", lang)
    for idx, fam in enumerate(family_list, 1):
        mark = " *" if fam == current else ""
        print(f"  {idx:2d}. {fam}{mark}")
    print("  (* 当前 / * current)")

    raw = _ask(_text("选择", "Select", lang), default="")
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(family_list):
            return family_list[idx - 1]
    _safe_print("输入无效，保持不变", "Invalid input, keeping current", lang)
    return current


def _choose_aspect(current: str, family: str, families: Dict[str, List[str]], lang: str) -> str:
    allowed = families.get(family, [])
    if not allowed:
        _safe_print(
            "当前模型族没有可用画幅",
            "No available aspect for current family",
            lang,
        )
        return current

    print()
    _safe_print(f"可选画幅 (family: {family}):", f"Available aspects:", lang)
    entries = [x for x in ASPECT_OPTIONS if x[0] in allowed]
    for idx, (key, zh_desc, en_desc) in enumerate(entries, 1):
        mark = " *" if key == current else ""
        print(f"  {idx}. {zh_desc} ({key}){mark}")
    print("  (* 当前 / * current)")

    raw = _ask(_text("选择 (默认 1 十六比九)", "Select (default 1 16:9)", lang), default="1")
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(entries):
            return entries[idx - 1][0]
    _safe_print("输入无效，保持不变", "Invalid input, keeping current", lang)
    return current


def _choose_resolution(current: str, lang: str) -> str:
    print()
    _safe_print("可选分辨率:", "Resolution options:", lang)
    for idx, (key, zh_desc, en_desc) in enumerate(RESOLUTION_OPTIONS, 1):
        mark = " *" if key == current else ""
        print(f"  {idx}. {zh_desc} ({key}){mark}")
    print("  (* 当前 / * current)")

    raw = _ask(_text("选择 (默认 1 原图)", "Select (default 1 Original)", lang), default="1")
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(RESOLUTION_OPTIONS):
            return RESOLUTION_OPTIONS[idx - 1][0]
    _safe_print("输入无效，保持不变", "Invalid input, keeping current", lang)
    return current


def _load_reference_bytes(reference_path: str, lang: str) -> Optional[bytes]:
    if not reference_path:
        return None
    ref = Path(reference_path)
    if not ref.exists() or not ref.is_file():
        print(
            _text(
                f"提示: 参考图不存在，忽略：{reference_path}",
                f"Tip: reference image not found, ignored: {reference_path}",
                lang,
            )
        )
        return None
    return ref.read_bytes()


def _resolve_output_path(path: str) -> str:
    """展开输出路径模板，支持 {timestamp}。"""
    if not path:
        return path
    return path.replace("{timestamp}", str(int(time.time())))


async def _generate_once(
    family: str,
    aspect: str,
    upscale: str,
    default_output: str,
    reference_path: str,
    families: Dict[str, List[str]],
    lang: str,
) -> None:
    model_id = _build_model_id(family, aspect, families)
    print()
    prompt = _ask(_text("请输入提示词", "Enter prompt", lang), default="")
    if not prompt:
        _safe_print("提示: 提示词为空，已取消", "Tip: empty prompt, cancelled", lang)
        return

    output_path = _ask(
        _text("输出路径（留空按默认）", "Output path (empty for default)", lang),
        default=default_output,
    )
    output_path = _resolve_output_path(output_path)
    reference_image = _load_reference_bytes(reference_path, lang)

    generator = ImageGenerator()
    result = await generator.generate(
        prompt=prompt,
        model=model_id,
        reference_image=reference_image,
        output_path=output_path or None,
        upscale=upscale,
    )

    if result.startswith("http"):
        print()
        print(_text(f"完成: 图片 URL: {result}", f"Done: image URL: {result}", lang))
    else:
        print()
        print(_text(f"完成: 保存路径: {result}", f"Done: saved path: {result}", lang))


def main() -> int:
    try:
        lang = _bootstrap_language()
    except InputClosed:
        print("输入结束，已退出 / Input closed, exited")
        return 0

    _safe_print("Flow 菜单式交互生图", "Flow Interactive Image Generation", lang)
    print("-" * 40)

    try:
        if not _ensure_st(lang):
            _safe_print("未提供 ST，退出", "No ST provided, exiting", lang)
            return 1
    except InputClosed:
        _safe_print("输入结束，已退出", "Input closed, exited", lang)
        return 0

    families = _parse_model_catalog()
    default_family, default_aspect = _model_to_family_aspect(DEFAULT_MODEL)

    family = default_family if default_family in families else list(families.keys())[0]
    aspect = DEFAULT_ASPECT
    if aspect not in families.get(family, []):
        aspect = families[family][0] if families.get(family) else DEFAULT_ASPECT
    upscale = DEFAULT_RESOLUTION
    reference_path = ""
    default_output = DEFAULT_OUTPUT_TEMPLATE

    while True:
        current_model = _build_model_id(family, aspect, families)

        # 获取当前分辨率和画幅的显示
        current_res_zh = next((x[1] for x in RESOLUTION_OPTIONS if x[0] == upscale), upscale)
        current_res_en = next((x[2] for x in RESOLUTION_OPTIONS if x[0] == upscale), upscale)
        current_aspect_zh = next((x[1] for x in ASPECT_OPTIONS if x[0] == aspect), aspect)
        current_aspect_en = next((x[2] for x in ASPECT_OPTIONS if x[0] == aspect), aspect)

        print()
        _safe_print("当前配置:", "Current:", lang)
        print(_text(f"  画幅: {current_aspect_zh}", f"  Aspect: {current_aspect_en}", lang))
        print(_text(f"  分辨率: {current_res_zh}", f"  Resolution: {current_res_en}", lang))
        print(f"  模型: {current_model}")
        print(_text(f"  参考图: {reference_path or '无'}", f"  Reference: {reference_path or 'None'}", lang))
        print(f"  输出: {default_output}")

        print()
        _safe_print("菜单:", "Menu:", lang)
        print("  1) 配置画幅")
        print("  2) 配置分辨率")
        print("  3) 开始生图")
        print("  4) 配置模型族")
        print("  5) 配置参考图")
        print("  6) 配置默认输出路径")
        print("  7) 查看可用模型")
        print("  8) 切换语言")
        print("  0) 退出")

        try:
            choice = _ask(_text("请选择", "Select", lang), default="3")
        except InputClosed:
            _safe_print("输入结束，已退出", "Input closed, exited", lang)
            return 0

        if choice == "1":
            aspect = _choose_aspect(aspect, family, families, lang)
        elif choice == "2":
            upscale = _choose_resolution(upscale, lang)
        elif choice == "3":
            try:
                asyncio.run(
                    _generate_once(
                        family=family,
                        aspect=aspect,
                        upscale=upscale,
                        default_output=default_output,
                        reference_path=reference_path,
                        families=families,
                        lang=lang,
                    )
                )
            except KeyboardInterrupt:
                print()
                _safe_print("已中断当前任务", "Current task interrupted", lang)
            except InputClosed:
                print()
                _safe_print("输入结束，已退出", "Input closed, exited", lang)
                return 0
            except Exception as e:
                print()
                print(_text(f"错误: 生成失败: {e}", f"Error: generation failed: {e}", lang))
        elif choice == "4":
            family = _choose_family(family, families, lang)
            if aspect not in families.get(family, []):
                aspect = families[family][0]
        elif choice == "5":
            try:
                reference_path = _ask(
                    _text("输入参考图路径（留空清空）", "Input reference image path (empty to clear)", lang),
                    default=reference_path,
                )
            except InputClosed:
                _safe_print("输入结束，已退出", "Input closed, exited", lang)
                return 0
        elif choice == "6":
            try:
                default_output = _ask(
                    _text("输入默认输出路径", "Input default output path", lang),
                    default=default_output,
                )
            except InputClosed:
                _safe_print("输入结束，已退出", "Input closed, exited", lang)
                return 0
        elif choice == "7":
            print()
            _safe_print("可用模型列表：", "Available models:", lang)
            for model_id, conf in IMAGE_MODELS.items():
                print(f"  - {model_id} :: {conf.get('description', '')}")
        elif choice == "8":
            lang = _choose_language(lang)
            _safe_print("完成: 语言已更新", "Done: language updated", lang)
        elif choice == "0":
            _safe_print("已退出", "Exited", lang)
            return 0
        else:
            _safe_print("提示: 无效选项", "Tip: invalid option", lang)


if __name__ == "__main__":
    raise SystemExit(main())
