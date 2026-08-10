"""
Flow CLI - 图片与视频生成命令行入口
"""
import argparse
import asyncio
import sys
from pathlib import Path

from .config import get_config
from .models import list_models, DEFAULT_MODEL
from .client import ImageGenerator
from .gflow_bridge import (
    clear_fixed_project,
    get_fixed_project,
    run_gflow,
    set_fixed_project,
)


def main():
    """主入口"""
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

  # 最新图片生成
  flow-cli image t2i "电影感的雨夜街道" --model nano2 -o street.png

  # 最短时长视频生成
  flow-cli video t2v "薄雾中的竹林" --model omni-flash --duration 4 -o bamboo.mp4

  # 文生图
  flow-cli generate "一只可爱的猫咪在花园里玩耍"
  
  # 指定模型和输出路径
  flow-cli gen "山水画" -m gemini-3.0-pro-image-landscape -o landscape.png
  
  # 图生图
  flow-cli gen "将这张图片变成水彩画风格" -r input.jpg -o output.png
  
  # 查看余额
  flow-cli credits
  
  # 登录
  flow-cli login --st "your-session-token"
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    
    gen_parser = subparsers.add_parser("generate", aliases=["gen", "g"], help="生成图片")
    gen_parser.add_argument("prompt", help="图片描述提示词")
    gen_parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"模型名称 (默认: {DEFAULT_MODEL})")
    gen_parser.add_argument("-o", "--output", help="输出文件路径")
    gen_parser.add_argument("-r", "--reference", help="参考图片路径 (图生图)")
    gen_parser.add_argument("-u", "--upscale", choices=["none", "2k", "4k"], default="none", help="放大分辨率 (none/2k/4k)")
    
    subparsers.add_parser("models", aliases=["m"], help="列出可用模型")
    
    subparsers.add_parser("credits", aliases=["c"], help="查询账户余额")
    
    login_parser = subparsers.add_parser("login", aliases=["l"], help="登录并保存 Token")
    login_parser.add_argument("--st", required=True, help="Session Token")
    
    subparsers.add_parser("config", help="显示当前配置")

    project_parser = subparsers.add_parser("project", help="设置生成任务复用的 Flow 项目")
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
        help="生成 Flow 视频（Omni Flash / Veo 3.1）",
    )

    subparsers.add_parser("media-models", help="列出最新图片与视频模型")
    
    args = parser.parse_args()
    
    if args.debug:
        config = get_config()
        config.debug = True
    
    if args.command in ["generate", "gen", "g"]:
        return cmd_generate(args)
    elif args.command in ["models", "m"]:
        return cmd_models()
    elif args.command in ["credits", "c"]:
        return cmd_credits()
    elif args.command in ["login", "l"]:
        return cmd_login(args.st)
    elif args.command == "config":
        return cmd_config()
    elif args.command == "project":
        return cmd_project(args)
    elif args.command == "media-models":
        return run_gflow("models", [], show_help_when_empty=False)
    else:
        parser.print_help()
        return 0


def cmd_generate(args):
    """生成图片"""
    config = get_config()
    
    if not config.token.st:
        print("错误: 未登录，请先运行 'flow-cli login --st <session-token>' 登录")
        return 1
    
    try:
        generator = ImageGenerator()
        
        reference_image = None
        if args.reference:
            ref_path = Path(args.reference)
            if not ref_path.exists():
                print(f"错误: 参考图片不存在: {args.reference}")
                return 1
            reference_image = ref_path.read_bytes()
        
        output_path = args.output
        if not output_path:
            import time
            timestamp = int(time.time())
            output_path = f"output/flow_{timestamp}.png"
        
        result = asyncio.run(generator.generate(
            prompt=args.prompt,
            model=args.model,
            reference_image=reference_image,
            output_path=output_path,
            upscale=args.upscale,
        ))
        
        print("\n完成!")
        if result.startswith("http"):
            print(f"   图片URL: {result}")
        else:
            print(f"   保存路径: {result}")
        
        return 0
        
    except Exception as e:
        print(f"错误: 生成失败: {e}")
        return 1


def cmd_models():
    """列出可用模型"""
    list_models()
    return 0


def cmd_credits():
    """查询余额"""
    config = get_config()
    
    if not config.token.st:
        print("错误: 未登录，请先运行 'flow-cli login --st <session-token>' 登录")
        return 1
    
    try:
        generator = ImageGenerator()
        result = asyncio.run(generator.check_credits())
        
        credits = result.get("credits", 0)
        tier = result.get("userPaygateTier", "未知")
        
        print("\n账户信息")
        print(f"   Credits: {credits}")
        print(f"   等级: {tier}")
        
        return 0
    except Exception as e:
        print(f"错误: 查询失败: {e}")
        return 1


def cmd_login(st: str):
    """登录"""
    config = get_config()
    st_changed = config.token.st != st
    config.token.st = st
    if st_changed:
        config.token.at = ""
        config.token.at_expires = ""
        config.token.project_id = ""
        config.token.user_paygate_tier = "PAYGATE_TIER_NOT_PAID"
    config.save_token()
    
    print("完成: Session Token 已保存")
    if st_changed:
        print("提示: 检测到 ST 变更，已清空旧 AT/Project，后续将自动创建新项目")
    print("\n正在验证 Token...")
    
    try:
        generator = ImageGenerator()
        result = asyncio.run(generator.check_credits())
        
        credits = result.get("credits", 0)
        tier = result.get("userPaygateTier", "未知")
        
        print("完成: 登录成功!")
        print(f"  Credits: {credits}")
        print(f"  等级: {tier}")
        
        return 0
    except Exception as e:
        print(f"提示: Token 验证失败: {e}")
        print("  Token 已保存，但可能无效或已过期")
        return 1


def cmd_config():
    """显示当前配置"""
    config = get_config()
    
    print("\n当前配置")
    print("-" * 40)
    print(f"Flow API: {config.flow.api_base_url}")
    print(f"输出目录: {config.output_dir}")
    print(f"调试模式: {config.debug}")
    print(f"Captcha 方法: {config.captcha.method}")
    print("-" * 40)
    
    if config.token.st:
        print(f"ST: {config.token.st[:20]}...")
    else:
        print("ST: 未配置")
    
    if config.token.at:
        print(f"AT: {config.token.at[:20]}...")
    else:
        print("AT: 未获取")
    
    if config.token.project_id:
        print(f"Project: {config.token.project_id[:20]}...")
    else:
        print("Project: 未创建")
    
    print("-" * 40)
    
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
