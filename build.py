# -*- coding: utf-8 -*-
"""
Atlantis Watcher — 构建入口（向后兼容）

完整实现已迁移至 build_release.py，本文件保留为薄入口以兼容既有调用方式：

    python build.py                # 等价于 python build_release.py
    python build.py --installer    # 生成安装包
    python build.py --onefile      # 单文件便携版

构建体系说明见 BUILD_README.md。
"""

import sys

from build_release import main

if __name__ == '__main__':
    sys.exit(main())
