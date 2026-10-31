"""模拟 codex app-server（测试用途）：按 stdio JSON-RPC 行协议应答。

用于在没有真实 codex CLI 时验证 CodexProvider 的完整协议链路。
运行：python tools/fake_codex_server.py
"""
from __future__ import annotations

import json
import sys
import time


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    now = int(time.time())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method = msg.get("method")
        if method == "initialize":
            _emit({"id": 1, "result": {"capabilities": {}}})
        elif method == "account/rateLimits/read":
            _emit({"id": 2, "result": {"rateLimits": {
                "primary": {"usedPercent": 38, "resetsAt": now + 5 * 3600,
                            "windowDurationMins": 300},
                "secondary": {"usedPercent": 62, "resetsAt": now + 7 * 86400,
                              "windowDurationMins": 10080},
            }}})
        # initialized 等通知不回复
    return 0


if __name__ == "__main__":
    sys.exit(main())
