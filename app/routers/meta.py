# -*- coding: utf-8 -*-
"""元信息路由：主页、健康检查、运行时状态。

/health 是 APK 局域网自动嗅探的命中契约，必须保持
`service == "Atlantis Watcher"`，且尽量轻量（不读注册表、不枚举网卡）。
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app import __version__ as APP_VERSION
from app import paths
from app.runtime import get_context

router = APIRouter(tags=["meta"])

_MISSING_FRONTEND_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Atlantis Watcher · 前端未构建</title>
<style>body{background:#0b1220;color:#dbe7ef;font:14px/1.8 ui-monospace,Consolas,monospace;padding:48px;max-width:720px;margin:auto}
h1{color:#35d6bd;font-size:20px}code{background:#16243a;padding:2px 8px;border-radius:4px;color:#f5b642}
p{color:#8fa6bb}</style></head>
<body><h1>服务已启动，但前端产物缺失</h1>
<p>后端接口正常，仅缺少 <code>static/dist/index.html</code>。</p>
<p>在项目根目录执行：<br><code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code></p>
<p>构建完成后刷新本页即可。健康检查：<code>/health</code>；运行时信息：<code>/api/runtime</code>。</p>
</body></html>"""


@router.get("/", summary="主页")
async def read_root():
    index = paths.dist_dir() / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(_MISSING_FRONTEND_HTML, status_code=503)


@router.get("/health", summary="健康检查")
async def health_check():
    # 局域网嗅探会高频命中此端点：只读带缓存的地址，不触碰注册表/网卡枚举
    ip, port = get_context().endpoint()
    return {
        "status": "healthy",
        "service": "Atlantis Watcher",
        "version": APP_VERSION,
        "port": port,
        "ip": ip,
        "url": f"http://{ip}:{port}",
    }


@router.get("/api/runtime", summary="运行时信息")
async def runtime_info():
    """完整运行状态：地址列表、运行时长、自启状态、日志与设置文件路径"""
    return get_context().runtime_info()


# ---------------------------------------------------------------------------
# 根级品牌图标
#
# index.html 以相对路径引用 ./favicon.svg / ./favicon.ico，浏览器实际请求
# 的是站点根（/favicon.svg）。后端只挂载了 /static 与 /assets，过去这些
# 请求全部 404，标签页与快捷方式拿不到图标。这里按白名单从 dist 根提供，
# 冻结态路径同样由 app.paths.dist_dir() 解析到 _MEIPASS/static/dist。
# ---------------------------------------------------------------------------
_ICON_FILES = {
    "favicon.svg": "image/svg+xml",
    "favicon.ico": "image/x-icon",
    "favicon-16.png": "image/png",
    "favicon-32.png": "image/png",
    "apple-touch-icon.png": "image/png",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
}


def _icon_handler(filename: str, media_type: str):
    async def serve():
        target = paths.dist_dir() / filename
        if not target.is_file():
            raise HTTPException(status_code=404, detail=f"缺少品牌资源: {filename}")
        return FileResponse(target, media_type=media_type)

    return serve


for _name, _media in _ICON_FILES.items():
    router.add_api_route(
        f"/{_name}",
        _icon_handler(_name, _media),
        methods=["GET"],
        include_in_schema=False,
        name="brand_icon_" + _name.replace(".", "_").replace("-", "_"),
    )
