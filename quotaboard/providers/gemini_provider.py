"""Gemini 客户端订阅额度查询（本地登录态自动发现，纯后端协议）。

原理：Gemini Windows 桌面客户端（Electron/Chromium）登录会话 cookie 以
v10 加密存放在 %APPDATA%\\gemini\\Network\\Cookies（SQLite，被进程独占锁），
key 来自 %APPDATA%\\gemini\\Local State 的 os_crypt.encrypted_key（DPAPI 保护）。

链路（均实测打通）：
1. VSS 卷影复制被锁的 Cookies 文件到 %TEMP%\\gemini_cookies_vss.db（提权 helper）
2. DPAPI 解出 AES-256 key → AESGCM 解 v10 cookie → latin-1 保留原始字节
3. 剥离固定 32 字节前缀（Chromium 存储混淆层）得到纯 ASCII 认证串
4. GET https://gemini.google.com/app 提取 batchexecute 所需 SNlM0e token
5. POST _/BardChatUi/data/batchexecute (rpcids=jSf9Qc) 返回用量窗口：
   [tier, [[remaining, usage_level, metric_type, [[reset_ts, ns]]], ...], use_overage]
   metric_type: 1=5h 窗口, 2=周窗口；usage_level 为已用比例（0-1）

解密结果缓存到 %APPDATA%\\QuotaBoard\\gemini_cookie.cache（DPAPI 加密），
避免每次刷新都触发 UAC 提权；登录态失效时自动重新提取。
"""
from __future__ import annotations

import hashlib
import base64
import io
import http.cookiejar
import json
import os
import random
import re
import sqlite3
from ..background_process import run_hidden
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from ..model import QuotaResult
from .base import Provider

GEMINI_DIR = os.path.join(os.environ.get("APPDATA", ""), "gemini")
COOKIES_DB = os.path.join(GEMINI_DIR, "Network", "Cookies")
LOCAL_STATE = os.path.join(GEMINI_DIR, "Local State")
VSS_DB = os.path.join(os.environ.get("TEMP", "."), "gemini_cookies_vss.db")
CACHE_PATH = os.path.join(os.environ.get("APPDATA", ""), "QuotaBoard",
                          "gemini_cookie.cache")

PROXY_CANDIDATES = ["http://127.0.0.1:7897"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
PREFIX_BYTES = 32  # Chromium cookie 值固定混淆前缀长度

TIER_LABEL = {1: "FREE", 2: "PRO", 3: "ULTRA", 4: "PLUS", 6: "ULTRA"}
METRIC_LABEL = {1: "5h", 2: "周"}


# ---------------- DPAPI / AESGCM 工具 ----------------

def _dpapi_unprotect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ct: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key).decrypt(nonce, ct, None)


# ---------------- 缓存 ----------------

def _read_cache() -> dict | None:
    try:
        if os.path.isfile(CACHE_PATH):
            with open(CACHE_PATH, "rb") as f:
                raw = _dpapi_unprotect(f.read())
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and data:
                return data
    except Exception:
        pass
    return None


