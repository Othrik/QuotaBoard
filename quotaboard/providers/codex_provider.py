"""Codex 用量查询（官方本地 app-server，参考 codex-usage-viewer）。

原理：启动官方 codex CLI 的本地 app-server（--stdio），通过 JSON-RPC 行协议
发送 initialize → initialized → account/rateLimits/read，读取其登录的
ChatGPT 账号的 5 小时与每周用量限额。鉴权完全由官方 codex 进程处理
（使用其已登录的 ChatGPT 账号），本模块不接触任何凭据。

前置条件：本机已安装 codex CLI 并完成登录（npm i -g @openai/codex；
codex login 或 codex 首次使用时的登录流程）。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime

from ..model import QuotaResult
from .base import Provider

INITIALIZE_REQ = json.dumps({
    "method": "initialize", "id": 1,
    "params": {"clientInfo": {"name": "quotaboard", "title": "QuotaBoard",
                              "version": "1.0.0"},
               "capabilities": {"experimentalApi": True}},
}, separators=(",", ":"))
INITIALIZED_NOTIFY = json.dumps({"method": "initialized", "params": {}},
                                 separators=(",", ":"))
RATE_LIMITS_REQ = json.dumps({"method": "account/rateLimits/read", "id": 2,
                              "params": None}, separators=(",", ":"))

TIMEOUT_SECONDS = 25


def _classify_error(message: str) -> str:
    m = message or ""
    low = m.lower()
    if any(k in low for k in ("unauthorized", "not logged in", "login")):
        return "未登录 ChatGPT，请先运行 codex login"
    if "timeout" in low:
        return "请求超时"
    if any(k in low for k in ("network", "offline", "connection")):
        return "网络不可用"
    if any(k in low for k in ("500", "502", "503")):
        return "服务暂时异常"
    if "http" in low:
        return "HTTP 状态异常"
    return f"暂时无法获取额度：{m[:100]}"


class CodexProvider(Provider):
    key = "codex"
    label = "ChatGPT"

    def __init__(self, cfg: dict) -> None:
        super().__init__(cfg)
        self.cmd: list[str] | None = cfg.get("cmd")  # 测试时可注入模拟进程

    def _spawn(self) -> subprocess.Popen:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # 后台运行，不弹终端
        if self.cmd:
            return subprocess.Popen(
                self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", creationflags=flags)
        codex = self._find_codex()
        if not codex:
            raise FileNotFoundError(
                "未找到 codex：请安装 Codex CLI（npm i -g @openai/codex）"
                "或 ChatGPT Windows 桌面应用")
        if os.name == "nt" and codex.lower().endswith((".cmd", ".bat")):
            return subprocess.Popen(
                ["cmd", "/c", "codex app-server --stdio -c analytics.enabled=false"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", creationflags=flags)
        return subprocess.Popen(
            [codex, "app-server", "--stdio", "-c", "analytics.enabled=false"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", creationflags=flags)

    @staticmethod
    def _find_codex() -> str | None:
        """定位 codex 可执行文件（结果缓存）：
        1) PATH 中的 codex（npm 安装）；
        2) 用户级 WindowsApps 内捆绑（可枚举）；
        3) 系统级包：Get-AppxPackage 查 InstallLocation（WindowsApps 受 ACL 保护）。
        """
        global _FOUND_CODEX, _FOUND_CODEX_CHECKED
        if _FOUND_CODEX_CHECKED:
            return _FOUND_CODEX
        found = CodexProvider._locate_codex()
        _FOUND_CODEX = found
        _FOUND_CODEX_CHECKED = True
        return found

    @staticmethod
    def _locate_codex() -> str | None:
        import shutil
        found = shutil.which("codex")
        if found:
            return found
        local_root = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                  "Microsoft", "WindowsApps")
        if local_root and os.path.isdir(local_root):
            try:
                entries = os.listdir(local_root)
            except OSError:
                entries = []
            for name in entries:
                if not name.startswith("OpenAI.Codex"):
                    continue
                exe = os.path.join(local_root, name, "app", "resources", "codex.exe")
                if os.path.isfile(exe):
                    return exe
        try:
            ps = CodexProvider._powershell_path()
            if not ps:
                return None
            out = subprocess.run(
                [ps, "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-AppxPackage -Name 'OpenAI.Codex*' | "
                 "Sort-Object Version -Descending | "
                 "Select-Object -First 1).InstallLocation"],
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.strip()
            if out:
                exe = os.path.join(out, "app", "resources", "codex.exe")
                if os.path.isfile(exe):
                    return exe
        except Exception:
            pass
        return None

    @staticmethod
    def _powershell_path() -> str | None:
        import shutil
        for candidate in (
            shutil.which("powershell"),
            shutil.which("pwsh"),
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Windows\sysnative\WindowsPowerShell\v1.0\powershell.exe",
        ):
            if candidate:
                return candidate
        return None

    def fetch(self) -> QuotaResult:
        try:
            proc = self._spawn()
        except FileNotFoundError:
            return self.err(
                "未找到 codex：请安装 Codex CLI（npm i -g @openai/codex）"
                "或 ChatGPT Windows 桌面应用")
        except Exception as e:
            return self.err(f"无法启动 Codex app-server：{e}")

        q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._reader, args=(proc, q), daemon=True).start()

        try:
            self._send(proc, INITIALIZE_REQ)
            self._wait_id(proc, q, 1)
            self._send(proc, INITIALIZED_NOTIFY)
            self._send(proc, RATE_LIMITS_REQ)
            response = self._wait_id(proc, q, 2)
        except Exception as e:
            return self.err(str(e))
        finally:
            self._stop(proc)

        result = self._parse(response)
        if result.ok:
            from ..subscription import read_codex_subscription_expiry
            result.subscription_expires_at = read_codex_subscription_expiry()
            result.subscription_source = '本机登录态' if result.subscription_expires_at else ''
            result.subscription_note = ('登录时记录，续费后可能需要重新登录更新。'
                                        if result.subscription_expires_at else '当前登录态未提供订阅到期时间。')
        return result

    # ---------- 底层 ----------
    @staticmethod
    def _reader(proc, q: queue.Queue) -> None:
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    q.put(line)
        except Exception:
            pass

    @staticmethod
    def _send(proc, message: str) -> None:
        proc.stdin.write(message + "\n")
        proc.stdin.flush()

    def _wait_id(self, proc, q: queue.Queue, expected: int) -> dict:
        deadline = time.time() + TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                line = q.get(timeout=0.25)
            except queue.Empty:
                if proc.poll() is not None:
                    raise RuntimeError("Codex app-server 进程退出，请检查 codex 登录状态")
                continue
            try:
                env = json.loads(line)
            except (ValueError, TypeError):
                continue
            if env.get("id") != expected:
                continue
            if env.get("error"):
                err = env["error"]
                raise RuntimeError(_classify_error(
                    err.get("message") if isinstance(err, dict) else str(err)))
            return env
        raise TimeoutError("Codex app-server 响应超时")

    @staticmethod
    def _stop(proc) -> None:
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            pass

    # ---------- 解析 ----------
    def _parse(self, response: dict) -> QuotaResult:
        try:
            rate_limits = response["result"]["rateLimits"]
        except (KeyError, TypeError):
            return self.err("响应缺少额度字段")

        short: dict | None = None   # 5 小时窗口
        long: dict | None = None    # 周窗口
        for key in ("primary", "secondary"):
            w = rate_limits.get(key)
            if not isinstance(w, dict):
                continue
            try:
                used = int(w["usedPercent"])
                resets = int(w["resetsAt"])
                dur = int(w["windowDurationMins"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (0 <= used <= 100) or resets <= 0 or dur <= 0:
                continue
            if dur < 1440 and dur % 60 == 0:
                short = {"used": used, "resets": resets, "dur": dur}
            elif dur >= 1440 and dur % 1440 == 0:
                long = {"used": used, "resets": resets, "dur": dur}

        if not short and not long:
            return self.err("响应中未找到有效额度窗口")

        parts = []
        if short:
            parts.append(f"5h {100 - short['used']}%")
        if long:
            parts.append(f"周 {100 - long['used']}%")
        display = " · ".join(parts)

        remaining_pcts = [100 - w["used"] for w in (short, long) if w]
        percent = min(remaining_pcts)

        # 双窗口环形图数据：每个 {label, percent(剩余), note(重置时间)}
        metrics = []
        for name, w in (("5h", short), ("周", long)):
            if w:
                local = datetime.fromtimestamp(w["resets"])
                # 5h 窗口显示时分；周窗口显示日期+时分（如「周重置 11-03 20:01」）
                fmt = "%m-%d %H:%M" if name == "周" else "%H:%M"
                metrics.append({
                    "label": name,
                    "percent": 100 - w["used"],
                    "note": f"{name}重置 {local.strftime(fmt)}",
                    "resets_at": w['resets'],
                })

        notes = [m["note"] for m in metrics]
        sub_note = " · ".join(notes)

        return QuotaResult(
            platform=self.key, label=self.label, display=display,
            available=None, used=None, total=None, unit="",
            percent=percent, ok=True, sub_note=sub_note, metrics=metrics,
            subscription_plan={'plus':'Plus','pro':'Pro','team':'Team','business':'Business','enterprise':'Enterprise','edu':'Edu','free':'Free','go':'Go'}.get(str(rate_limits.get('planType','')).lower(), ''),
        )


_FOUND_CODEX: str | None = None
_FOUND_CODEX_CHECKED = False
