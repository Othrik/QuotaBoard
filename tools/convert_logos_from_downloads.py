"""一次性脚本：用用户提供的官方 Logo（PNG/WebP/SVG）替换 assets/logo 对应文件。

- zhipu.png      → assets/logo/zhipu.png
- doubao.webp    → assets/logo/doubao.png
- openai.svg     → assets/logo/openai.png
- deepseek-color.svg → assets/logo/deepseek.png

SVG 用 QtSvg 渲染为透明背景 PNG（保持原始宽高比，长边 1024px）。
"""
from pathlib import Path

from PIL import Image

DOWNLOADS = Path.home() / "Downloads"
LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "logo"


def svg_to_png(svg_path: Path, out: Path, long_edge: int = 1024) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(svg_path))
    size = renderer.defaultSize()
    if size.isEmpty():
        raise RuntimeError(f"SVG 无效：{svg_path}")
    w, h = size.width(), size.height()
    scale = long_edge / max(w, h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    img = QImage(nw, nh, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    renderer.render(p, QRectF(0, 0, nw, nh))
    p.end()
    assert img.save(str(out), "PNG"), f"保存失败：{out}"


def main() -> None:
    # 1) 智谱（PNG）
    src = DOWNLOADS / "zhipu.png"
    if src.is_file():
        im = Image.open(src).convert("RGBA")
        im.save(LOGO_DIR / "zhipu.png", "PNG")
        print(f"zhipu: {im.size} -> {LOGO_DIR / 'zhipu.png'}")

    # 2) 豆包（WebP）
    src = DOWNLOADS / "doubao.webp"
    if src.is_file():
        im = Image.open(src).convert("RGBA")
        im.save(LOGO_DIR / "doubao.png", "PNG")
        print(f"doubao: {im.size} -> {LOGO_DIR / 'doubao.png'}")

    # 3) OpenAI（SVG）
    src = DOWNLOADS / "openai.svg"
    if src.is_file():
        svg_to_png(src, LOGO_DIR / "openai.png")
        print(f"openai: SVG -> {LOGO_DIR / 'openai.png'}")

    # 4) DeepSeek（SVG）
    src = DOWNLOADS / "deepseek-color.svg"
    if src.is_file():
        svg_to_png(src, LOGO_DIR / "deepseek.png")
        print(f"deepseek: SVG -> {LOGO_DIR / 'deepseek.png'}")

    print("done")


if __name__ == "__main__":
    main()
