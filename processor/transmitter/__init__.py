"""R2 上传模块：把 processeddata 的产物推到 Cloudflare R2，并回写上传时间。

命令行：
    uv run python processor/transmitter/transtoR2.py --all

当库用：
    from processor.transmitter import load_config, build_client, collect
"""

from .transtoR2 import (  # noqa: F401
    DEFAULT_PREFIX,
    SRC_DIR,
    build_client,
    collect,
    decide,
    load_config,
    read_stamps,
    stamp_dict_file,
    stamp_index,
    upload,
)

__all__ = [
    "DEFAULT_PREFIX",
    "SRC_DIR",
    "build_client",
    "collect",
    "decide",
    "load_config",
    "read_stamps",
    "stamp_dict_file",
    "stamp_index",
    "upload",
]
