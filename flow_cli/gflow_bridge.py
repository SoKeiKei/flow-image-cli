"""将成熟的 gflow-cli 能力桥接到 flow-cli。"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


_PROJECT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_GENERATION_COMMANDS = {
    "image": {"t2i", "i2i"},
    "video": {"t2v", "i2v", "r2v"},
}


def _state_path() -> Path:
    config_dir = Path(os.environ.get("FLOW_CLI_HOME", Path.home() / ".flow-cli"))
    return config_dir / "fixed-flow-project.json"


def get_fixed_project() -> str | None:
    """读取需要复用的 Flow 项目。"""
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    project_id = data.get("project_id")
    if isinstance(project_id, str) and _PROJECT_ID_PATTERN.fullmatch(project_id):
        return project_id
    return None


def set_fixed_project(project_id: str) -> Path:
    """保存后续生成任务默认复用的 Flow 项目。"""
    if not _PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("项目 ID 格式不正确")
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"project_id": project_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def clear_fixed_project() -> bool:
    """清除固定项目设置，不删除 Flow 网页里的项目。"""
    path = _state_path()
    if not path.exists():
        return False
    path.unlink()
    return True


def _with_fixed_project(command: str, arguments: Sequence[str]) -> list[str]:
    forwarded = list(arguments)
    if not forwarded or forwarded[0] not in _GENERATION_COMMANDS.get(command, set()):
        return forwarded
    if "--project" in forwarded or any(arg.startswith("--project=") for arg in forwarded):
        return forwarded
    project_id = get_fixed_project()
    if project_id:
        forwarded.extend(["--project", project_id])
    return forwarded


def run_gflow(
    command: str,
    arguments: Sequence[str],
    *,
    show_help_when_empty: bool = True,
) -> int:
    """在当前 Python 环境中运行 gflow-cli，并原样返回退出码。"""
    if importlib.util.find_spec("gflow_cli") is None:
        print("错误: 视频组件未安装，请重新运行: py -m pip install -e .")
        return 2

    forwarded_arguments = _with_fixed_project(command, arguments)
    if not forwarded_arguments and show_help_when_empty:
        forwarded_arguments.append("--help")

    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("GFLOW_CLI_OUTPUT_DIR", str(Path.cwd() / "output"))

    process = subprocess.run(
        [sys.executable, "-m", "gflow_cli", command, *forwarded_arguments],
        env=environment,
        check=False,
    )
    return process.returncode
