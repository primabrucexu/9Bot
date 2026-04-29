from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from app.config import Settings
from app.services import stock_screener


class JiuyangongsheDiagramError(Exception):
    pass


@dataclass(frozen=True)
class JygsPaths:
    frontend_dir: Path
    root_dir: Path
    auth_dir: Path
    storage_state_path: Path
    diagrams_dir: Path
    state_path: Path
    login_signal_path: Path
    login_status_path: Path


_LOGIN_PROCESS: subprocess.Popen | None = None
_LOGIN_POLL_INTERVAL_SECONDS = 0.5
_LOGIN_STARTUP_GRACE_SECONDS = 0.4
_LOGIN_COMPLETE_TIMEOUT_SECONDS = 90.0
_ACTIVE_LOGIN_FLOW_STATUSES = {"starting", "waiting", "saving"}


def build_paths(settings: Settings) -> JygsPaths:
    root_dir = settings.data_dir / "jygs"
    auth_dir = root_dir / "auth"
    return JygsPaths(
        frontend_dir=settings.project_root.parent / "frontend",
        root_dir=root_dir,
        auth_dir=auth_dir,
        storage_state_path=auth_dir / "storage-state.json",
        diagrams_dir=root_dir / "diagrams",
        state_path=root_dir / "state.json",
        login_signal_path=auth_dir / "login-complete.signal",
        login_status_path=auth_dir / "login-status.json",
    )


def resolve_fetch_dates(
    *,
    exact_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    latest: bool = False,
) -> list[date]:
    latest_trade_date = stock_screener._resolve_latest_trade_date()
    trading_dates = _load_trading_dates(latest_trade_date)
    trading_date_set = set(trading_dates)

    if exact_date:
        target_date = _parse_date(exact_date)
        if target_date not in trading_date_set:
            raise JiuyangongsheDiagramError(f"{exact_date} 不是交易日，无法抓取涨停简图。")
        return [target_date]

    if start_date:
        start = _parse_date(start_date)
        end = _parse_date(end_date) if end_date else latest_trade_date
        if start > end:
            raise JiuyangongsheDiagramError("开始日期不能晚于结束日期。")

        resolved = [trade_day for trade_day in trading_dates if start <= trade_day <= end]
        if not resolved:
            raise JiuyangongsheDiagramError("选定区间内没有交易日可抓取。")
        return resolved

    if end_date:
        raise JiuyangongsheDiagramError("单独传入结束日期没有意义，请同时提供开始日期。")

    if latest or not any([exact_date, start_date, end_date]):
        return [latest_trade_date]

    raise JiuyangongsheDiagramError("无法解析抓图日期参数。")


