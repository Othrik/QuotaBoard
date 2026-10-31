"""智谱清言会员额度查询（客户端登录态模式，试点）。

原理：智谱清言 Windows 客户端以明文 SQLite 保存登录 cookies
（%APPDATA%\\chatglm\\Network\\Cookies），其中 chatglm_token 为 JWT。
直接读取后以 Authorization: Bearer 调用会员信息接口：

    GET https://chatglm.cn/chatglm/member-api/member/member_info

返回字段（已从 chatglm.cn 前端 main.js 的 Vuex getters 确认）：
    result.member_info.member_status          会员状态（2=有效会员，3=会员已过期）
    result.member_info.level                  等级（vip / svip）
    result.member_info.token_left_percent     剩余额度百分比（核心展示字段）
    result.member_info.left_score             可用积分
    result.member_info.member_expiration_time 会员到期时间（unix 秒）

鉴权方式经实测确认：服务端识别 Authorization: Bearer；cookie 中的 token
过期时返回 401 {"status":40101,"message":"token is expired"}，此时提示用户
打开智谱清言客户端重新登录（客户端启动会自动续期并写回 cookie）。

接口未公开，可能随平台调整而失效。
"""
from __future__ import annotations

import os
import sqlite3
import urllib.error

from ..model import QuotaResult
from .base import Provider, DEFAULT_HEADERS, http_get_json

MEMBER_URL = "https://chatglm.cn/chatglm/member-api/member/member_info"

# token 过期 / 未登录的响应码（HTTP 401 且 body 含这些 status）
_EXPIRED_STATUS = {"40101", "40002", "40003"}
_UNAUTH_TEXT = ("token is expired", "not login", "unauthorized", "unauthenticated")


def _cookies_db_path() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "chatglm", "Network", "Cookies")


def _cache_path() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "QuotaBoard",
                        "zhipu_token.cache")


def _read_cache() -> str:
    try:
        p = _cache_path()
        if os.path.isfile(p):
            from ..config import decrypt_secret
            return decrypt_secret(open(p, "r", encoding="utf-8").read().strip())
    except Exception:
        pass
    return ""


def _write_cache(token: str) -> None:
    try:
        from ..config import encrypt_secret
        p = _cache_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(encrypt_secret(token))
    except Exception:
        pass


def _read_sqlite_token(db: str) -> str | None:
    """读取 cookies DB 中的 chatglm_token。

    返回 token 字符串；读失败（文件被客户端独占锁定）返回 None；
    成功但无该 cookie 返回 ""。
    """
    def _query(path: str) -> str:
        con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        try:
            cur = con.cursor()
            cur.execute("SELECT name, value FROM cookies WHERE name = ?",
                        ("chatglm_token",))
            row = cur.fetchone()
            return row[1] if row and row[1] else ""
        finally:
            con.close()

    try:
        return _query(db)
    except Exception:
        pass
    # 被客户端独占锁定：复制 Cookies(+journal) 到临时目录再读
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="qb_zhipu_")
    for f in ("Cookies", "Cookies-journal"):
        src = os.path.join(os.path.dirname(db), f)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(tmp, f))
            except Exception:
                pass
    tmp_db = os.path.join(tmp, "Cookies")
    if not os.path.isfile(tmp_db):
        return None
    try:
        return _query(tmp_db)
    except Exception:
        return None


def read_client_token(manual: str = "") -> tuple[bool, str, str]:
    """获取登录 token。优先级：手动粘贴 → Cookies 直读 → 本地加密缓存。

    返回 (是否找到, 错误说明, token)。从 Cookies 成功读取后自动刷新缓存，
    因此客户端运行期间（Cookie 被锁定）可继续使用缓存中的登录态。
    """
    if manual:
        return True, "", manual

    db = _cookies_db_path()
    if os.path.isfile(db):
        token = _read_sqlite_token(db)
        if token is None:
            # 客户端运行中，Cookie 被独占锁定：回退到缓存
            cached = _read_cache()
            if cached:
                return True, "", cached
            return False, (
                "智谱清言客户端正在运行，登录态文件被锁定：请先关闭客户端刷新一次"
                "（仅首次需要），或在设置中手动粘贴 chatglm_token"), ""
        if token:
            _write_cache(token)
            return True, "", token
        return False, "智谱清言客户端未登录（Cookie 中无 chatglm_token）", ""

    cached = _read_cache()
    if cached:
        return True, "", cached
    return False, "未找到智谱清言客户端登录态（未安装客户端或未登录）", ""


