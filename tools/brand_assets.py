# -*- coding: utf-8 -*-
"""Generate all Atlantis Watcher brand assets from one raster master.

The source image is intentionally kept in ``assets/brand`` so the build is
repeatable and all surfaces use the same supplied artwork. Full-bleed assets
keep the original opaque navy background. Android adaptive assets additionally
extract the bright gateway mark onto transparency and keep it inside the safe
zone required by launcher masks.
"""
from __future__ import annotations

import base64
import io
import math
import struct
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "assets" / "brand"
SOURCE_PATH = BRAND_DIR / "atlantis-watcher-source.png"
PUBLIC_DIR = ROOT / "frontend" / "public"
FRONTEND_ASSETS_DIR = ROOT / "frontend" / "src" / "assets"
RES_DIR = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"

# Shared theme values used by configure_android.py and the frontend.
DEEP = "#020A2B"
HULL = "#0A1740"
ACCENT = "#18D8F2"
ACCENT_DIM = "#128BE5"
AMBER = "#FFC347"
TEXT = "#E8F7FF"
CORAL = "#FF6B6B"

WINDOWS_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
FAVICON_ICO_SIZES = (16, 32, 48, 64)
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}
LAUNCHER_DP = 48
FOREGROUND_DP = 108
SAFE_RATIO = 0.66
MASTER_SIZE = 1024


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _ensure_dirs() -> None:
    for path in (BRAND_DIR, PUBLIC_DIR, FRONTEND_ASSETS_DIR, RES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _load_source() -> Image.Image:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Missing brand source image: {SOURCE_PATH}. "
            "Copy the supplied square PNG to this path before generating assets."
        )
    with Image.open(SOURCE_PATH) as source:
        if source.width != source.height:
            raise ValueError(f"Brand source must be square, got {source.size}")
        return source.convert("RGBA")


def _resample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, Image.Resampling.LANCZOS)


@lru_cache(maxsize=1)
def _master() -> Image.Image:
    return _resample(_load_source(), (MASTER_SIZE, MASTER_SIZE))


def _sharpen(image: Image.Image, size: int) -> Image.Image:
    if size <= 32:
        image = ImageEnhance.Contrast(image).enhance(1.04)
        image = image.filter(ImageFilter.UnsharpMask(radius=0.55, percent=115, threshold=2))
    elif size <= 64:
        image = image.filter(ImageFilter.UnsharpMask(radius=0.45, percent=90, threshold=2))
    return image


def render_icon(size: int, plate: str = "square") -> Image.Image:
    """Render an opaque icon from the supplied master image."""
    rendered = _sharpen(_resample(_master(), (size, size)), size)
    if plate == "circle":
        from PIL import ImageDraw

        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        rendered.putalpha(mask)
    elif plate != "square":
        rendered.putalpha(255)
    return rendered


def _background_estimate(source: Image.Image) -> tuple[int, int, int]:
    points = ((0, 0), (0, source.height - 1), (source.width - 1, 0),
              (source.width - 1, source.height - 1))
    pixels = [source.getpixel(point)[:3] for point in points]
    return tuple(round(sum(pixel[channel] for pixel in pixels) / len(pixels)) for channel in range(3))


def _gateway_alpha(source: Image.Image) -> Image.Image:
    """Extract the luminous gateway from the dark background."""
    background = _background_estimate(source)
    rgba = source.convert("RGBA")
    alpha = Image.new("L", rgba.size, 0)
    src = rgba.load()
    dst = alpha.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _ = src[x, y]
            distance = math.sqrt(sum((value - background[channel]) ** 2 for channel, value in enumerate((r, g, b))))
            brightness = max(r, g, b)
            chroma = max(r, g, b) - min(r, g, b)
            if brightness < 52 or distance < 16:
                value = 0.0
            else:
                value = max(0.0, min(255.0, (distance - 16.0) * 4.2 + (brightness - 52.0) * 1.8 + chroma * 0.65))
            dst[x, y] = round(value)
    return alpha.filter(ImageFilter.GaussianBlur(0.35))


@lru_cache(maxsize=1)
def _gateway_mask() -> Image.Image:
    return _gateway_alpha(_master())


