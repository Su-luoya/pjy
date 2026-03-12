"""Windows-friendly launcher for bundled Streamlit app."""

from __future__ import annotations

import argparse
import atexit
from dataclasses import dataclass
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8501
MAX_PORT_TRIES = 200
HTTP_PROBE_TIMEOUT_SEC = 0.8


@dataclass(frozen=True)
class HttpProbeResult:
    status_code: int | None
    body: str = ""
    error: str = ""


@dataclass(frozen=True)
class HttpReadiness:
    health_ok: bool
    root_ok: bool
    detail: str

    @property
    def ready(self) -> bool:
        return self.health_ok and self.root_ok


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


def _http_get(url: str, timeout_sec: float = HTTP_PROBE_TIMEOUT_SEC) -> HttpProbeResult:
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = response.read(512).decode("utf-8", errors="ignore")
            return HttpProbeResult(status_code=response.getcode(), body=body)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(512).decode("utf-8", errors="ignore")
        except OSError:
            body = ""
        return HttpProbeResult(status_code=exc.code, body=body, error=str(exc))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HttpProbeResult(status_code=None, error=str(exc))


def probe_streamlit_readiness(host: str, port: int) -> HttpReadiness:
    base_url = f"http://{host}:{port}"
    health = _http_get(f"{base_url}/_stcore/health")
    root = _http_get(f"{base_url}/")

    health_ok = health.status_code == 200 and health.body.strip().lower() == "ok"
    root_ok = root.status_code is not None and root.status_code != 404

    health_code = "n/a" if health.status_code is None else str(health.status_code)
    root_code = "n/a" if root.status_code is None else str(root.status_code)
    health_body = health.body.strip().replace("\n", " ")
    detail = (
        f"health={health_code} body={health_body!r} err={health.error or '-'}; "
        f"root={root_code} err={root.error or '-'}"
    )
    return HttpReadiness(health_ok=health_ok, root_ok=root_ok, detail=detail)


def wait_for_http_ready(
    host: str,
    port: int,
    timeout_sec: float = 20.0,
    child: subprocess.Popen[bytes] | None = None,
) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_sec
    last_detail = "尚未探测到 HTTP 响应"
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            return False, f"子进程提前退出，返回码={child.returncode}"
        readiness = probe_streamlit_readiness(host, port)
        last_detail = readiness.detail
        if readiness.ready:
            return True, last_detail
        time.sleep(0.3)
    return False, f"HTTP 就绪超时（{timeout_sec:.1f}s），最后状态：{last_detail}"


def wait_for_service(host: str, port: int, timeout_sec: float = 20.0) -> bool:
    ready, _status = wait_for_http_ready(host, port, timeout_sec=timeout_sec)
    return ready


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
        "server.baseUrlPath": "",
        "server.headless": True,
        "browser.gatherUsageStats": False,
    }
    bootstrap.run(str(script_path), False, [], flags)


def _build_worker_command(host: str, port: int) -> list[str]:
    if _is_frozen():
        return [sys.executable, "--serve", "--host", host, "--port", str(port)]
    return [sys.executable, "-m", "src.launcher", "--serve", "--host", host, "--port", str(port)]


def _build_worker_env() -> dict[str, str]:
    env = os.environ.copy()
    env["STREAMLIT_SERVER_BASE_URL_PATH"] = ""
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    return env


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _run_parent(host: str, preferred_port: int, no_browser: bool) -> int:
    current_child: subprocess.Popen[bytes] | None = None
    attempted_ports: list[int] = []
    last_status = "未开始探测"

    def _signal_handler(_signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        if current_child is not None:
            _terminate_process(current_child)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    for offset in range(MAX_PORT_TRIES):
        port = preferred_port + offset
        if not is_port_available(host, port):
            continue

        attempted_ports.append(port)
        url = f"http://{host}:{port}"
        child = subprocess.Popen(_build_worker_command(host=host, port=port), env=_build_worker_env())
        current_child = child

        ready, status = wait_for_http_ready(host, port, timeout_sec=25, child=child)
        if not ready:
            last_status = f"{status}；returncode={child.poll()}"
            _terminate_process(child)
            current_child = None
            continue

        if not no_browser:
            webbrowser.open(url)

        print(f"服务已启动：{url}")
        print("按 Ctrl+C 退出。")

        try:
            return child.wait()
        finally:
            _terminate_process(child)
            current_child = None

    attempted = ", ".join(str(p) for p in attempted_ports) or "无可用端口"
    raise RuntimeError(f"服务启动失败。尝试端口：{attempted}。最后状态：{last_status}")


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