def start_login(settings: Settings, target_date: str | None = None) -> dict[str, Any]:
    global _LOGIN_PROCESS

    paths = build_paths(settings)
    login_flow = _read_login_flow(paths)
    if login_flow["status"] in _ACTIVE_LOGIN_FLOW_STATUSES and _get_login_process() is not None:
        raise JiuyangongsheDiagramError("已有进行中的网页登录流程，请先完成当前登录。")

    _cleanup_login_artifacts(paths)
    _ensure_parent_directory(paths.storage_state_path)
    _ensure_parent_directory(paths.login_status_path)

    login_date = target_date or stock_screener._resolve_latest_trade_date().isoformat()
    login_url = f"https://www.jiuyangongshe.com/action/{login_date}"
    _write_login_flow(
        paths,
        status="starting",
        message="正在启动 Edge 登录窗口，请稍候。",
        login_url=login_url,
    )

    command = _build_node_command(
        paths.frontend_dir / "scripts" / "jygs-login.mjs",
        [
            "--storage-state",
            str(paths.storage_state_path),
            "--url",
            login_url,
            "--signal-file",
            str(paths.login_signal_path),
            "--status-file",
            str(paths.login_status_path),
        ],
    )

    try:
        _LOGIN_PROCESS = subprocess.Popen(
            command,
            cwd=paths.frontend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        _LOGIN_PROCESS = None
        _write_login_flow(
            paths,
            status="failed",
            message="未找到 node，请先安装 Node.js。",
            login_url=login_url,
        )
        raise JiuyangongsheDiagramError("未找到 node，请先安装 Node.js。") from exc

    time.sleep(_LOGIN_STARTUP_GRACE_SECONDS)
    process = _get_login_process()
    if process is None:
        login_flow = _read_login_flow(paths)
        raise JiuyangongsheDiagramError(login_flow["message"] or "启动网页登录失败。")

    return get_status(settings)


def complete_login(settings: Settings, timeout_seconds: float = _LOGIN_COMPLETE_TIMEOUT_SECONDS) -> dict[str, Any]:
    paths = build_paths(settings)
    login_flow = _read_login_flow(paths)
    process = _get_login_process()

    if process is None:
        if login_flow["status"] == "saved" and paths.storage_state_path.exists():
            return get_status(settings)
        raise JiuyangongsheDiagramError("当前没有进行中的网页登录流程，请先点击“启动登录”。")

    _ensure_parent_directory(paths.login_signal_path)
    paths.login_signal_path.write_text("complete\n", encoding="utf-8")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(_LOGIN_POLL_INTERVAL_SECONDS)
        login_flow = _read_login_flow(paths)
        if login_flow["status"] == "saved" and paths.storage_state_path.exists():
            _get_login_process()
            return get_status(settings)
        if login_flow["status"] == "failed":
            _get_login_process()
            raise JiuyangongsheDiagramError(login_flow["message"] or "保存登录态失败。")
        if _get_login_process() is None:
            if paths.storage_state_path.exists():
                return get_status(settings)
            raise JiuyangongsheDiagramError(login_flow["message"] or "登录窗口已关闭，请重新开始。")

    raise JiuyangongsheDiagramError("等待保存登录态超时，请确认已在弹出的 Edge 窗口完成登录。")


def get_status(settings: Settings) -> dict[str, Any]:
    paths = build_paths(settings)
    return {
        "login_ready": paths.storage_state_path.exists(),
        "storage_state_path": str(paths.storage_state_path),
        "login_flow": _read_login_flow(paths),
        "latest": get_latest_entry(settings),
    }


def get_latest_entry(settings: Settings) -> dict[str, Any] | None:
    paths = build_paths(settings)
    state = _read_state(paths)
    dates = state.get("dates", {})
    if not isinstance(dates, dict):
        return None

    for trade_day in sorted(dates.keys(), reverse=True):
        item = dates.get(trade_day)
        if not isinstance(item, dict):
            continue
        try:
            output_path = _resolve_diagram_file(paths, trade_day)
        except JiuyangongsheDiagramError:
            continue
        return {
            "date": trade_day,
            "status": item.get("status", "downloaded"),
            "output_path": str(output_path),
            "source_image_url": item.get("image_url"),
            "updated_at": item.get("updated_at"),
        }
    return None


def resolve_diagram_file(settings: Settings, trade_date: str) -> Path:
    return _resolve_diagram_file(build_paths(settings), trade_date)


def run_login(settings: Settings, target_date: str | None = None) -> dict[str, Any]:
    paths = build_paths(settings)
    _ensure_parent_directory(paths.storage_state_path)
    login_date = target_date or stock_screener._resolve_latest_trade_date().isoformat()
    login_url = f"https://www.jiuyangongshe.com/action/{login_date}"
    command = _build_node_command(
        paths.frontend_dir / "scripts" / "jygs-login.mjs",
        ["--storage-state", str(paths.storage_state_path), "--url", login_url],
    )
    _run_interactive_command(command, cwd=paths.frontend_dir)
    return {
        "storage_state_path": str(paths.storage_state_path),
        "login_url": login_url,
    }


def fetch_diagrams(
    settings: Settings,
    *,
    exact_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    latest: bool = False,
    force: bool = False,
    interval_ms: int = 1000,
) -> dict[str, Any]:
    paths = build_paths(settings)
    _ensure_parent_directory(paths.storage_state_path)
    paths.diagrams_dir.mkdir(parents=True, exist_ok=True)

    login_flow = _read_login_flow(paths)
    if login_flow["status"] in _ACTIVE_LOGIN_FLOW_STATUSES and _get_login_process() is not None:
        raise JiuyangongsheDiagramError("网页登录仍在进行中，请先完成登录态保存。")

    requested_dates = resolve_fetch_dates(
        exact_date=exact_date,
        start_date=start_date,
        end_date=end_date,
        latest=latest,
    )
    requested_date_strings = [trade_day.isoformat() for trade_day in requested_dates]
    pending_dates = requested_date_strings if force else _filter_missing_dates(paths, requested_date_strings)
    skipped_dates = [trade_day for trade_day in requested_date_strings if trade_day not in pending_dates]

    if not pending_dates:
        summary = {
            "requested_dates": requested_date_strings,
            "fetched": [],
            "skipped": skipped_dates,
            "state_path": str(paths.state_path),
        }
        _update_state(paths, summary)
        return summary

    if not paths.storage_state_path.exists():
        raise JiuyangongsheDiagramError(
            f"未找到登录态文件：{paths.storage_state_path}。请先完成网页登录并保存登录态。"
        )

    args = [
        "--storage-state",
        str(paths.storage_state_path),
        "--output-dir",
        str(paths.diagrams_dir),
        "--interval-ms",
        str(interval_ms),
    ]
    for trade_day in pending_dates:
        args.extend(["--date", trade_day])

    command = _build_node_command(paths.frontend_dir / "scripts" / "jygs-fetch.mjs", args)
    payload = _run_json_command(command, cwd=paths.frontend_dir)
    fetched = payload.get("results")
    if not isinstance(fetched, list):
        raise JiuyangongsheDiagramError("抓图脚本返回结果格式不正确。")

    summary = {
        "requested_dates": requested_date_strings,
        "fetched": fetched,
        "skipped": skipped_dates,
        "state_path": str(paths.state_path),
    }
    _update_state(paths, summary)
    return summary


def _parse_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise JiuyangongsheDiagramError(f"日期格式不正确：{raw_value}，应为 YYYY-MM-DD。") from exc


def _load_trading_dates(latest_trade_date: date) -> list[date]:
    try:
        trade_calendar = stock_screener.ak.tool_trade_date_hist_sina()
    except Exception as exc:  # pragma: no cover - upstream dependency
        raise JiuyangongsheDiagramError(f"获取交易日历失败：{exc}") from exc

    if trade_calendar.empty or "trade_date" not in trade_calendar.columns:
        raise JiuyangongsheDiagramError("交易日历数据不可用。")

    return [trade_day for trade_day in trade_calendar["trade_date"].tolist() if trade_day <= latest_trade_date]


def _filter_missing_dates(paths: JygsPaths, dates: list[str]) -> list[str]:
    return [trade_day for trade_day in dates if not any(paths.diagrams_dir.glob(f"{trade_day}.*"))]


def _build_node_command(script_path: Path, args: list[str]) -> list[str]:
    return ["node", str(script_path), *args]


def _run_interactive_command(command: list[str], *, cwd: Path) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise JiuyangongsheDiagramError("未找到 node，请先安装 Node.js。") from exc
    except subprocess.CalledProcessError as exc:
        raise JiuyangongsheDiagramError(f"执行命令失败：{' '.join(command)}") from exc


def _run_json_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise JiuyangongsheDiagramError("未找到 node，请先安装 Node.js。") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip() or f"命令执行失败：{' '.join(command)}"
        raise JiuyangongsheDiagramError(message) from exc

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise JiuyangongsheDiagramError("抓图脚本输出不是合法 JSON。") from exc


def _read_state(paths: JygsPaths) -> dict[str, Any]:
    if not paths.state_path.exists():
        return {"dates": {}}

    try:
        return json.loads(paths.state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JiuyangongsheDiagramError(f"状态文件损坏：{paths.state_path}") from exc


def _update_state(paths: JygsPaths, summary: dict[str, Any]) -> None:
    state = _read_state(paths)
    state.setdefault("dates", {})
    now = datetime.now(UTC).isoformat(timespec="seconds")

    for trade_day in summary["skipped"]:
        existing = state["dates"].get(trade_day, {})
        state["dates"][trade_day] = {
            **existing,
            "status": existing.get("status", "skipped"),
            "updated_at": now,
        }

    for item in summary["fetched"]:
        trade_day = item["date"]
        state["dates"][trade_day] = {
            "status": item.get("status", "downloaded"),
            "output_path": item.get("outputPath"),
            "image_url": item.get("imageUrl"),
            "updated_at": now,
        }

    state["last_run"] = {
        "requested_dates": summary["requested_dates"],
        "skipped": summary["skipped"],
        "fetched_count": len(summary["fetched"]),
        "updated_at": now,
    }

    _ensure_parent_directory(paths.state_path)
    paths.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_parent_directory(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def _resolve_diagram_file(paths: JygsPaths, trade_date: str) -> Path:
    matched_files = sorted(paths.diagrams_dir.glob(f"{trade_date}.*"))
    if not matched_files:
        raise JiuyangongsheDiagramError(f"未找到 {trade_date} 对应的涨停简图文件。")
    return matched_files[0]


def _cleanup_login_artifacts(paths: JygsPaths) -> None:
    for file_path in (paths.login_signal_path, paths.login_status_path):
        if file_path.exists():
            file_path.unlink()


def _read_login_flow(paths: JygsPaths) -> dict[str, Any]:
    status = {
        "status": "idle",
        "message": None,
        "login_url": None,
        "updated_at": None,
    }
    if paths.login_status_path.exists():
        try:
            loaded = json.loads(paths.login_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JiuyangongsheDiagramError(f"登录状态文件损坏：{paths.login_status_path}") from exc
        if isinstance(loaded, dict):
            status = {
                "status": str(loaded.get("status") or "idle"),
                "message": loaded.get("message"),
                "login_url": loaded.get("login_url"),
                "updated_at": loaded.get("updated_at"),
            }

    if status["status"] in _ACTIVE_LOGIN_FLOW_STATUSES and _get_login_process() is None:
        if paths.storage_state_path.exists():
            status = {
                **status,
                "status": "saved",
                "message": "登录态已保存。",
                "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        else:
            status = {
                **status,
                "status": "failed",
                "message": "登录窗口已关闭，请重新开始。",
                "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        _write_login_flow(
            paths,
            status=status["status"],
            message=status["message"],
            login_url=status["login_url"],
            updated_at=status["updated_at"],
        )
    return status


def _write_login_flow(
    paths: JygsPaths,
    *,
    status: str,
    message: str | None,
    login_url: str | None,
    updated_at: str | None = None,
) -> None:
    payload = {
        "status": status,
        "message": message,
        "login_url": login_url,
        "updated_at": updated_at or datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _ensure_parent_directory(paths.login_status_path)
    paths.login_status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_login_process() -> subprocess.Popen | None:
    global _LOGIN_PROCESS
    if _LOGIN_PROCESS is not None and _LOGIN_PROCESS.poll() is not None:
        _LOGIN_PROCESS = None
    return _LOGIN_PROCESS
