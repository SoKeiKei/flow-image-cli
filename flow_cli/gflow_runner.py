"""以补丁方式启动 gflow-cli。

gflow-cli 0.96.1 在 agent-only 编辑器上读取"扣费确认框"时，假设文案顺序是
"……N 个视频……X 点数"（先数量后点数），只核对最后一个数字之前的数字。
中文界面的文案相反："要消耗 7 个点数，开始生成这 1 个视频吗？"，点数 7 被误当成
生成数量，导致正常请求被拒绝。这里只为中文确认框按"生成这 N 个"读取数量，
其他文案仍走 gflow-cli 原逻辑。

另外，gflow-cli 0.96.1 在 agent-only 编辑器上拒绝 Omni 1.2 Flash（注明"尚未实测"），
但菜单匹配已内置。2026-11-09 本机实测 `omni-1.2-flash --duration 3` 可正常生成 3 秒视频，
所以只放开这一条拒绝，其余限制照旧。上游修复后可删除本模块。
"""

from __future__ import annotations

import re
from typing import Any, Callable

_ZH_COUNT = re.compile(r"生成[^\d]*(\d+)\s*(?:个|张|条|段)")
_CJK = re.compile(r"[一-鿿]")


def make_gate_quotes_more(
    original: Callable[[str, int], bool | None],
) -> Callable[[str, int], bool | None]:
    def gate_quotes_more(title: str, count: int) -> bool | None:
        if _CJK.search(title):
            match = _ZH_COUNT.search(title)
            # 数量还没渲染出来时返回 None，让 gflow 继续等待，不能批准也不能误拒
            return int(match.group(1)) > count if match else None
        return original(title, count)

    return gate_quotes_more


def make_unported_video(original: Callable[[Any], str | None]) -> Callable[[Any], str | None]:
    def unported_video(request: Any) -> str | None:
        from gflow_cli.api.transports import agent_only_composer as composer

        omni_1_2 = composer.VideoModel.OMNI_1_2_FLASH
        if request.model is not omni_1_2:
            return original(request)
        # 临时按 Omni 1.1 做其余检查（模式、数量、比例等），只跳过 Omni 1.2 这一条
        object.__setattr__(request, "model", composer.VideoModel.OMNI_FLASH)
        try:
            return original(request)
        finally:
            object.__setattr__(request, "model", omni_1_2)

    return unported_video


def apply_patch() -> bool:
    try:
        from gflow_cli.api.transports import agent_only_composer
    except ImportError:
        return False
    current = getattr(agent_only_composer, "gate_quotes_more", None)
    if current is None:
        return False
    agent_only_composer.gate_quotes_more = make_gate_quotes_more(current)
    unported = getattr(agent_only_composer, "unported_video", None)
    if unported is not None and hasattr(agent_only_composer, "VideoModel"):
        agent_only_composer.unported_video = make_unported_video(unported)
    return True


def main() -> None:
    apply_patch()
    from gflow_cli.cli import main as gflow_main

    gflow_main()


if __name__ == "__main__":
    main()