def _find(data, keys: tuple[str, ...]):
    """宽容递归查找字段值。"""
    if isinstance(data, dict):
        for k, v in data.items():
            low = str(k).lower()
            if any(key in low for key in keys):
                return v
            hit = _find(v, keys)
            if hit is not None:
                return hit
    elif isinstance(data, list):
        for item in data:
            hit = _find(item, keys)
            if hit is not None:
                return hit
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_member(data) -> dict | None:
    """从接口响应中宽容提取 member_info 字典。"""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("result"), dict) and "member_info" in data["result"]:
        member = data["result"]["member_info"]
    elif any(k in data for k in ("member_status", "level", "token_left_percent",
                                  "member_expiration_time", "left_score")):
        member = data
    else:
        member = _find(data, ("member_info",))
    return member if isinstance(member, dict) else None


class ZhipuMemberProvider(Provider):
    key = "zhipu_member"
    label = "智谱清言"

    def fetch(self) -> QuotaResult:
        manual = str(self.cfg.get("manual_token", "") or "").strip()
        ok, msg, token = read_client_token(manual=manual)
        if not ok:
            return self.err(msg)

        try:
            data = http_get_json(MEMBER_URL, {
                "Authorization": f"Bearer {token}",
                "Referer": "https://chatglm.cn/",
            }, timeout=20)
        except urllib.error.HTTPError as e:
            try:
                body = e.read(300).decode("utf-8", "replace")
            except Exception:
                body = ""
            if e.code == 401 or any(t in body.lower() for t in _UNAUTH_TEXT):
                return self.err("登录态已过期，请打开智谱清言客户端重新登录一次")
            return self.err(f"请求失败：HTTP {e.code} {body[:120]}")
        except Exception as e:
            return self.err(f"请求失败：{e}")

        if isinstance(data, dict) and data.get("status") in (40101, 40002):
            return self.err("登录态已过期，请打开智谱清言客户端重新登录一次")

        member = extract_member(data)
        if member is None:
            return self.err("响应未包含会员信息（接口可能已调整）")

        level = str(member.get("level") or "").upper()
        status = _num(member.get("member_status"))
        percent = _num(member.get("token_left_percent"))
        score = _num(member.get("left_score"))
        expire_ts = _num(member.get("member_expiration_time"))

        # 会员状态：2=有效会员，3=已过期，1/0=非会员（从 JS getters 确认）
        if status == 2:
            status_text = "有效"
        elif status == 3:
            status_text = "已过期"
        else:
            status_text = "非会员"

        if percent is None:
            return self.err("未解析到剩余额度字段（token_left_percent），接口可能已调整")

        note_parts = [f"{level} {status_text}" if level else status_text]
        if expire_ts and expire_ts > 0:
            import datetime
            dt = datetime.datetime.fromtimestamp(expire_ts)
            note_parts.append(f"{dt.year}-{dt.month:02d}-{dt.day:02d}到期")
        if score is not None:
            note_parts.append(f"积分{score:,.0f}")

        return QuotaResult(
            platform=self.key, label=self.label,
            display=f"{percent:.0f}%",
            available=None, used=None, total=None,
            unit="", percent=percent, ok=True,
            sub_note=" · ".join(note_parts),
        )

    def debug_fetch(self) -> tuple[bool, str, object]:
        """供测试与联调：返回 (是否成功, 说明, 原始数据)。"""
        manual = str(self.cfg.get("manual_token", "") or "").strip()
        ok, msg, token = read_client_token(manual=manual)
        if not ok:
            return False, msg, None
        try:
            data = http_get_json(MEMBER_URL, {
                "Authorization": f"Bearer {token}",
                "Referer": "https://chatglm.cn/",
            }, timeout=20)
            return True, "ok", data
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read(300).decode("utf-8", "replace")
            except Exception:
                pass
            return False, f"HTTP {e.code} {body[:150]}", None
        except Exception as e:
            return False, str(e), None
