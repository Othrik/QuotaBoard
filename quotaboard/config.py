"""配置管理：API Key 本地存储（Windows DPAPI 加密）+ 手动额度 + 刷新缓存。

配置存放于 %APPDATA%/QuotaBoard/config.json，凭据字段以 DPAPI 加密后的
base64 保存，明文不落盘、不出现在日志中。
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
from pathlib import Path
from typing import Any, Optional


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_encrypt(plain: bytes) -> bytes:
    buf = ctypes.create_string_buffer(plain, len(plain))
    blob_in = _DATA_BLOB(len(plain), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(cipher: bytes) -> bytes:
    buf = ctypes.create_string_buffer(cipher, len(cipher))
    blob_in = _DATA_BLOB(len(cipher), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return base64.b64encode(_dpapi_encrypt(value.encode("utf-8"))).decode("ascii")


def decrypt_secret(enc: str) -> str:
    if not enc:
        return ""
    try:
        return _dpapi_decrypt(base64.b64decode(enc.encode("ascii"))).decode("utf-8")
    except Exception:
        return ""


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "refresh_interval_minutes": 30,
    "startup_with_windows": False,
    "platforms": {
        "openai": {"enabled": False, "api_key_enc": ""},
        "chatgpt_plus": {"enabled": False, "session_token_enc": ""},
        "codex": {"enabled": False},
        "zhipu": {"enabled": False, "api_key_enc": ""},
        "zhipu_member": {"enabled": False},
        "kimi": {"enabled": False, "api_key_enc": ""},
        "volc": {"enabled": False, "ak_enc": "", "sk_enc": ""},
    },
    "manual": {},   # {名称: {total, used, unit, note}}
    "cache": {},    # {平台: QuotaResult 可序列化字典}
}


class Config:
    """读取 / 保存本地配置；带内存缓存，避免频繁落盘。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(os.environ.get(
            "APPDATA", str(Path.home()))) / "QuotaBoard" / "config.json"
        self._data: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
        self._merge_defaults()
        self.load()

    def _merge_defaults(self) -> None:
        for k, v in DEFAULT_CONFIG.items():
            if k not in self._data:
                self._data[k] = json.loads(json.dumps(v))

    def load(self) -> None:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
                    self._merge_defaults()
        except Exception as e:
            print(f"[config] 读取配置失败，使用默认配置：{e}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ---- 通用 ----
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def refresh_interval_minutes(self) -> int:
        return int(self._data.get("refresh_interval_minutes", 30))

    @refresh_interval_minutes.setter
    def refresh_interval_minutes(self, minutes: int) -> None:
        self._data["refresh_interval_minutes"] = max(1, int(minutes))

    @property
    def startup_with_windows(self) -> bool:
        return bool(self._data.get("startup_with_windows", False))

    @startup_with_windows.setter
    def startup_with_windows(self, value: bool) -> None:
        self._data["startup_with_windows"] = bool(value)

    # ---- 平台凭据 ----
    def platform_cfg(self, key: str) -> dict[str, Any]:
        return self._data["platforms"].setdefault(key, {})

    def get_credential(self, key: str, field: str) -> str:
        return decrypt_secret(str(self.platform_cfg(key).get(f"{field}_enc", "")))

    def set_credential(self, key: str, field: str, value: str) -> None:
        self.platform_cfg(key)[f"{field}_enc"] = encrypt_secret(value)

    def set_enabled(self, key: str, enabled: bool) -> None:
        self.platform_cfg(key)["enabled"] = bool(enabled)

    def is_enabled(self, key: str) -> bool:
        return bool(self.platform_cfg(key).get("enabled", False))

    # ---- 手动额度 ----
    @property
    def manual_entries(self) -> dict[str, dict[str, Any]]:
        return self._data.setdefault("manual", {})

    # ---- 缓存 ----
    def get_cache(self, key: str) -> Optional[dict[str, Any]]:
        return self._data.setdefault("cache", {}).get(key)

    def set_cache(self, key: str, value: dict[str, Any]) -> None:
        self._data.setdefault("cache", {})[key] = value

    def drop_platform(self, key: str) -> None:
        self._data["platforms"].pop(key, None)
        self._data.setdefault("cache", {}).pop(key, None)
