from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
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

    cloudflared = (
        shutil.which("cloudflared.exe")
        or shutil.which("cloudflared")
        or str(Path.home() / "cloudflared.exe")
    )
    if not Path(cloudflared).exists():
        print("未检测到 cloudflared，已跳过公网隧道。安装后再次运行即可自动开启。")
        print("安装方式：winget install Cloudflare.cloudflared")
        print("         或下载 cloudflared-windows-amd64.exe 到用户目录")
    else:
        print("等待 Web 服务就绪...", end="", flush=True)
        for _ in range(30):
            try:
                with socket.create_connection(("127.0.0.1", 5173), timeout=1):
                    print(" 就绪")
                    break
            except OSError:
                time.sleep(1)
                print(".", end="", flush=True)
        else:
            print(" 超时，仍尝试启动隧道")
        launch(
            [cloudflared, "tunnel", "--url", "http://127.0.0.1:5173"],
            os.environ.copy(),
            "Cloudflare 临时隧道（请复制 trycloudflare.com 地址）",
        )


if __name__ == "__main__":
    main()
