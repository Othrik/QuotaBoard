"""一次性脚本：平台 Logo 统一为 64x64 圆角图标格（radius=12）。

输入 assets/logo/*.png（原始下载），输出覆盖同名文件（圆角版本）。
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent / "assets" / "logo"

for p in sorted(ROOT.glob("*.png")):
    im = Image.open(p).convert("RGBA")
    # 等比缩放至 64x64（居中，留 0 边距——图标本身自带底色）
    im = im.resize((64, 64), Image.LANCZOS)
    mask = Image.new("L", (64, 64), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, 63, 63), radius=12, fill=255)
    out = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    out.save(p, "PNG")
    print(f"{p.name}: {p.stat().st_size}B")
print("done")
