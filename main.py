# -*- coding: utf-8 -*-
"""Atlantis Watcher 进程入口。

保持极简：import 本模块不产生任何副作用（不建 FastAPI 实例、不挂静态目录、
不加载重量级依赖）。全部启动逻辑位于 app.bootstrap。
"""
import sys


def main() -> int:
    from app.bootstrap import bootstrap
    return bootstrap()


if __name__ == "__main__":
    sys.exit(main())
