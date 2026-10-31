# -*- coding: utf-8 -*-
"""测量各 logo 不透明像素面积占比，用于按 ChatGPT(openai) 基准对齐视觉大小。"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "assets" / "logo"
out = {}
for p in sorted(ROOT.glob("*.png")):
    im = Image.open(p).convert("RGBA")
    a = im.split()[3]
    total = im.width * im.height
    opaque = sum(1 for v in a.getdata() if v > 16)  # alpha>16 视为有效像素
    out[p.name] = {
        "ratio": round(opaque / total, 3),
    }
# 基准：openai（ChatGPT 所用图标）
base = out["openai.png"]["ratio"]
for k in out:
    r = out[k]["ratio"]
    out[k]["scale"] = round((base / r) ** 0.5, 3) if r else 1.0
out["_base_openai_ratio"] = base
print(json.dumps(out, ensure_ascii=False, indent=1))