def render_foreground(size: int) -> Image.Image:
    """Render a transparent safe-area foreground for adaptive icons."""
    source = _master()
    alpha = _gateway_mask()
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("Unable to extract the gateway mark from the source image")
    mark = source.crop(bbox)
    mark_alpha = alpha.crop(bbox)
    safe = max(1, round(size * SAFE_RATIO))
    scale = min(safe / mark.width, safe / mark.height)
    target = (max(1, round(mark.width * scale)), max(1, round(mark.height * scale)))
    mark = _resample(mark, target)
    mark_alpha = _resample(mark_alpha, target)
    mark.putalpha(mark_alpha)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(mark, ((size - target[0]) // 2, (size - target[1]) // 2))
    return _sharpen(canvas, size)


def render_monochrome(size: int) -> Image.Image:
    alpha = render_foreground(size).getchannel("A")
    image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    image.putalpha(alpha)
    return image


def render_splash(width: int, height: int) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), rgb(DEEP) + (255,))
    master = _master()
    mark_size = max(64, min(width, height) // 3)
    mark = _resample(master, (mark_size, mark_size))
    canvas.alpha_composite(mark, ((width - mark_size) // 2, (height - mark_size) // 2))
    return canvas.convert("RGB")


def write_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, format="PNG", optimize=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_ico(path: Path, sizes: tuple[int, ...]) -> None:
    payloads = []
    for size in sizes:
        buffer = io.BytesIO()
        render_icon(size, plate="square").save(buffer, format="PNG", optimize=True)
        payloads.append((size, buffer.getvalue()))
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<HHH", 0, 1, len(payloads))
    directory = bytearray()
    offset = 6 + 16 * len(payloads)
    for size, payload in payloads:
        dimension = 0 if size == 256 else size
        directory.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32,
                                     len(payload), offset))
        offset += len(payload)
    path.write_bytes(header + directory + b"".join(payload for _, payload in payloads))


def _svg_image(image: Image.Image, title: str = "Atlantis Watcher") -> str:
    # SVG is used as a scalable wrapper for browser compatibility. The 1024px
    # PNG master remains available separately; a 256px embedded preview keeps
    # the frontend bundle small without affecting launcher or desktop assets.
    buffer = io.BytesIO()
    _resample(image, (256, 256)).save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" '
        'width="1024" height="1024" role="img" aria-label="Atlantis Watcher">\n'
        f"  <title>{title}</title>\n"
        f'  <image href="data:image/png;base64,{encoded}" width="1024" height="1024" preserveAspectRatio="none"/>\n'
        "</svg>\n"
    )


def android_colors_xml() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        f'    <color name="colorPrimary">{ACCENT}</color>\n'
        f'    <color name="colorPrimaryDark">{DEEP}</color>\n'
        f'    <color name="colorAccent">{ACCENT}</color>\n'
        f'    <color name="aw_background">{DEEP}</color>\n'
        f'    <color name="aw_surface">{HULL}</color>\n'
        f'    <color name="aw_amber">{AMBER}</color>\n'
        f'    <color name="aw_text">{TEXT}</color>\n'
        f'    <color name="aw_error">{CORAL}</color>\n'
        '</resources>\n'
    )


def build_windows_icon() -> int:
    write_ico(ROOT / "icon.ico", WINDOWS_ICO_SIZES)
    return 1


def build_frontend_assets() -> int:
    master = _master()
    write_png(BRAND_DIR / "atlantis-watcher-master.png", master)
    write_text(BRAND_DIR / "atlantis-watcher.svg", _svg_image(master))
    write_text(BRAND_DIR / "atlantis-watcher-mark.svg", _svg_image(master, "Atlantis Watcher mark"))
    write_text(PUBLIC_DIR / "favicon.svg", _svg_image(master))
    write_ico(PUBLIC_DIR / "favicon.ico", FAVICON_ICO_SIZES)
    for name, size in (("favicon-16.png", 16), ("favicon-32.png", 32),
                       ("apple-touch-icon.png", 180), ("icon-192.png", 192),
                       ("icon-512.png", 512)):
        write_png(PUBLIC_DIR / name, render_icon(size, plate="square"))
    write_text(FRONTEND_ASSETS_DIR / "brandMark.svg", _svg_image(_resample(master, (256, 256))))
    return 10


def _bitmap_drawable(reference: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    android:src="{reference}"\n'
        '    android:gravity="fill" />\n'
    )


