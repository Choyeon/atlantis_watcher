# -*- coding: utf-8 -*-
"""Atlantis Watcher 品牌图标单一真源（Single Source of Truth）。

设计：声呐眼 / 深渊信标
  - 圆角方形「仪表舱」深底 #0B1220，细边框分区（不用阴影/渐变）
  - C 形声呐扫描环：持续观测，缺口朝右上，留出「信号进入」的动势
  - 中心镜头圆 + 深底瞳孔：Watcher 之眼
  - 右上琥珀点：实时捕获的信号，呼应品牌警示色
  - 顶部状态光带 + 底部三道水波刻度：仪表读数 + 亚特兰蒂斯深海

本模块只依赖 Pillow（项目已有），不引入新依赖。所有几何用 0-100 归一化坐标：
  * 位图：Pillow 超采样绘制
  * 矢量：同一组几何生成 SVG path（三段贝塞尔近似圆弧，Android VectorDrawable 也支持）
因此桌面 ICO / favicon / APK 自适应图标 / 网页内联 SVG 不会各自漂移。

用法：
    python tools/brand_assets.py              # 生成全部资产
    python tools/brand_assets.py --windows    # 仅生成 icon.ico
    python tools/brand_assets.py --frontend   # 仅生成前端资源
    python tools/brand_assets.py --android    # 仅生成 Android 资源
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "assets" / "brand"
PUBLIC_DIR = ROOT / "frontend" / "public"
RES_DIR = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"

# ---------------------------------------------------------------------------
# 品牌色（与 frontend/src/styles 的设计令牌一致）
# ---------------------------------------------------------------------------
DEEP = "#0B1220"          # 深海底
HULL = "#142034"          # 面板
ACCENT = "#35D6BD"        # 海沫青松石
ACCENT_DIM = "#1E9C8A"    # 次级青
AMBER = "#F5B642"         # 琥珀信号
TEXT = "#E8EEF7"          # 读数白
CORAL = "#FF6B6B"         # 危险（保留，图标不使用）

# 描边不画半透明（Pillow 直接写像素不做混合），改用预混暗青
EDGE = "#173C43"
WAVE_1 = "#2E8F82"
WAVE_2 = "#246F68"
WAVE_3 = "#1B504E"
HALO = "#6B5327"

# ---------------------------------------------------------------------------
# 归一化几何（100 x 100 画布）
# ---------------------------------------------------------------------------
PLATE_R = 22.0
EDGE_INSET = 1.4
EDGE_W = 1.1
RING_CX, RING_CY, RING_R = 49.0, 51.0, 27.0
RING_W = 7.0
RING_W_MIN = 9.0          # 极小尺寸加粗
RING_START, RING_END = 20.0, 300.0   # PIL 角度：0=右，顺时针
LENS_R, LENS_HOLE = 8.5, 3.4
BEACON_X, BEACON_Y, BEACON_R = 78.0, 30.0, 4.6
BEACON_HALO_R, BEACON_HALO_W = 7.8, 1.2
BAR = (24.0, 13.0, 76.0, 18.0)       # x0,y0,x1,y1
BAR_R = 2.5
WAVES = (                # x, y, w, h, color
    (44.0, 81.0, 12.0, 2.4, WAVE_1),
    (41.0, 86.0, 18.0, 2.4, WAVE_2),
    (37.0, 91.0, 26.0, 2.4, WAVE_3),
)

WINDOWS_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
FAVICON_ICO_SIZES = (16, 32, 48, 64)
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}
LAUNCHER_DP = 48
FOREGROUND_DP = 108
SAFE_RATIO = 0.66          # 自适应图标前景限制在中心 66% 安全区

def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def detail_for(size: int) -> int:
    """按尺寸分层：0=极简(<=24) 1=紧凑(<=48) 2=完整(>=64)"""
    if size <= 24:
        return 0
    if size <= 48:
        return 1
    return 2


# ---------------------------------------------------------------------------
# 矢量路径生成（SVG / Android VectorDrawable 共用；不用 arc 命令，Android 不支持）
# ---------------------------------------------------------------------------
def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _pt(x: float, y: float) -> str:
    return f"{_fmt(x)} {_fmt(y)}"


def round_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    k = r * 0.5522847498  # 90° 圆角的三次贝塞尔控制点系数
    return (
        f"M {_pt(x0 + r, y0)} L {_pt(x1 - r, y0)} "
        f"C {_pt(x1 - r + k, y0)} {_pt(x1, y0 + r - k)} {_pt(x1, y0 + r)} "
        f"L {_pt(x1, y1 - r)} "
        f"C {_pt(x1, y1 - r + k)} {_pt(x1 - r + k, y1)} {_pt(x1 - r, y1)} "
        f"L {_pt(x0 + r, y1)} "
        f"C {_pt(x0 + r - k, y1)} {_pt(x0, y1 - r + k)} {_pt(x0, y1 - r)} "
        f"L {_pt(x0, y0 + r)} "
        f"C {_pt(x0, y0 + r - k)} {_pt(x0 + r - k, y0)} {_pt(x0 + r, y0)} Z"
    )


def circle_path(cx: float, cy: float, r: float) -> str:
    k = r * 0.5522847498
    return (
        f"M {_pt(cx + r, cy)} "
        f"C {_pt(cx + r, cy + k)} {_pt(cx + k, cy - r)} {_pt(cx, cy - r)} "
        f"C {_pt(cx - k, cy - r)} {_pt(cx - r, cy - k)} {_pt(cx - r, cy)} "
        f"C {_pt(cx - r, cy + k)} {_pt(cx - k, cy + r)} {_pt(cx, cy + r)} "
        f"C {_pt(cx + k, cy + r)} {_pt(cx + r, cy + k)} {_pt(cx + r, cy)} Z"
    )


def arc_path(cx: float, cy: float, r: float, start: float, end: float) -> str:
    """把圆弧拆成 <=90° 的三次贝塞尔段，SVG 与 Android vector 都能渲染。"""
    total = end - start
    segments = max(1, math.ceil(total / 90.0))
    delta = total / segments
    k = 4 / 3 * math.tan(math.radians(delta) / 4) * r

    def pos(deg: float) -> tuple[float, float]:
        a = math.radians(deg)
        return cx + r * math.cos(a), cy + r * math.sin(a)

    x0, y0 = pos(start)
    parts = [f"M {_pt(x0, y0)}"]
    for i in range(segments):
        a0 = start + i * delta
        a1 = a0 + delta
        p0 = pos(a0)
        p1 = pos(a1)
        t0 = (-math.sin(math.radians(a0)), math.cos(math.radians(a0)))
        t1 = (-math.sin(math.radians(a1)), math.cos(math.radians(a1)))
        c1 = (p0[0] + k * t0[0], p0[1] + k * t0[1])
        c2 = (p1[0] - k * t1[0], p1[1] - k * t1[1])
        parts.append(f"C {_pt(c1[0], c1[1])} {_pt(c2[0], c2[1])} {_pt(p1[0], p1[1])}")
    return " ".join(parts)


def build_shapes(detail: int, plate: bool, transparent_hole: bool = False) -> list[dict]:
    """返回与位图同构的矢量图元列表。"""
    shapes: list[dict] = []

    def add(d: str, fill: str | None = None, stroke: str | None = None,
            sw: float = 0.0, cap: str = "butt") -> None:
        shapes.append({"d": d, "fill": fill, "stroke": stroke, "sw": sw, "cap": cap})

    if plate:
        add(round_rect_path(0, 0, 100, 100, PLATE_R), fill=DEEP)
        if detail >= 1:
            add(round_rect_path(EDGE_INSET, EDGE_INSET, 100 - EDGE_INSET,
                                100 - EDGE_INSET, PLATE_R - EDGE_INSET),
                stroke=EDGE, sw=EDGE_W)

    add(arc_path(RING_CX, RING_CY, RING_R, RING_START, RING_END),
        stroke=ACCENT, sw=RING_W_MIN if detail == 0 else RING_W)

    add(circle_path(RING_CX, RING_CY, LENS_R), fill=ACCENT)
    if detail >= 1 and not transparent_hole:
        add(circle_path(RING_CX, RING_CY, LENS_HOLE), fill=DEEP)

    add(circle_path(BEACON_X, BEACON_Y, BEACON_R), fill=AMBER)
    if detail >= 2:
        add(circle_path(BEACON_X, BEACON_Y, BEACON_HALO_R), stroke=HALO, sw=BEACON_HALO_W)
        add(round_rect_path(*BAR, BAR_R), fill=ACCENT_DIM)
        for x, y, w, h, color in WAVES:
            add(round_rect_path(x, y, x + w, y + h, h / 2), fill=color)
    return shapes


def svg_document(detail: int = 2, plate: bool = True,
                 transparent_hole: bool = False, title: str = "Atlantis Watcher") -> str:
    shapes = build_shapes(detail, plate, transparent_hole)
    body = []
    for s in shapes:
        fill = s["fill"] or "none"
        stroke = s["stroke"] or "none"
        sw = f' stroke-width="{_fmt(s["sw"])}"' if s["stroke"] else ""
        cap = f' stroke-linecap="{s["cap"]}"' if s["stroke"] else ""
        body.append(f'  <path d="{s["d"]}" fill="{fill}" stroke="{stroke}"{sw}{cap}/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'width="100" height="100" role="img" aria-label="Atlantis Watcher">\n'
        f"  <title>{title}</title>\n" + "\n".join(body) + "\n</svg>\n"
    )


def android_vector(detail: int = 2, plate: bool = True,
                   transparent_hole: bool = False) -> str:
    """Android VectorDrawable：viewport 固定 100，物理尺寸 108dp 自动缩放。"""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"',
        '    android:width="108dp"',
        '    android:height="108dp"',
        '    android:viewportWidth="100"',
        '    android:viewportHeight="100">',
    ]
    for s in build_shapes(detail, plate, transparent_hole):
        fill = s["fill"] or "#00000000"
        stroke = f'\n        android:strokeColor="{s["stroke"]}"' if s["stroke"] else ""
        sw = f'\n        android:strokeWidth="{_fmt(s["sw"])}"' if s["stroke"] else ""
        cap = f'\n        android:strokeLineCap="{s["cap"]}"' if s["stroke"] else ""
        lines.append(
            f'    <path\n        android:pathData="{s["d"]}"'
            f'\n        android:fillColor="{fill}"{stroke}{sw}{cap}/>'
        )
    lines.append("</vector>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 位图渲染（Pillow，超采样 + Lanczos）
# ---------------------------------------------------------------------------
def render_icon(size: int, detail: int | None = None,
                plate: str = "square") -> Image.Image:
    """plate: square | circle | none（none 为透明前景）"""
    detail = detail_for(size) if detail is None else detail
    ss = 8 if size <= 64 else 4
    s = size * ss
    u = s / 100.0

    def p(v: float) -> int:
        return int(round(v * u))

    def box(x0: float, y0: float, x1: float, y1: float) -> list[int]:
        return [p(x0), p(y0), p(x1), p(y1)]

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if plate == "square":
        d.rounded_rectangle(box(0, 0, 100, 100), radius=p(PLATE_R), fill=rgb(DEEP) + (255,))
        if detail >= 1:
            d.rounded_rectangle(
                box(EDGE_INSET, EDGE_INSET, 100 - EDGE_INSET, 100 - EDGE_INSET),
                radius=p(PLATE_R - EDGE_INSET), outline=rgb(EDGE) + (255,),
                width=max(1, p(EDGE_W)),
            )
    elif plate == "circle":
        d.ellipse(box(0, 0, 100, 100), fill=rgb(DEEP) + (255,))

    ring_w = p(RING_W_MIN if detail == 0 else RING_W)
    d.arc(box(RING_CX - RING_R, RING_CY - RING_R, RING_CX + RING_R, RING_CY + RING_R),
          start=RING_START, end=RING_END, fill=rgb(ACCENT) + (255,), width=ring_w)

    d.ellipse(box(RING_CX - LENS_R, RING_CY - LENS_R, RING_CX + LENS_R, RING_CY + LENS_R),
              fill=rgb(ACCENT) + (255,))
    if detail >= 1:
        hole = (0, 0, 0, 0) if plate == "none" else rgb(DEEP) + (255,)
        d.ellipse(box(RING_CX - LENS_HOLE, RING_CY - LENS_HOLE,
                      RING_CX + LENS_HOLE, RING_CY + LENS_HOLE), fill=hole)

    d.ellipse(box(BEACON_X - BEACON_R, BEACON_Y - BEACON_R,
                  BEACON_X + BEACON_R, BEACON_Y + BEACON_R),
              fill=rgb(AMBER) + (255,))
    if detail >= 2:
        d.ellipse(box(BEACON_X - BEACON_HALO_R, BEACON_Y - BEACON_HALO_R,
                      BEACON_X + BEACON_HALO_R, BEACON_Y + BEACON_HALO_R),
                  outline=rgb(HALO) + (255,), width=max(1, p(BEACON_HALO_W)))
        d.rounded_rectangle(box(*BAR), radius=p(BAR_R), fill=rgb(ACCENT_DIM) + (255,))
        for x, y, w, h, color in WAVES:
            d.rounded_rectangle(box(x, y, x + w, y + h), radius=p(h / 2),
                                fill=rgb(color) + (255,))

    return img.resize((size, size), Image.LANCZOS)


def render_foreground(size: int) -> Image.Image:
    """自适应图标前景：透明画布，符号居中缩进到 66% 安全区。"""
    inner = max(8, int(size * SAFE_RATIO))
    symbol = render_icon(inner, detail=2, plate="none")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(symbol, ((size - inner) // 2, (size - inner) // 2), symbol)
    return canvas


def render_monochrome(size: int) -> Image.Image:
    """Android 13+ 主题图标：保留 alpha，颜色统一为白。"""
    src = render_foreground(size)
    out = Image.new("RGBA", src.size, (255, 255, 255, 0))
    out.putalpha(src.getchannel("A"))
    return out


def render_splash(width: int, height: int) -> Image.Image:
    """启动图：深底 + 居中品牌符号，替换 Capacitor 白色默认图。"""
    img = Image.new("RGB", (width, height), rgb(DEEP))
    mark_size = int(min(width, height) * 0.62)
    symbol = render_icon(mark_size, detail=2, plate="none")
    img.paste(symbol, ((width - mark_size) // 2, (height - mark_size) // 2), symbol)
    return img


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def write_png(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_ico(path: Path, sizes: tuple[int, ...], renderer) -> None:
    """逐尺寸独立渲染写入 ICO（Pillow 13 支持 append_images，LOD 才真正生效）。"""
    frames = {s: renderer(s) for s in sizes}
    largest = frames[max(sizes)]
    others = [frames[s] for s in sizes if s != max(sizes)]
    path.parent.mkdir(parents=True, exist_ok=True)
    largest.save(
        path, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=others,
    )
    data = path.read_bytes()
    _, typ, count = struct.unpack("<HHH", data[:6])
    assert typ == 1, f"ICO 类型异常: {typ}"
    got = []
    off = 6
    for _ in range(count):
        w = data[off] or 256
        got.append(w)
        off += 16
    assert set(got) == set(sizes), f"ICO 尺寸不完整: {got} != {list(sizes)}"


def android_colors_xml() -> str:
    """Android 主题色；configure_android.py 与图标脚本共用，避免构建链互相覆盖。"""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        '    <!-- 品牌色：由 tools/brand_assets.py 生成，勿手改 -->\n'
        f'    <color name="aw_background">{DEEP}</color>\n'
        f'    <color name="aw_accent">{ACCENT}</color>\n'
        f'    <color name="aw_surface">{HULL}</color>\n'
        f'    <color name="aw_text">{TEXT}</color>\n'
        '\n    <!-- AppCompat 主题必需色项 -->\n'
        f'    <color name="colorPrimary">{ACCENT}</color>\n'
        f'    <color name="colorPrimaryDark">{DEEP}</color>\n'
        f'    <color name="colorAccent">{ACCENT}</color>\n'
        '    <color name="white">#FFFFFF</color>\n'
        '    <color name="black">#000000</color>\n'
        '</resources>\n'
    )


def build_windows_icon() -> int:
    write_ico(ROOT / "icon.ico", WINDOWS_ICO_SIZES,
              lambda s: render_icon(s, plate="square"))
    return 1


def build_frontend_paths_module() -> None:
    """生成 Vue 组件共用的路径常量；SVG / Android vector / 网页从同一几何派生。"""
    full = build_shapes(2, plate=True, transparent_hole=False)
    mark = build_shapes(2, plate=False, transparent_hole=True)
    colors = {
        "deep": DEEP, "hull": HULL, "accent": ACCENT, "accentDim": ACCENT_DIM,
        "amber": AMBER, "text": TEXT, "coral": CORAL,
    }
    text = (
        "// 由 tools/brand_assets.py 生成，勿手改。\n"
        "// 与 favicon.svg / Android VectorDrawable 共用同一组归一化几何。\n"
        f"export const BRAND_COLORS = {json.dumps(colors, indent=2)}\n\n"
        f"export const BRAND_PATHS = {json.dumps({'full': full, 'mark': mark}, indent=2)}\n"
    )
    write_text(ROOT / "frontend" / "src" / "assets" / "brandPaths.js", text)


def build_frontend_assets() -> int:
    n = 0
    build_frontend_paths_module()
    n += 1
    # 矢量真源（项目资产 + 前端 public）
    full_svg = svg_document(2, plate=True, title="Atlantis Watcher")
    mark_svg = svg_document(2, plate=False, transparent_hole=True,
                            title="Atlantis Watcher Mark")
    write_text(BRAND_DIR / "atlantis-watcher.svg", full_svg)
    write_text(BRAND_DIR / "atlantis-watcher-mark.svg", mark_svg)
    write_text(PUBLIC_DIR / "favicon.svg", full_svg)
    n += 3

    write_ico(PUBLIC_DIR / "favicon.ico", FAVICON_ICO_SIZES,
              lambda s: render_icon(s, plate="square"))
    n += 1
    for size, name in ((16, "favicon-16.png"), (32, "favicon-32.png"),
                       (180, "apple-touch-icon.png"), (192, "icon-192.png"),
                       (512, "icon-512.png")):
        write_png(PUBLIC_DIR / name, render_icon(size, plate="square"))
        n += 1
    return n


def build_android_assets() -> int:
    if not RES_DIR.exists():
        raise SystemExit(f"未找到 Android 资源目录: {RES_DIR}")
    n = 0

    for density, scale in DENSITIES.items():
        mipmap = RES_DIR / f"mipmap-{density}"
        launcher = int(LAUNCHER_DP * scale)
        fg = int(FOREGROUND_DP * scale)
        write_png(mipmap / "ic_launcher.png", render_icon(launcher, plate="square"))
        write_png(mipmap / "ic_launcher_round.png", render_icon(launcher, plate="circle"))
        write_png(mipmap / "ic_launcher_foreground.png", render_foreground(fg))
        write_png(mipmap / "ic_launcher_monochrome.png", render_monochrome(fg))
        n += 4

    # 自适应图标（含 Android 13+ 主题单色图标）
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
        n += 1

    # 清理 Capacitor 默认模板：绿色网格背景 + Android 机器人前景
    write_text(RES_DIR / "drawable" / "ic_launcher_background.xml",
               android_vector(2, plate=True))
    write_text(RES_DIR / "drawable-v24" / "ic_launcher_foreground.xml",
               android_vector(2, plate=False, transparent_hole=True))
    n += 2

    # 品牌颜色（与 configure_android.apply_styles 保持一致，避免构建链互相覆盖）
    write_text(RES_DIR / "values" / "ic_launcher_background.xml",
               '<?xml version="1.0" encoding="utf-8"?>\n'
               '<resources>\n'
               f'    <color name="ic_launcher_background">{DEEP}</color>\n'
               '</resources>\n')
    write_text(RES_DIR / "values" / "colors.xml", android_colors_xml())
    n += 2

    # 白色默认启动图 → 深海品牌启动图（保留原有各密度尺寸与横竖目录）
    for splash in sorted(RES_DIR.glob("drawable*/splash.png")):
        with Image.open(splash) as old:
            w, h = old.size
        render_splash(w, h).save(splash, format="PNG", optimize=True)
        n += 1
    return n


def build_preview() -> Path:
    """生成品牌总览图：上排为尺寸阶梯，下排为三个真实应用场景。"""
    W, H = 1200, 500
    sheet = Image.new("RGB", (W, H), (244, 246, 248))
    d = ImageDraw.Draw(sheet)
    label = (40, 55, 75)

    d.text((28, 20), "ATLANTIS WATCHER  /  BRAND MARK", fill=(20, 32, 52))
    d.text((28, 38), "SONAR EYE  -  one geometry, every surface", fill=(90, 105, 125))
    d.line([(28, 62), (W - 28, 62)], fill=(214, 220, 228), width=1)

    # 上排：尺寸阶梯（16 → 128），按 LOD 分层
    sizes = (16, 24, 32, 48, 64, 96, 128)
    x = 36
    for size in sizes:
        icon = render_icon(size, plate="square")
        y = 84 + (128 - size) // 2
        sheet.paste(icon, (x, y), icon)
        d.text((x, 224), f"{size}px", fill=label)
        d.text((x, 240), "LOD 0" if size <= 24 else ("LOD 1" if size <= 48 else "LOD 2"),
               fill=(120, 135, 155))
        x += 110

    # 右上：256px 主图标 + 说明
    hero = render_icon(160, plate="square")
    sheet.paste(hero, (860, 80), hero)
    d.text((860, 248), "PRIMARY  /  windows exe + web favicon", fill=label)
    d.line([(28, 282), (W - 28, 282)], fill=(214, 220, 228), width=1)

    # 下排：三个场景卡
    cards = [
        (28, "DESKTOP TRAY  /  dark hull", rgb(DEEP), None),
        (428, "ANDROID THEMED  /  monochrome", (232, 238, 247), "mono"),
        (828, "ANDROID ROUND  /  launcher", (232, 238, 247), "round"),
    ]
    for cx, title, bg, mode in cards:
        cw, ch = 344, 186
        tile = Image.new("RGB", (cw, ch), bg)
        td = ImageDraw.Draw(tile)
        td.rounded_rectangle([1, 1, cw - 2, ch - 2], radius=8,
                             outline=rgb(EDGE) if bg == rgb(DEEP) else (205, 214, 226), width=1)
        if mode == "mono":
            mark = render_monochrome(108)
            if bg != rgb(DEEP):
                # 浅底上白色剪影不可见，改用青松石展示形状
                tinted = Image.new("RGBA", mark.size, rgb(ACCENT) + (255,))
                tinted.putalpha(mark.getchannel("A"))
                mark = tinted
        elif mode == "round":
            mark = render_icon(108, plate="circle")
        else:
            mark = render_icon(108, plate="square")
        tile.paste(mark, ((cw - 108) // 2, 22), mark)
        td.text((16, 148), title, fill=rgb(ACCENT_DIM) if bg == rgb(DEEP) else label)
        sheet.paste(tile, (cx, 306))

    out = BRAND_DIR / "preview.png"
    write_png(out, sheet)
    return out


def main(argv: list[str]) -> int:
    only = argv[1] if len(argv) > 1 else "--all"
    counts = {}
    if only in ("--all", "--windows"):
        counts["windows"] = build_windows_icon()
    if only in ("--all", "--frontend"):
        counts["frontend"] = build_frontend_assets()
    if only in ("--all", "--android"):
        counts["android"] = build_android_assets()
    if only == "--all":
        counts["preview"] = 1
        print("preview:", build_preview())
    for key, value in counts.items():
        print(f"{key}: {value} files")
    print("BRAND_ASSETS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
