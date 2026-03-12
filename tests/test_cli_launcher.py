from __future__ import annotations

import socket
from pathlib import Path

import pandas as pd
import pytest

from src.cli import main as cli_main
from src import launcher as launcher_module
from src.launcher import HttpProbeResult, find_available_port


class _FakeProcess:
    def __init__(self, wait_code: int = 0, poll_code: int | None = None) -> None:
        self._wait_code = wait_code
        self.returncode = poll_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        if self.returncode is None:
            self.returncode = self._wait_code
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        if self.returncode is None:
            self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        if self.returncode is None:
            self.returncode = 0


def _build_sample_excel(path: Path) -> None:
    sheet = pd.DataFrame(
        [
            {
                "Unnamed: 0": "供应商 : 普通供应商A",
                "开单日期": "",
                "单据号": "",
                "品名规格": "",
                "金额": "",
            },
            {
                "Unnamed: 0": "",
                "开单日期": "2022-01-01",
                "单据号": "001",
                "品名规格": "项目A[20250102-21021212]",
                "金额": "100",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sheet.to_excel(writer, index=False, sheet_name="2022年")


def test_cli_default_exports_all_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_excel = tmp_path / "input.xlsx"
    output_dir = tmp_path / "outputs"
    _build_sample_excel(input_excel)

    monkeypatch.setattr("src.cli.generate_brief_pdf", lambda _bundle: b"%PDF-1.4\nbrief")
    monkeypatch.setattr("src.cli.generate_full_pdf", lambda _bundle: b"%PDF-1.4\nfull")

    result = cli_main(["report", "--input", str(input_excel), "--output", str(output_dir)])
    assert result == 0

    assert (output_dir / "供应商年度分析简报.pdf").exists()
    assert (output_dir / "供应商年度分析完整报告.pdf").exists()
    assert (output_dir / "供应商年度分析结果.xlsx").exists()
    assert (output_dir / "表A_供应商年度汇总.csv").exists()
    assert (output_dir / "表B_年度总览.csv").exists()
    assert (output_dir / "表C_年度金额环比.csv").exists()


def test_find_available_port_skips_occupied_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)

    try:
        occupied_port = sock.getsockname()[1]
        chosen_port = find_available_port(preferred_port=occupied_port, max_tries=10)
    finally:
        sock.close()

    assert chosen_port != occupied_port
    assert chosen_port > occupied_port


def test_probe_streamlit_readiness_accepts_health_ok_and_root_not_404(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_responses = {
        "http://127.0.0.1:8501/_stcore/health": HttpProbeResult(status_code=200, body="ok"),
        "http://127.0.0.1:8501/": HttpProbeResult(status_code=200, body="<html>"),
    }
    monkeypatch.setattr(launcher_module, "_http_get", lambda url: fake_responses[url])

    readiness = launcher_module.probe_streamlit_readiness("127.0.0.1", 8501)

    assert readiness.ready is True
    assert readiness.health_ok is True
    assert readiness.root_ok is True


def test_probe_streamlit_readiness_rejects_404(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_responses = {
        "http://127.0.0.1:8501/_stcore/health": HttpProbeResult(status_code=404, body="not found"),
        "http://127.0.0.1:8501/": HttpProbeResult(status_code=200, body="<html>"),
    }
    monkeypatch.setattr(launcher_module, "_http_get", lambda url: fake_responses[url])

    readiness = launcher_module.probe_streamlit_readiness("127.0.0.1", 8501)

    assert readiness.ready is False
    assert readiness.health_ok is False
    assert readiness.root_ok is True


def test_probe_streamlit_readiness_rejects_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_responses = {
        "http://127.0.0.1:8501/_stcore/health": HttpProbeResult(status_code=None, error="connection refused"),
        "http://127.0.0.1:8501/": HttpProbeResult(status_code=None, error="connection refused"),
    }
    monkeypatch.setattr(launcher_module, "_http_get", lambda url: fake_responses[url])

    readiness = launcher_module.probe_streamlit_readiness("127.0.0.1", 8501)

    assert readiness.ready is False
    assert readiness.health_ok is False
    assert readiness.root_ok is False


def test_run_streamlit_server_loads_config_before_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit import config as streamlit_config
    from streamlit.web import bootstrap

    script_path = Path("/tmp/fake_streamlit_app.py")
    monkeypatch.setattr(launcher_module, "_resolve_streamlit_script", lambda: script_path)
    monkeypatch.setattr(streamlit_config, "_main_script_path", "", raising=False)

    calls: list[str] = []
    captured: dict[str, object] = {}

    def fake_load_config_options(flag_options: dict[str, object]) -> None:
        calls.append("load")
        captured["load_flags"] = dict(flag_options)

    def fake_run(main_script_path: str, is_hello: bool, args: list[str], flag_options: dict[str, object]) -> None:
        calls.append("run")
        captured["main_script_path"] = main_script_path
        captured["is_hello"] = is_hello
        captured["args"] = list(args)
        captured["run_flags"] = dict(flag_options)

    monkeypatch.setattr(bootstrap, "load_config_options", fake_load_config_options)
    monkeypatch.setattr(bootstrap, "run", fake_run)

    launcher_module._run_streamlit_server("127.0.0.1", 9321)

    assert calls == ["load", "run"]
    assert streamlit_config._main_script_path == str(script_path.resolve())
    assert captured["main_script_path"] == str(script_path.resolve())
    assert captured["is_hello"] is False
    assert captured["args"] == []

    flags = captured["load_flags"]
    assert flags == captured["run_flags"]
    assert flags["server_address"] == "127.0.0.1"
    assert flags["server_port"] == 9321
    assert flags["server_baseUrlPath"] == ""
    assert flags["server_headless"] is True
    assert flags["global_developmentMode"] is False
    assert flags["browser_gatherUsageStats"] is False


def test_parent_retries_next_port_when_root_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher_module, "MAX_PORT_TRIES", 2)
    monkeypatch.setattr(launcher_module.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(launcher_module, "is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(launcher_module, "_build_worker_env", lambda: {"FOO": "BAR"})

    all_processes = [_FakeProcess(), _FakeProcess()]
    created_processes = list(all_processes)
    popen_calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_popen(command: list[str], env: dict[str, str] | None = None) -> _FakeProcess:
        popen_calls.append((command, env))
        return created_processes.pop(0)

    readiness_results = iter([(False, "root=404"), (True, "ok")])
    waited_ports: list[int] = []

    def fake_wait_for_http_ready(
        host: str,
        port: int,
        timeout_sec: float = 20.0,
        child: _FakeProcess | None = None,
    ) -> tuple[bool, str]:
        _ = host, timeout_sec, child
        waited_ports.append(port)
        return next(readiness_results)

    monkeypatch.setattr(launcher_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(launcher_module, "wait_for_http_ready", fake_wait_for_http_ready)

    browser_opened: list[str] = []
    monkeypatch.setattr(launcher_module.webbrowser, "open", lambda url: browser_opened.append(url))

    exit_code = launcher_module._run_parent("127.0.0.1", preferred_port=8501, no_browser=True)

    assert exit_code == 0
    assert waited_ports == [8501, 8502]
    assert popen_calls[0][0][-1] == "8501"
    assert popen_calls[1][0][-1] == "8502"
    assert popen_calls[0][1] == {"FOO": "BAR"}
    assert all_processes[0].terminated is True
    assert browser_opened == []


def test_parent_reports_child_early_exit_without_opening_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher_module, "MAX_PORT_TRIES", 1)
    monkeypatch.setattr(launcher_module.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(launcher_module, "is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(
        launcher_module.subprocess,
        "Popen",
        lambda _command, env=None: _FakeProcess(poll_code=3),
    )
    monkeypatch.setattr(
        launcher_module,
        "wait_for_http_ready",
        lambda _host, _port, timeout_sec=20.0, child=None: (False, "子进程提前退出，返回码=3"),
    )

    browser_opened: list[str] = []
    monkeypatch.setattr(launcher_module.webbrowser, "open", lambda url: browser_opened.append(url))

    with pytest.raises(RuntimeError, match="返回码=3"):
        launcher_module._run_parent("127.0.0.1", preferred_port=8501, no_browser=False)

    assert browser_opened == []
