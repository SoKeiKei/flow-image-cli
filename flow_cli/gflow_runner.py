"""以补丁方式启动 gflow-cli。

1. 禁止使用「智能体」界面（2026-11-18 用户定）：所有生成都必须走 Flow 的完整编辑器
   （有"帧/素材"、比例、模型、时长等单次设置的那个），不得向智能体对话框下指令。
   gflow-cli 遇到只有对话框的 agent-only 界面时，原本会改用智能体做文生图/文生视频；
   这里把"智能体界面能不能做"一律改成"不能"，于是 gflow 会先自动关掉智能体开关、
   刷新重试，仍是智能体界面就直接报错（退出码 36），不会向智能体提交任何生成。
   由于智能体路径整体禁用，原来针对它的两个补丁（中文扣费框误读、Omni 1.2 放行）已删除。

隐私：gflow-cli 0.95+ 内置"匿名使用统计"（本地计数 + 每周上传）。本项目一律关闭：
设置 DO_NOT_TRACK / GFLOW_CLI_TELEMETRY，并把记录、告知、上传函数换成空操作。
"""

from __future__ import annotations

import os
from typing import Any, Callable

NO_AGENT_REASON = (
    "智能体生成（flow-cli 已禁用智能体；请在 Flow 网页里把「智能体」开关关掉，"
    "使用带「帧/素材」的完整编辑器）"
)


def refuse_agent(*_args: Any, **_kwargs: Any) -> str:
    """替换 gflow 的 unported_video / unported_image：智能体界面一律不能做。"""
    return NO_AGENT_REASON


def make_refuse_unported(original: Callable[[str], Any]) -> Callable[[str], Any]:
    def refuse_unported(what: str) -> Any:
        if what == NO_AGENT_REASON:
            from gflow_cli.errors import FlowHostMigratedError

            return FlowHostMigratedError(
                detail=(
                    "Flow 现在给这个账号的是只有对话框的智能体界面，而 flow-cli 不使用智能体生成；"
                    "请在 Flow 网页里关闭「智能体」开关后重试"
                )
            )
        return original(what)

    return refuse_unported


def disable_telemetry() -> bool:
    """彻底关闭 gflow-cli 的使用统计：不记录、不提示、不上传。"""
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["GFLOW_CLI_TELEMETRY"] = "0"
    try:
        from gflow_cli import telemetry, telemetry_upload
    except ImportError:
        return False

    def noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    for name in ("record", "record_counter", "record_crash"):
        if hasattr(telemetry, name):
            setattr(telemetry, name, noop)
    if hasattr(telemetry, "maybe_show_notice"):
        telemetry.maybe_show_notice = lambda *_a, **_k: False
    if hasattr(telemetry, "uploads_enabled"):
        telemetry.uploads_enabled = lambda *_a, **_k: False
    for name in ("maybe_upload", "send", "_spawn_sender"):
        if hasattr(telemetry_upload, name):
            setattr(telemetry_upload, name, noop)
    return True


def apply_patch() -> bool:
    disable_telemetry()
    try:
        from gflow_cli.api.transports import agent_only_composer
    except ImportError:
        return False
    if not hasattr(agent_only_composer, "unported_video"):
        return False
    agent_only_composer.unported_video = refuse_agent
    agent_only_composer.unported_image = refuse_agent
    agent_only_composer.refuse_unported = make_refuse_unported(
        agent_only_composer.refuse_unported
    )
    return True


def main() -> None:
    apply_patch()
    from gflow_cli.cli import main as gflow_main

    gflow_main()


if __name__ == "__main__":
    main()
