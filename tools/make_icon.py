# -*- coding: utf-8 -*-
"""兼容入口：生成多尺寸 Windows 图标 icon.ico。

实际绘制逻辑已收敛到 tools/brand_assets.py（单一品牌真源），
本文件只保留历史调用契约与 ICO 帧校验，避免两套绘制代码各自漂移。

用法:
    python tools/make_icon.py
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_assets import ROOT, WINDOWS_ICO_SIZES, build_windows_icon  # noqa: E402


def verify_ico(path: Path) -> None:
    data = path.read_bytes()
    reserved, typ, count = struct.unpack("<HHH", data[:6])
    assert typ == 1, f"ICO 类型异常: {typ}"

    off = 6
    frames = []
    for _ in range(count):
        w, h, _, _, _, _, size, _ = struct.unpack("<BBBBHHII", data[off:off + 16])
        frames.append((w or 256, size))
        off += 16

    assert {w for w, _ in frames} == set(WINDOWS_ICO_SIZES), \
        f"尺寸不完整: {[w for w, _ in frames]}"
    for i, (w, size) in enumerate(frames, 1):
        print(f"  #{i}: {w}x{w}  {size}B")
    print(f"文件大小: {len(data)} 字节")


def main() -> int:
    build_windows_icon()
    target = ROOT / "icon.ico"
    print(f"已生成 {target}")
    verify_ico(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
