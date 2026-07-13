from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
API_PYTHON = ROOT / ".venv-api" / "Scripts" / "python.exe"
API_SOURCE = ROOT / "apps" / "api" / "src"
WEB_PATH = ROOT / "apps" / "web"


def fail(message: str) -> None:
    print(f"[coc-star] {message}", file=sys.stderr)
    raise SystemExit(1)


def launch(command: list[str], environment: dict[str, str], title: str) -> None:
    if os.name != "nt":
        fail("当前一键启动脚本面向 Windows，请分别启动 API 和 Web 服务。")
    subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=False,
    )
    print(f"已启动：{title}")


def main() -> None:
    if not API_PYTHON.exists():
        fail(f"未找到后端 Python 环境：{API_PYTHON}")
    if not (WEB_PATH / "package.json").exists():
        fail(f"未找到前端项目：{WEB_PATH}")

    corepack = shutil.which("corepack.cmd") or shutil.which("corepack")
    if corepack is None:
        fail("未找到 Corepack，请先安装 Node.js 或启用 Corepack。")

    api_environment = os.environ.copy()
    api_environment["PYTHONPATH"] = str(API_SOURCE)
    launch(
        [
            str(API_PYTHON),
            "-m",
            "uvicorn",
            "coc_star_api.main:app",
            "--reload",
            "--app-dir",
            str(API_SOURCE),
        ],
        api_environment,
        "API http://127.0.0.1:8000",
    )

    web_environment = os.environ.copy()
    web_environment["COREPACK_HOME"] = str(ROOT / ".corepack")
    launch(
        [corepack, "pnpm", "--dir", str(WEB_PATH), "dev"],
        web_environment,
        "Web http://localhost:5173",
    )

    print("浏览器地址：http://localhost:5173")


if __name__ == "__main__":
    main()
