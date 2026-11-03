"""豆包客户端订阅额度查询（登录态自动发现）。

原理：豆包 Windows 客户端（Chromium 系）运行时，登录会话 cookie
（sessionid + x-tt-multi-sids）以明文存在于进程内存与浏览器存储中。
通过只读内存扫描自动获取这两个 cookie，然后调用订阅配额汇总接口：

    POST https://www.doubao.com/alice/commerce/sale/subscription/quota/summary/
        ?version_code=...&device_platform=web&aid=582478...

返回（实测结构）：
    data.window_limit_section.window_limit_groups[].window_limits[]
        window_type=1  → 5 小时窗口（total_amount/used_amount/used_percent）
        window_type=2  → 周窗口
    data.incentive_quota_section.window_limit_groups[]  → 活动赠送额度（window_type=3）
    data.current_subscription                            → 订阅产品与到期时间

凭据优先级：设置页手动粘贴 → 内存扫描（客户端运行时） → DPAPI 加密缓存。
读取成功自动写缓存，之后即使客户端关闭也可继续显示。
接口未公开，可能随平台调整而失效。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import time
import urllib.error

from ..model import QuotaResult
from .base import Provider, http_post_json

QUOTA_URL = (
    "https://www.doubao.com/alice/commerce/sale/subscription/quota/summary/"
    "?version_code=20800&language=zh&device_platform=web"
    "&doubao_device_platform=desktop&aid=582478&real_aid=582478"
    "&pkg_type=release_version&device_id=177462281012986"
    "&pc_version=2.34.6&doubao_pc_version=2.34.6"
    "&web_id=7662832405736687142&tea_uuid=177462281012986"
    "&region=CN&sys_region=CN&samantha_web=1&web_platform=desktop"
    "&use-olympus-account=1&runtime=web&runtime_version=3.43.4"
    "&client_platform=pc_client&chromium_version=147.0.7727.149"
    "&channel=win&fp=verify_177462281012986"
    "&web_tab_id=02a97436-86cc-479a-95e7-e9d72a76bcd1"
    "3cDRZCyMClyVuhHP15QC1Z3FJhTbiokKaQPNpw")

_WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Doubao/2.34.6")

# ---------------- 凭据读取 ----------------

_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_MEM_COMMIT = 0x1000
_PROTECT_READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}


class _MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("PartitionId", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def _cache_path() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "QuotaBoard",
                        "doubao_session.cache")


def _read_cache() -> dict:
    try:
        p = _cache_path()
        if os.path.isfile(p):
            from ..config import decrypt_secret
            raw = decrypt_secret(open(p, "r", encoding="utf-8").read().strip())
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("sessionid"):
                return data
    except Exception:
        pass
    return {}


def _write_cache(data: dict) -> None:
    try:
        from ..config import encrypt_secret
        p = _cache_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(encrypt_secret(json.dumps(data, ensure_ascii=False)))
    except Exception:
        pass


def _list_processes(name_part: str) -> list[int]:
    k32 = ctypes.windll.kernel32
    TH32CS_SNAPPROCESS = 0x00000002

    class _PE(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_wchar * 260),
        ]

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wt.HANDLE(-1).value:
        return []
    pids = []
    try:
        pe = _PE()
        pe.dwSize = ctypes.sizeof(_PE)
        if not k32.Process32FirstW(snap, ctypes.byref(pe)):
            return []
        while True:
            if name_part.lower() in pe.szExeFile.lower():
                pids.append(int(pe.th32ProcessID))
            if not k32.Process32NextW(snap, ctypes.byref(pe)):
                break
    finally:
        k32.CloseHandle(snap)
    return pids


def _scan_process(pid: int, pats: list[tuple[re.Pattern, str]],
                  cap: int = 40) -> list[tuple[str, str]]:
    """只读扫描进程内存，返回 [(name, matched_text)]。"""
    k32 = ctypes.windll.kernel32
    ph = k32.OpenProcess(_PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ,
                         False, pid)
    if not ph:
        return []
    out: list[tuple[str, str]] = []
    try:
        addr = 0
        mbi = _MBI()
        while True:
            if k32.VirtualQueryEx(ph, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)) == 0:
                break
            size = mbi.RegionSize
            if mbi.State == _MEM_COMMIT and mbi.Protect in _PROTECT_READABLE:
                chunk = ctypes.create_string_buffer(size)
                read = ctypes.c_size_t(0)
                if k32.ReadProcessMemory(ph, ctypes.c_void_p(addr), chunk, size,
                                         ctypes.byref(read)):
                    data = chunk.raw[:read.value]
                    for pat, name in pats:
                        for m in pat.finditer(data):
                            out.append((name, m.group(0)[:300]))
                            if len(out) >= cap:
                                return out
            addr += size
            if addr > 0x7FFFFFFFFFFFFFFF:
                break
    finally:
        k32.CloseHandle(ph)
    return out


_SESSIONID_RE = re.compile(rb'sessionid[=:]["\']?\s*([0-9a-fA-F]{32})')
_SIDS_RE = re.compile(
    rb'x-tt-multi-sids["\']?\s*[:=]\s*["\']?([0-9]{10,20}%3A[0-9a-fA-F]{20,40})')
_SIDS_JSON_RE = re.compile(rb'"(?:x-tt-multi-sids|multi_sids)"\s*:\s*"([^"]{20,80})"')


def _scan_session(manual: str = "") -> tuple[bool, str, dict]:
    """获取 sessionid + x-tt-multi-sids。

    优先级：手动粘贴（JSON 或 "sessionid|multi_sids"）→ 内存扫描 → 缓存。
    返回 (是否成功, 错误说明, 凭据 dict)。
    """
    def _parse_manual(m: str) -> dict | None:
        m = m.strip()
        try:
            obj = json.loads(m)
            if isinstance(obj, dict) and obj.get("sessionid"):
                return {"sessionid": str(obj["sessionid"]).strip(),
                        "multi_sids": str(obj.get("multi_sids", "")).strip()}
        except Exception:
            pass
        parts = [p.strip() for p in re.split(r"[|;,\n]", m) if p.strip()]
        if len(parts) >= 1 and re.fullmatch(r"[0-9a-fA-F]{32}", parts[0]):
            return {"sessionid": parts[0],
                    "multi_sids": parts[1] if len(parts) > 1 else ""}
        return None

    if manual:
        cred = _parse_manual(manual)
        if cred:
            return True, "", cred
        return False, ("手动填写的豆包 sessionid 格式不正确（应为 32 位十六进制，"
                       "可选用 | 分隔 x-tt-multi-sids）", {})

    pids = _list_processes("Doubao")
    if pids:
        pats = [(_SESSIONID_RE, "sid"), (_SIDS_RE, "sids"), (_SIDS_JSON_RE, "sids_json")]
        hits: list[tuple[str, str]] = []
        for pid in pids:
            hits = _scan_process(pid, pats)
            if hits:
                break
        sessionids: set[str] = set()
        multis: set[str] = set()
        for name, text in hits:
            txt = text.decode("ascii", "ignore")
            if name == "sid":
                m = re.search(r"[0-9a-fA-F]{32}", txt)
                if m:
                    sessionids.add(m.group(0))
            else:
                m = re.search(r"[0-9]{10,20}%3A[0-9a-fA-F]{20,40}", txt)
                if m:
                    multis.add(m.group(0))
        if sessionids:
            cred = {"sessionid": next(iter(sessionids)),
                    "multi_sids": next(iter(multis)) if multis else ""}
            _write_cache(cred)
            return True, "", cred

    cached = _read_cache()
    if cached:
        return True, "", cached
    return False, ("未检测到豆包客户端登录态：请先打开豆包客户端并登录"
                   "（或在设置中手动粘贴 sessionid）", {})


# ---------------- 接口调用与解析 ----------------


def _fmt_amount(v) -> str:
    try:
        return f"{float(str(v).replace(',', '')):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


class DoubaoProvider(Provider):
    key = "doubao"
    label = "豆包"

    def _request(self, cred: dict) -> dict:
        """POST 配额汇总接口。"""
        cookie = f"sessionid={cred['sessionid']}"
        if cred.get("multi_sids"):
            cookie += f"; x-tt-multi-sids={cred['multi_sids']}"
        return http_post_json(QUOTA_URL, {}, headers={
            "User-Agent": _WEB_UA,
            "Referer": "https://www.doubao.com/member/quota-management",
            "Origin": "https://www.doubao.com",
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie,
        }, timeout=20)

    def fetch(self) -> QuotaResult:
        manual = str(self.cfg.get("manual_sessionid", "") or "").strip()
        ok, msg, cred = _scan_session(manual=manual)
        if not ok:
            return self.err(msg)

        try:
            data = self._request(cred)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return self.err("登录态已失效，请重新打开豆包客户端登录一次")
            return self.err(f"请求失败：HTTP {e.code}")
        except Exception as e:
            return self.err(f"请求失败：{e}")

        if not isinstance(data, dict) or data.get("code") not in (0, None):
            return self.err(f"接口返回异常：{str(data)[:120]}")

        payload = data.get("data") or {}
        if not isinstance(payload, dict):
            return self.err("响应缺少 data 字段")

        # ---- 提取额度窗口 ----
        windows: list[dict] = []  # (label, used_percent, total, used, end_ts)
        section = payload.get("window_limit_section") or {}
        groups = section.get("window_limit_groups") or []
        for g in groups:
            if not isinstance(g, dict):
                continue
            for w in g.get("window_limits") or []:
                if not isinstance(w, dict):
                    continue
                wtp = w.get("window_type")
                pct = _num(w.get("used_percent"))
                if wtp == 1:
                    windows.append({"label": "5h", "pct": pct,
                                    "total": _fmt_amount(w.get("total_amount")),
                                    "used": _fmt_amount(w.get("used_amount")),
                                    "end": _num(w.get("end_time"))})
                elif wtp == 2:
                    windows.append({"label": "周", "pct": pct,
                                    "total": _fmt_amount(w.get("total_amount")),
                                    "used": _fmt_amount(w.get("used_amount")),
                                    "end": _num(w.get("end_time"))})

        # 活动赠送额度（window_type=3）
        bonus_pct = bonus_total = bonus_used = bonus_end = None
        bonus_section = payload.get("incentive_quota_section") or {}
        for g in bonus_section.get("window_limit_groups") or []:
            if not isinstance(g, dict):
                continue
            for w in g.get("window_limits") or []:
                if isinstance(w, dict) and w.get("window_type") == 3:
                    bonus_pct = _num(w.get("used_percent"))
                    bonus_total = _fmt_amount(w.get("total_amount"))
                    bonus_used = _fmt_amount(w.get("used_amount"))
                    bonus_end = _num(w.get("end_time"))

        if not windows:
            return self.err("响应未包含有效额度窗口（接口可能已调整）")

        # ---- 主显示：剩余百分比 ----
        parts = [f"{w['label']} {100 - w['pct']:.0f}%" for w in windows]
        display = " · ".join(parts)
        remaining = [100 - w["pct"] for w in windows if w["pct"] is not None]
        percent = min(remaining) if remaining else None

        def _fmt_reset(ts, fmt: str) -> str:
            import datetime
            try:
                dt = datetime.datetime.fromtimestamp(ts / 1000)
                return dt.strftime(fmt)
            except (TypeError, ValueError, OSError):
                return ""

        # 每个窗口：{label, percent(剩余), note(重置时间)}
        # 5h 显示时分（如「5h重置 21:10」）；周显示日期（如「周重置 11-03 21:04」）
        # 活动赠送（window_type=3）不在悬浮窗显示
        metrics = []
        for w in windows:
            if w["pct"] is None:
                continue
            fmt = "%m-%d %H:%M" if w["label"] == "周" else "%H:%M"
            reset = _fmt_reset(w["end"], fmt)
            metrics.append({
                "label": w["label"],
                "percent": 100 - w["pct"],
                "resets_at": w['end']/1000 if w.get('end') else None,
                "note": f"{w['label']}重置 {reset}" if reset
                        else f"{w['label']} {w['used']} / {w['total']}",
            })

        # ---- 订阅信息 ----
        note_parts: list[str] = []
        for w in windows:
            if w["pct"] is None:
                continue
            fmt = "%m-%d %H:%M" if w["label"] == "周" else "%H:%M"
            reset = _fmt_reset(w["end"], fmt)
            if reset:
                note_parts.append(f"{w['label']}重置 {reset}")
        sub = payload.get("current_subscription") or {}
        subscription_expires_at = ''
        subscription_plan = ''
        if isinstance(sub, dict):
            product = sub.get('display') or {}
            if isinstance(product, dict):
                subscription_plan = str(product.get('short_name') or product.get('product_name') or '').strip()
            end_ts = _num(sub.get("end_time"))
            if end_ts and end_ts > 0:
                from ..subscription import subscription_date
                subscription_expires_at = subscription_date(end_ts)
                if subscription_expires_at:
                    note_parts.append(f"{subscription_expires_at[:10]}到期")

        return QuotaResult(
            platform=self.key, label=self.label, display=display,
            available=None, used=None, total=None, unit="",
            percent=percent, ok=True,
            sub_note=" · ".join(note_parts), metrics=metrics,
            subscription_expires_at=subscription_expires_at,
            subscription_plan=subscription_plan,
            subscription_source='订阅接口' if subscription_expires_at else '',
        )

    def debug_fetch(self) -> tuple[bool, str, object]:
        """供测试与联调。"""
        manual = str(self.cfg.get("manual_sessionid", "") or "").strip()
        ok, msg, cred = _scan_session(manual=manual)
        if not ok:
            return False, msg, None
        try:
            data = self._request(cred)
            return True, "ok", data
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}", None
        except Exception as e:
            return False, str(e), None
