"""Logo 统一处理：等比缩放至 128x128 画布内（居中，不变形）+ 圆角遮罩（radius=24）。

128px 高分辨率源 + 圆角，适配 2x 高分屏下 18px 行首图标，避免模糊。
输入 assets/logo/*.png（原始下载/转换后的 PNG），输出覆盖同名文件（圆角版）。
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent / "assets" / "logo"
SIZE = 128
RADIUS = 24


def fit_paste(base: Image.Image, src: Image.Image) -> None:
    """将 src 等比缩放居中贴到 base 上，不拉伸变形。"""
    w, h = src.size
    scale = min(SIZE / w, SIZE / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    src2 = src.resize((nw, nh), Image.LANCZOS)
    x = (SIZE - nw) // 2
    y = (SIZE - nh) // 2
    base.paste(src2, (x, y), src2 if src2.mode == "RGBA" else None)


for p in sorted(ROOT.glob("*.png")):
    im = Image.open(p).convert("RGBA")
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fit_paste(canvas, im)
    mask = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=RADIUS, fill=255)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)
    out.save(p, "PNG")
    print(f"{p.name}: {p.stat().st_size}B")
print("done")