def _write_cache(cookies: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        raw = json.dumps(cookies, ensure_ascii=False).encode("utf-8")
        with open(CACHE_PATH, "wb") as f:
            f.write(_dpapi_protect(raw))
    except Exception:
        pass


def _clear_cache() -> None:
    try:
        if os.path.isfile(CACHE_PATH):
            os.remove(CACHE_PATH)
    except Exception:
        pass


# ---------------- VSS 提权读取被锁的 Cookies ----------------

_TASK_NAME = "QuotaBoardGeminiVSS"
_SCHTASKS = (r"C:\Windows\System32\schtasks.exe"
             if os.path.isfile(r"C:\Windows\System32\schtasks.exe")
             else "schtasks.exe")
_PWSH = (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
         if os.path.isfile(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
         else "powershell.exe")


def _schtasks(*args: str) -> bool:
    """调用 schtasks，成功返回 True（退出码 0 即成功，如 /Query 找到任务）。"""
    try:
        r = run_hidden([_SCHTASKS, *args], capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _schtasks_xml() -> str:
    """读出计划任务定义；任务不存在或读取失败返回空串。"""
    try:
        r = run_hidden([_SCHTASKS, "/Query", "/TN", _TASK_NAME, "/XML"],
                       capture_output=True, text=True, timeout=60)
        return r.stdout or "" if r.returncode == 0 else ""
    except Exception:
        return ""


def _task_target() -> tuple[str, str]:
    """计划任务该执行什么：打包态用自身 GUI exe（Subsystem=window，无控制台），
    源码态才用 python 跑 helper。"""
    if getattr(sys, "frozen", False):
        # 打包态：exe 自身带 --gemini-vss 分支（main.py 注册）
        return sys.executable, "--gemini-vss"
    script = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "gemini_vss_helper.py"))
    return sys.executable, "-u \"%s\"" % script


def _task_matches(xml_text: str) -> bool:
    """任务里的可执行文件必须就是当前程序。

    历史遗留的任务可能还指向某个 python 解释器，这种任务以最高权限运行时会
    弹出一个「管理员: ...python.exe」黑底控制台窗口，还会抢走前台焦点，
    表现为桌面和任务栏跟着抽搐一下——所以宁可让 VSS 这条路失败，也不执行它。"""
    exe, _ = _task_target()
    if not xml_text or not exe:
        return False
    normalized = xml_text.replace("/", "\\").lower()
    return exe.replace("/", "\\").lower() in normalized


def _ensure_task() -> bool:
    """确保 VSS 计划任务存在、且指向当前程序（首次创建弹一次 UAC，之后静默运行）。"""
    if _task_matches(_schtasks_xml()):
        return True
    exe, args = _task_target()
    user = os.environ.get("USERNAME", "")
    ps = (
        "$action = New-ScheduledTaskAction -Execute \"%s\" -Argument \"%s\";"
        "$trigger = New-ScheduledTaskTrigger -Once -At \"23:59\";"
        "$principal = New-ScheduledTaskPrincipal -UserId \"%s\" -RunLevel Highest "
        "-LogonType Interactive;"
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
        "-DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5);"
        "Register-ScheduledTask -TaskName \"%s\" -Action $action -Trigger $trigger "
        "-Principal $principal -Settings $settings -Force | Out-Null"
        % (exe, args, user, _TASK_NAME))
    b64 = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    try:
        r = run_hidden([_PWSH, "-NoProfile", "-NonInteractive", "-EncodedCommand", b64],
                           capture_output=True, timeout=180)
        if r.returncode != 0:
            return False
    except Exception:
        return False
    # 重建需要管理员权限：没权限时任务还是老样子，此时必须放弃，绝不拿旧任务去跑
    return _task_matches(_schtasks_xml())


def _run_vss_helper() -> bool:
    """通过计划任务以最高权限运行 helper，复制 Cookies 到 %TEMP%。"""
    if not _ensure_task():
        return False
    before = os.stat(VSS_DB).st_mtime_ns if os.path.isfile(VSS_DB) else None
    if not _schtasks("/Run", "/TN", _TASK_NAME):
        return False
    import time
    # 卷影创建 + 复制约 10-40s，轮询最多 120s
    for _ in range(120):
        if (os.path.isfile(VSS_DB) and os.path.getsize(VSS_DB) > 0
                and os.stat(VSS_DB).st_mtime_ns != before):
            return True
        time.sleep(1)
    return False


def _vss_extract_cookies() -> dict | None:
    """提权复制被锁 Cookies → 主进程解密 → 剥前缀 → 纯 ASCII cookie dict。"""
    if not _run_vss_helper():
        return None
    try:
        aes_key = _load_aes_key()
        with sqlite3.connect(VSS_DB) as con:
            rows = con.execute(
                "SELECT host_key, name, encrypted_value FROM cookies ORDER BY last_access_utc ASC").fetchall()
        out = {}
        for host, name, enc in rows:
            if host not in (".google.com", "google.com", "gemini.google.com", ".gemini.google.com"):
                continue
            if not enc or enc[:3] != b"v10":
                continue
            try:
                plain = _aes_gcm_decrypt(aes_key, enc[3:15], enc[15:])
            except Exception:
                continue
            if plain[:32] == hashlib.sha256(host.encode("utf-8")).digest():
                plain = plain[32:]
            val = plain.decode("latin-1")
            # 剥离固定混淆前缀（Chromium 存储层），得到真实 ASCII 值
            if not val.isascii() and len(val) > PREFIX_BYTES:
                val = val[PREFIX_BYTES:]
            if val.isascii() and len(val) > 0:
                out[name] = val
        if out:
            _write_cache(out)
            return out
    except Exception:
        pass
    return None


def _load_aes_key() -> bytes:
    with open(LOCAL_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)
    enc_key = state["os_crypt"]["encrypted_key"]
    # encrypted_key 为 base64（"DPAPI" + 二进制 DPAPI 密文）
    raw = base64.b64decode(enc_key.encode("ascii"))
    assert raw[:5] == b"DPAPI", "unexpected encrypted_key format"
    return _dpapi_unprotect(raw[5:])


# ---------------- 协议调用 ----------------

class _Opener:
    """带代理候选的 opener：优先 127.0.0.1:7897，失败回退直连。"""

    def __init__(self) -> None:
        self._opener = None
        self._jar = http.cookiejar.CookieJar()
        self._cookies_seeded = False
        self._direct = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    def _ensure(self) -> None:
        if self._opener is not None:
            return
        for proxy in PROXY_CANDIDATES:
            try:
                op = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                    urllib.request.HTTPCookieProcessor(self._jar))
                test = urllib.request.Request("https://gemini.google.com/",
                                              method="HEAD")
                test.add_header("User-Agent", UA)
                op.open(test, timeout=5).close()
                self._opener = op
                return
            except Exception:
                continue
        self._opener = self._direct

    def open(self, req: urllib.request.Request, timeout: float = 25):
        self._ensure()
        header = req.get_header("Cookie")
        if header and not self._cookies_seeded:
            for part in header.split(";"):
                name, sep, value = part.strip().partition("=")
                if sep:
                    self._jar.set_cookie(http.cookiejar.Cookie(0,name,value,None,False,".google.com",True,True,"/",True,True,None,True,None,None,{}))
            self._cookies_seeded = True
        req.remove_header("Cookie")
        return self._opener.open(req, timeout=timeout)


