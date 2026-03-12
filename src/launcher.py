"""Windows-friendly launcher for bundled Streamlit app."""

from __future__ import annotations

import argparse
import atexit
import signal
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8501
MAX_PORT_TRIES = 200


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def find_available_port(
    host: str = DEFAULT_HOST,
    preferred_port: int = DEFAULT_PORT,
    max_tries: int = MAX_PORT_TRIES,
) -> int:
    for offset in range(max_tries):
        candidate = preferred_port + offset
        if is_port_available(host, candidate):
            return candidate
    raise RuntimeError(f"未找到可用端口（起始端口={preferred_port}，尝试次数={max_tries}）。")


def wait_for_service(host: str, port: int, timeout_sec: float = 20.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.2)
    return False


def _create_temp_streamlit_script() -> Path:
    script = tempfile.NamedTemporaryFile(mode="w", suffix="_streamlit_entry.py", delete=False, encoding="utf-8")
    script.write("from src.web_app import run\n")
    script.write("run()\n")
    script.close()

    script_path = Path(script.name)
    atexit.register(lambda: script_path.unlink(missing_ok=True))
    return script_path


def _resolve_streamlit_script() -> Path:
    if _is_frozen():
        return _create_temp_streamlit_script()

    script_path = Path(__file__).resolve().parents[1] / "app.py"
    if not script_path.exists():
        raise FileNotFoundError(f"未找到 Streamlit 入口文件: {script_path}")
    return script_path


def _run_streamlit_server(host: str, port: int) -> None:
    from streamlit.web import bootstrap

    script_path = _resolve_streamlit_script()
    flags = {
        "server.address": host,
        "server.port": port,
        "server.headless": True,
        "browser.gatherUsageStats": False,
    }
    bootstrap.run(str(script_path), False, [], flags)


def _build_worker_command(host: str, port: int) -> list[str]:
    if _is_frozen():
        return [sys.executable, "--serve", "--host", host, "--port", str(port)]
    return [sys.executable, "-m", "src.launcher", "--serve", "--host", host, "--port", str(port)]


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _run_parent(host: str, preferred_port: int, no_browser: bool) -> int:
    port = find_available_port(host=host, preferred_port=preferred_port)
    url = f"http://{host}:{port}"

    child = subprocess.Popen(_build_worker_command(host=host, port=port))

    def _signal_handler(_signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        _terminate_process(child)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if not wait_for_service(host, port, timeout_sec=25):
        _terminate_process(child)
        raise RuntimeError(f"服务启动超时，未能监听 {url}")

    if not no_browser:
        webbrowser.open(url)

    print(f"服务已启动：{url}")
    print("按 Ctrl+C 退出。")

    try:
        return child.wait()
    finally:
        _terminate_process(child)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="supplier-analysis-launcher", description="供应商分析本地启动器")
    parser.add_argument("--serve", action="store_true", help="内部参数：子进程服务模式")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="首选端口，默认 8501")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        _run_streamlit_server(host=args.host, port=args.port)
        return 0

    return _run_parent(host=args.host, preferred_port=args.port, no_browser=args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
