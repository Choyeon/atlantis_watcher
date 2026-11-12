# -*- coding: utf-8 -*-
"""兼容入口：生成 Android 全套图标与启动资源。

实际绘制逻辑已收敛到 tools/brand_assets.py（单一品牌真源）。
产出：mipmap 全密度方形/圆形/自适应前景/单色主题图标、
anydpi-v26 自适应图标 XML、品牌矢量 drawable、深色启动图、主题色。

用法:
    python tools/make_android_icon.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_assets import (  # noqa: E402
    DENSITIES, RES_DIR, build_android_assets,
)


def main() -> int:
    if not RES_DIR.exists():
        raise SystemExit(f"未找到 Android 资源目录: {RES_DIR}\n请先执行: npx cap add android")

    total = build_android_assets()
    print(f"已生成 {total} 个 Android 图标/资源文件")
    print(f"  密度目录: {', '.join(DENSITIES.keys())}")
    print("  自适应前景 + 单色主题图标: mipmap-{mdpi..xxxhdpi}")
    print("  模板残留已替换: drawable/ic_launcher_background.xml, "
          "drawable-v24/ic_launcher_foreground.xml, drawable*/splash.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
