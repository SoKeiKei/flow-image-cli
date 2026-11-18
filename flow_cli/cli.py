"""
Flow CLI - 图片与视频生成命令行入口
"""

import argparse
import sys

from .gflow_bridge import (
    clear_fixed_project,
    get_fixed_project,
    run_gflow,
    set_fixed_project,
)
from .migrated_image import print_current_models


def main():
    """主入口"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) > 1 and sys.argv[1] in {"auth", "image", "video"}:
        return run_gflow(sys.argv[1], sys.argv[2:])

    parser = argparse.ArgumentParser(
        prog="flow-cli",
        description="供 Agent 直接调用的 Flow 图片与视频生成命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用真实 Chrome 登录
  flow-cli auth login --browser chrome

  # 图片生成
  flow-cli image t2i "电影感的雨夜街道" --model nano2 -o street.png

  # flow.google.com 上只有 Omni 模型（omni-flash、omni-1.2-flash）接受 --duration；Veo 省略时长（默认 8 秒）
  flow-cli video t2v "薄雾中的竹林" --model omni-flash --duration 4 -o bamboo.mp4
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    subparsers.add_parser("models", aliases=["m", "media-models"], help="列出当前图片与视频模型")

    project_parser = subparsers.add_parser(
        "project", help="设置生成任务复用的 Flow 项目"
    )
    project_subparsers = project_parser.add_subparsers(dest="project_action")
    project_use_parser = project_subparsers.add_parser("use", help="固定使用指定项目")
    project_use_parser.add_argument("project_id", help="Flow 项目 ID")
    project_subparsers.add_parser("show", help="显示当前固定项目")
    project_subparsers.add_parser("clear", help="取消固定项目（不会删除网页项目）")

    subparsers.add_parser(
        "auth",
        help="使用真实 Chrome 登录 Flow（推荐）",
    )

    subparsers.add_parser(
        "image",
        help="通过成熟组件生成最新 Flow 图片",
    )

    subparsers.add_parser(
        "video",
        help="生成 Flow 视频（Omni 1.1 / 1.2 Flash、Veo 3.1；具体能力由 gflow-cli 提供）",
    )

    args = parser.parse_args()

    if args.command in ["models", "m", "media-models"]:
        return print_current_models()
    elif args.command == "project":
        return cmd_project(args)
    else:
        parser.print_help()
        return 0


def cmd_project(args):
    """管理新图片和视频命令默认复用的 Flow 项目。"""
    if args.project_action == "use":
        try:
            set_fixed_project(args.project_id)
        except ValueError as error:
            print(f"错误: {error}")
            return 1
        print("完成: 后续图片和视频生成将默认复用这个 Flow 项目")
        return 0

    if args.project_action == "clear":
        clear_fixed_project()
        print("完成: 已取消固定项目，Flow 网页中的项目没有被删除")
        return 0

    project_id = get_fixed_project()
    if project_id:
        print(f"当前固定项目: {project_id}")
    else:
        print("当前未设置固定项目")
    return 0


if __name__ == "__main__":
    sys.exit(main())
