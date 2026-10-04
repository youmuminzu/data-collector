"""统一的命令行入口逻辑，各站点脚本共用。"""

from __future__ import annotations

import argparse
import sys

from .base import BaseCollector
from .models import CircuitBroken


def run_collector(collector: BaseCollector, description: str = "") -> int:
    parser = argparse.ArgumentParser(description=description or f"{collector.site} 数据采集")
    parser.add_argument("--force", action="store_true", help="忽略进度，从头重采")
    parser.add_argument("--max-pages", type=int, default=0, help="只抓前 N 页（调试）")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="最多抓 N 条后停止；默认 20000，传 0 表示不限制",
    )
    parser.add_argument(
        "--skip-dims", action="store_true", help="只跑全量列表，不做维度采集"
    )
    parser.add_argument(
        "--dims-only",
        action="store_true",
        help="跳过全量，只按维度采集并合并维度列（全量已跑完时用）",
    )
    parser.add_argument(
        "--dim-max-pages",
        type=int,
        default=0,
        help="每个维度最多抓 N 页（调试）",
    )
    args = parser.parse_args()

    try:
        return collector.run_all(
            force=args.force,
            max_pages=args.max_pages,
            max_rows=args.max_rows,
            skip_dims=args.skip_dims,
            dims_only=args.dims_only,
            dim_max_pages=args.dim_max_pages,
        )
    except CircuitBroken:
        print("已保存进度，等待一段时间后重跑即可从断点继续")
        return 1
    except KeyboardInterrupt:
        print("\n[中断] 进度已保存，重跑本命令可续传")
        return 130


def main(collector: BaseCollector, description: str = "") -> None:
    sys.exit(run_collector(collector, description))
