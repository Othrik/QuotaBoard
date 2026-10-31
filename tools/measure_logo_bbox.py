# -*- coding: utf-8 -*-
"""测量 assets/logo/*.png 的非透明有效像素包围盒，用于图标大小对齐。"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "assets" / "logo"
out = {}
for p in sorted(ROOT.glob("*.png")):
    im = Image.open(p).convert("RGBA")
    a = im.split()[3]
    bbox = a.getbbox()
    W = im.width
    if bbox:
        out[p.name] = {
            "size": [im.width, im.height],
            "bbox": list(bbox),
            "eff_w": round((bbox[2] - bbox[0]) / W, 3),
            "eff_h": round((bbox[3] - bbox[1]) / W, 3),
        }
    else:
        out[p.name] = {"bbox": None}
print(json.dumps(out, ensure_ascii=False, indent=1))
