"""冒烟测试：验证配置加密往返、Provider 错误路径、火山签名结构。

运行：
    python tests_smoke.py

说明：会向各平台接口发起一次真实请求（使用无效凭据），用于确认
错误路径返回失败结果而不是崩溃；不泄露任何有效凭据。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quotaboard.config import Config, decrypt_secret, encrypt_secret  # noqa: E402


def test_dpapi_roundtrip() -> None:
    secret = "sk-test-中文密钥-12345"
    enc = encrypt_secret(secret)
    assert enc and enc != secret, "加密结果不应等于明文"
    assert decrypt_secret(enc) == secret, "解密应还原明文"
    print("[OK] DPAPI 加密/解密往返一致")


def test_config_read_write() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = Config(Path(d) / "cfg.json")
        cfg.set_credential("openai", "api_key", "sk-abc")
        cfg.refresh_interval_minutes = 45
        cfg.save()
        cfg2 = Config(Path(d) / "cfg.json")
        assert cfg2.get_credential("openai", "api_key") == "sk-abc"
        assert cfg2.refresh_interval_minutes == 45
    print("[OK] 配置读写与凭据加密持久化")


def test_provider_error_paths() -> None:
    from quotaboard.providers import PROVIDERS

    cases = {
        "openai": {"api_key": "sk-invalid-quotaboard-test"},
        "zhipu": {"api_key": "invalid-quotaboard-test"},
        "kimi": {"api_key": "sk-invalid-quotaboard-test"},
        "chatgpt_plus": {"session_token": "invalid-token-test-0000"},
    }
    for key, cfg in cases.items():
        result = PROVIDERS[key](cfg).fetch()
        assert result.ok is False, f"{key} 应返回失败结果"
        assert result.error, f"{key} 应包含错误信息"
        print(f"[OK] {key} 错误路径返回失败结果（{result.error[:60]}…）")


def test_volc_signature_structure() -> None:
    from quotaboard.providers.volc_provider import _build_signature

    headers = _build_signature(
        "AKTEST123", "SKTEST456",
        {"Action": "GetUsageDetails", "Version": "2024-01-01"}, {})
    auth = headers["Authorization"]
    assert auth.startswith("HMAC-SHA256 Credential=AKTEST123/"), "Authorization 头结构错误"
    assert "SignedHeaders=content-type;host;x-content-sha256;x-date" in auth
    assert "Signature=" in auth
    assert headers["X-Content-Sha256"] and len(headers["X-Content-Sha256"]) == 64
    print("[OK] 火山签名头结构完整")

    # 完整链路：假凭据应返回"接口报错/请求失败"而非崩溃
    from quotaboard.providers import PROVIDERS
    result = PROVIDERS["volc"]({"ak": "AKTEST123", "sk": "SKTEST456",
                                "action": "GetUsageDetails"}).fetch()
    assert result.ok is False
    print(f"[OK] 火山方舟假凭据错误路径正常（{result.error[:70]}…）")


def test_codex_provider() -> None:
    from quotaboard.providers import PROVIDERS

    # 1) 未安装 codex（命令不存在）→ 返回明确错误
    provider = PROVIDERS["codex"]({"cmd": ["nonexistent-quotaboard-cmd-xyz"]})
    result = provider.fetch()
    assert result.ok is False and "未找到 codex" in result.error, result.error
    print("[OK] codex 未安装错误路径")

    # 2) 用模拟 app-server 验证完整协议链路与解析
    import sys
    from pathlib import Path
    fake = str(Path(__file__).resolve().parent / "tools" / "fake_codex_server.py")
    python = sys.executable
    provider = PROVIDERS["codex"]({"cmd": [python, fake]})
    result = provider.fetch()
    assert result.ok, f"模拟链路应成功：{result.error}"
    assert "5h 62%" in result.display, result.display
    assert "周 38%" in result.display, result.display
    assert result.percent == 38, result.percent
    assert "重置" in result.sub_note, result.sub_note
    # 双窗口环形图数据
    assert result.metrics and len(result.metrics) == 2, result.metrics
    assert result.metrics[0]["label"] == "5h" and result.metrics[0]["percent"] == 62
    assert result.metrics[1]["label"] == "周" and result.metrics[1]["percent"] == 38
    print(f"[OK] codex 模拟链路解析正确（{result.display}，percent={result.percent}，"
          f"metrics={[m['label'] for m in result.metrics]}）")


def test_zhipu_member_provider() -> None:
    import os
    from unittest import mock

    from quotaboard.providers import PROVIDERS
    from quotaboard.providers.zhipu_member_provider import (
        extract_member, read_client_token,
    )

    # 1) 无客户端登录态（APPDATA 指向空目录）→ 明确错误
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(
            os.environ, {"APPDATA": d}):
        ok, msg, tok = read_client_token()
        assert not ok and "未找到" in msg, msg
        result = PROVIDERS["zhipu_member"]({}).fetch()
        assert result.ok is False and "未找到" in result.error, result.error
    print("[OK] 智谱清言无客户端登录态错误路径")

    # 2) 响应解析（模拟成功响应，不发起真实请求）
    payload = {
        "status": 20000,
        "result": {"member_info": {
            "level": "vip", "member_status": 2,
            "token_left_percent": 62.5, "left_score": 1234,
            "member_expiration_time": 1750000000,
        }},
    }
    member = extract_member(payload)
    assert member is not None and member["level"] == "vip"
    with mock.patch(
            "quotaboard.providers.zhipu_member_provider.read_client_token",
            return_value=(True, "", "fake_token")), mock.patch(
            "quotaboard.providers.zhipu_member_provider.http_get_json",
            return_value=payload):
        result = PROVIDERS["zhipu_member"]({}).fetch()
    assert result.ok, result.error
    assert result.percent == 62.5
    assert "62" in result.display
    assert "VIP" in result.sub_note and "有效" in result.sub_note
    assert "到期" in result.sub_note and "1,234" in result.sub_note
    print(f"[OK] 智谱清言会员解析正确（{result.display}，"
          f"{result.sub_note}，percent={result.percent}）")

    # 3) token 过期（HTTP 401）→ 明确提示
    import urllib.error
    exc = urllib.error.HTTPError(
        "https://chatglm.cn/chatglm/member-api/member/member_info",
        401, "Unauthorized", {}, None)
    with mock.patch(
            "quotaboard.providers.zhipu_member_provider.read_client_token",
            return_value=(True, "", "fake_token")), mock.patch(
            "quotaboard.providers.zhipu_member_provider.http_get_json",
            side_effect=exc):
        result = PROVIDERS["zhipu_member"]({}).fetch()
    assert result.ok is False and "过期" in result.error, result.error
    print("[OK] 智谱清言登录态过期错误路径")

    # 4) 客户端运行中（Cookie 锁定）但缓存可用 → 用缓存 token 正常查询
    import quotaboard.providers.zhipu_member_provider as zmp
    with mock.patch.object(zmp, "_read_sqlite_token", return_value=None), \
            mock.patch.object(zmp, "_read_cache", return_value="cached_token"), \
            mock.patch.object(zmp, "http_get_json", return_value=payload):
        result = PROVIDERS["zhipu_member"]({}).fetch()
    assert result.ok, result.error
    assert result.percent == 62.5
    print("[OK] 智谱清言客户端运行中（锁定）使用缓存 token 成功")

    # 5) 手动粘贴 token 优先于自动读取
    with mock.patch.object(zmp, "http_get_json", return_value=payload):
        result = PROVIDERS["zhipu_member"]({"manual_token": "manual-abc"}).fetch()
    assert result.ok, result.error
    assert result.percent == 62.5
    print("[OK] 智谱清言手动粘贴 token 路径")


def test_doubao_provider() -> None:
    from unittest import mock

    import quotaboard.providers.doubao_provider as dmp
    from quotaboard.providers import PROVIDERS

    payload = {
        "code": 0, "msg": "",
        "data": {
            "current_subscription": {
                "display": {"product_name": "个人订阅", "short_name": "标准套餐"},
                "end_time": 1794491066517,
            },
            "window_limit_section": {
                "window_limit_groups": [{
                    "feature_group": "general",
                    "window_limits": [
                        {"window_type": 1, "used_percent": 53,
                         "total_amount": "1,470", "used_amount": "792"},
                        {"window_type": 2, "used_percent": 84,
                         "total_amount": "4,200", "used_amount": "3,537"},
                    ],
                }],
            },
            "incentive_quota_section": {
                "window_limit_groups": [{
                    "feature_group": "doubao_activity_reward_quota",
                    "window_limits": [
                        {"window_type": 3, "used_percent": 93,
                         "total_amount": "2,700", "used_amount": "2,512"},
                    ],
                }],
            },
            "member_info": {"hasActiveSubscription": True},
        },
    }

    # 1) 无登录态 → 明确错误
    with mock.patch.object(dmp, "_scan_session",
                           return_value=(False, "未检测到豆包客户端登录态", {})):
        result = PROVIDERS["doubao"]({}).fetch()
    assert result.ok is False and "未检测到" in result.error, result.error
    print("[OK] 豆包无客户端登录态错误路径")

    # 2) 成功解析（mock 凭据 + 响应，不发起真实请求）
    cred = {"sessionid": "27f4" + "0" * 28, "multi_sids": "1%3A2"}
    with mock.patch.object(dmp, "_scan_session", return_value=(True, "", cred)), \
            mock.patch.object(dmp, "http_post_json", return_value=payload):
        result = PROVIDERS["doubao"]({}).fetch()
    assert result.ok, result.error
    assert result.display == "5h 47% · 周 16%", result.display
    assert result.percent == 16.0, result.percent
    assert result.metrics and len(result.metrics) == 2, result.metrics
    assert result.metrics[0]["label"] == "5h" and result.metrics[0]["percent"] == 47
    assert result.metrics[1]["label"] == "周" and result.metrics[1]["percent"] == 16
    assert "个人订阅" in result.sub_note and "到期" in result.sub_note
    assert "活动赠送" in result.sub_note and "6%" not in result.sub_note
    assert "7%" in result.sub_note  # 活动赠送剩余 100-93=7
    print(f"[OK] 豆包订阅解析正确（{result.display}，percent={result.percent}，"
          f"metrics={[m['label'] for m in result.metrics]}，note={result.sub_note}）")

    # 3) 登录态失效（HTTP 401）→ 明确提示
    import urllib.error
    exc = urllib.error.HTTPError(
        "https://www.doubao.com/alice/commerce/sale/subscription/quota/summary/",
        401, "Unauthorized", {}, None)
    with mock.patch.object(dmp, "_scan_session", return_value=(True, "", cred)), \
            mock.patch.object(dmp, "http_post_json", side_effect=exc):
        result = PROVIDERS["doubao"]({}).fetch()
    assert result.ok is False and "登录态已失效" in result.error, result.error
    print("[OK] 豆包登录态失效错误路径")


if __name__ == "__main__":
    test_dpapi_roundtrip()
    test_config_read_write()
    test_provider_error_paths()
    test_volc_signature_structure()
    test_codex_provider()
    test_zhipu_member_provider()
    test_doubao_provider()
    print("\n全部冒烟测试通过。")