def _ascii_cookie_header(cookies: dict) -> str:
    return "; ".join("%s=%s" % (k, v) for k, v in cookies.items())


def _fetch_snlm0e(opener: _Opener, cookie_header: str) -> str:
    req = urllib.request.Request("https://gemini.google.com/app")
    req.add_header("User-Agent", UA)
    req.add_header("Accept-Language", "en-US,en;q=0.9")
    req.add_header("Cookie", cookie_header)
    resp = opener.open(req, timeout=30)
    text = resp.read(2_000_000).decode("utf-8", "replace")
    m = re.search(r'"SNlM0e":\s*"([^"]*)"', text)
    if not m:
        raise GeminiSessionError("Gemini 未返回登录校验参数，需要重新连接客户端登录态")
    return m.group(1)


def _fetch_usage(opener: _Opener, cookie_header: str, at: str) -> list:
    """调用 GET_USAGE_INFO RPC，返回原始窗口列表。"""
    reqid = random.randint(10000, 99999)
    params = urllib.parse.urlencode({
        "rpcids": "jSf9Qc", "hl": "en", "_reqid": reqid,
        "rt": "c", "source-path": "/usage",
    })
    url = "https://gemini.google.com/_/BardChatUi/data/batchexecute?%s" % params
    f_req = json.dumps([[["jSf9Qc", "[]", None, "generic"]]])
    body = urllib.parse.urlencode({"at": at, "f.req": f_req}).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    req.add_header("User-Agent", UA)
    req.add_header("Cookie", cookie_header)
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    req.add_header("Origin", "https://gemini.google.com")
    req.add_header("Referer", "https://gemini.google.com/")
    req.add_header("X-Same-Domain", "1")
    req.add_header("x-goog-ext-525001261-jspb",
                   "[1,null,null,null,null,null,null,null,[4,5,6,8],"
                   "null,null,null,null,null,null,null]")
    req.add_header("x-goog-ext-73010989-jspb", "[0]")
    resp = opener.open(req, timeout=30)
    text = resp.read(2_000_000).decode("utf-8", "replace")
    # 响应形如 `)]}'\n\n199\n[["wrb.fr","jSf9Qc","<inner>",...],...]\n25\n[...]`，
    # 每行独立 JSON；目标行首元素为 ["wrb.fr","jSf9Qc",...]
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, list):
            continue
        for item in row:
            if (isinstance(item, list) and len(item) >= 3
                    and str(item[1]) == "jSf9Qc" and isinstance(item[2], str)):
                return json.loads(item[2])
    raise RuntimeError("batchexecute 未返回用量数据")


def _fmt_reset(ts: float, fmt: str) -> str:
    import datetime
    try:
        return datetime.datetime.fromtimestamp(ts).strftime(fmt)
    except (TypeError, ValueError, OSError):
        return ""


class GeminiSessionError(RuntimeError):
    pass