def build_android_assets() -> int:
    total = 0
    for density, scale in DENSITIES.items():
        mipmap = RES_DIR / f"mipmap-{density}"
        launcher = round(LAUNCHER_DP * scale)
        foreground = round(FOREGROUND_DP * scale)
        write_png(mipmap / "ic_launcher.png", render_icon(launcher, plate="square"))
        write_png(mipmap / "ic_launcher_round.png", render_icon(launcher, plate="circle"))
        write_png(mipmap / "ic_launcher_foreground.png", render_foreground(foreground))
        write_png(mipmap / "ic_launcher_monochrome.png", render_monochrome(foreground))
        total += 4

    anydpi = RES_DIR / "mipmap-anydpi-v26"
    adaptive = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
        '</adaptive-icon>\n'
    )
    for name in ("ic_launcher", "ic_launcher_round"):
        write_text(anydpi / f"{name}.xml", adaptive)
        total += 1

    write_text(RES_DIR / "drawable" / "ic_launcher_background.xml",
               '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n'
               '    <solid android:color="@color/ic_launcher_background" />\n'
               '</shape>\n')
    write_text(RES_DIR / "drawable-v24" / "ic_launcher_foreground.xml",
               _bitmap_drawable("@mipmap/ic_launcher_foreground"))
    write_text(RES_DIR / "values" / "ic_launcher_background.xml",
               '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
               f'    <color name="ic_launcher_background">{DEEP}</color>\n'
               '</resources>\n')
    write_text(RES_DIR / "values" / "colors.xml", android_colors_xml())
    total += 4

    for splash in sorted(RES_DIR.glob("drawable*/splash.png")):
        with Image.open(splash) as old:
            width, height = old.size
        write_png(splash, render_splash(width, height))
        total += 1
    return total


def build_preview() -> Path:
    from PIL import ImageDraw

    width, height = 1200, 520
    sheet = Image.new("RGB", (width, height), (241, 245, 249))
    draw = ImageDraw.Draw(sheet)
    draw.text((28, 18), "ATLANTIS WATCHER / ABYSS GATEWAY", fill=(4, 15, 45))
    draw.text((28, 38), "supplied master image / one source across every surface", fill=(80, 98, 122))
    draw.line((28, 64, width - 28, 64), fill=(211, 220, 231), width=1)
    sizes = (16, 24, 32, 48, 64, 96, 128)
    x = 36
    for size in sizes:
        icon = render_icon(size)
        sheet.paste(icon.convert("RGB"), (x, 92 + (128 - size) // 2))
        draw.text((x, 232), f"{size}px", fill=(40, 55, 75))
        x += 110
    hero = render_icon(160)
    sheet.paste(hero.convert("RGB"), (860, 86))
    draw.text((860, 254), "MASTER / WINDOWS + WEB", fill=(40, 55, 75))
    draw.line((28, 288, width - 28, 288), fill=(211, 220, 231), width=1)
    for x, title, mode in ((28, "ANDROID ADAPTIVE", "foreground"),
                           (428, "ANDROID MONOCHROME", "mono"),
                           (828, "ANDROID LEGACY", "square")):
        tile = Image.new("RGB", (344, 194), (4, 15, 45))
        if mode == "foreground":
            mark = render_foreground(128)
            tile.paste(mark, (108, 22), mark)
        elif mode == "mono":
            mark = render_monochrome(128)
            tile.paste(mark, (108, 22), mark)
        else:
            mark = render_icon(128)
            tile.paste(mark.convert("RGB"), (108, 22))
        ImageDraw.Draw(tile).text((16, 166), title, fill=(140, 220, 235))
        sheet.paste(tile, (x, 318))
    out = BRAND_DIR / "preview.png"
    write_png(out, sheet)
    return out


def main(argv: list[str]) -> int:
    _ensure_dirs()
    only = argv[1] if len(argv) > 1 else "--all"
    counts: dict[str, int] = {}
    if only in ("--all", "--windows"):
        counts["windows"] = build_windows_icon()
    if only in ("--all", "--frontend"):
        counts["frontend"] = build_frontend_assets()
    if only in ("--all", "--android"):
        counts["android"] = build_android_assets()
    if only == "--all":
        print("preview:", build_preview())
    for key, value in counts.items():
        print(f"{key}: {value} files")
    print("BRAND_ASSETS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