class GeminiProvider(Provider):
    _next_reconnect = 0.0
    key = "gemini"
    label = "Gemini"

    def _get_cookies(self) -> dict:
        """缓存 → VSS 提权提取；空则抛异常。"""
        cached = _read_cache()
        if cached:
            return cached
        if time.monotonic() < type(self)._next_reconnect:
            raise GeminiSessionError("Gemini 需重新连接，10分钟内不重复提取登录态")
        extracted = _vss_extract_cookies()
        if not extracted:
            raise RuntimeError(
                "无法读取 Gemini 客户端登录态：请先打开 Gemini 客户端并登录，"
                "然后重试（首次会弹出一次管理员授权窗口）")
        return extracted

    def _query(self, cookies: dict) -> list:
        opener = _Opener()
        cookie_header = _ascii_cookie_header(cookies)
        at = _fetch_snlm0e(opener, cookie_header)
        return _fetch_usage(opener, cookie_header, at)

    def _query_with_recovery(self, cookies):
        try:
            return self._query(cookies)
        except (GeminiSessionError, urllib.error.HTTPError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (400,401,403):
                raise
            if time.monotonic() < type(self)._next_reconnect:
                raise GeminiSessionError("Gemini 需重新连接：请确认客户端可用，稍后重试（10分钟内不重复提取登录态）")
            type(self)._next_reconnect = time.monotonic() + 600
            fresh = _vss_extract_cookies()
            if not fresh:
                raise GeminiSessionError("未能读取最新登录态，请检查 Gemini 客户端与管理员读取任务")
            try:
                body = self._query(fresh)
            except (GeminiSessionError, urllib.error.HTTPError):
                _clear_cache()
                raise GeminiSessionError("最新登录态仍未通过 Gemini 校验，可能需要客户端重新验证或接口适配；10分钟后可重试")
            type(self)._next_reconnect = 0.0
            return body

    def fetch(self) -> QuotaResult:
        try:
            cookies = self._get_cookies()
        except Exception as e:
            return self.err(str(e))

        try:
            body = self._query_with_recovery(cookies)
        except urllib.error.HTTPError as e:
            # 401/403/400：登录态失效，清缓存下次自动重提
            if e.code in (400, 401, 403):
                _clear_cache()
                return self.err("登录态已失效，正在重新读取客户端登录态（刷新一次即可）")
            return self.err(f"请求失败：HTTP {e.code}")
        except Exception as e:
            return self.err(f"请求失败：{e}")

        if not isinstance(body, list) or len(body) < 3:
            return self.err("用量接口返回异常（接口可能已调整）")

        try:
            tier = int(body[0] or 0)
            windows = body[1] or []
            metrics: list[dict] = []
            parts: list[str] = []
            for item in windows:
                if not isinstance(item, list) or len(item) < 4:
                    continue
                remaining = item[0]
                usage_level = float(item[1] or 0)
                metric_type = int(item[2] or 0)
                reset_ts = None
                if isinstance(item[3], list) and item[3] and isinstance(item[3][0], list):
                    try:
                        reset_ts = float(item[3][0][0])
                    except (TypeError, ValueError):
                        reset_ts = None
                label = METRIC_LABEL.get(metric_type, f"窗口{metric_type}")
                pct = max(0.0, min(100.0, 100.0 - usage_level * 100.0))
                note = ""
                if reset_ts:
                    fmt = "%m-%d %H:%M" if label == "周" else "%H:%M"
                    reset = _fmt_reset(reset_ts, fmt)
                    if reset:
                        note = f"{label}重置 {reset}"
                        parts.append(note)
                metrics.append({"label": label, "percent": pct, "note": note,"resets_at":reset_ts})
            if not metrics:
                return self.err("响应未包含有效用量窗口（接口可能已调整）")
            # 展示顺序：5h 在前、周在后（与豆包/ChatGPT 一致）
            metrics.sort(key=lambda m: 0 if m["label"] == "5h" else 1)
            display = " · ".join(f"{m['label']} {m['percent']:.0f}%" for m in metrics)
            note_parts = [m["note"] for m in metrics if m.get("note")]
            sub_note = TIER_LABEL.get(tier, f"T{tier}")
            if note_parts:
                sub_note += " · " + " · ".join(note_parts)
            return QuotaResult(
                platform=self.key, label=self.label, display=display,
                available=None, used=None, total=None, unit="",
                percent=min(m["percent"] for m in metrics),
                ok=True, sub_note=sub_note, metrics=metrics,
                subscription_note='当前额度接口未提供订阅到期时间，请在 Google One 订阅管理中查看。',
                subscription_plan=TIER_LABEL.get(tier, '').title(),
            )
        except (TypeError, ValueError) as e:
            return self.err(f"用量数据解析失败：{e}")

    def debug_fetch(self) -> tuple[bool, str, object]:
        """供测试与联调。"""
        try:
            cookies = self._get_cookies()
        except Exception as e:
            return False, str(e), None
        try:
            body = self._query(cookies)
            return True, "ok", body
        except Exception as e:
            return False, str(e), None
