"""北方大数据交易平台 —— 数据商品采集入口

用法：
  uv run python crawl_bf.py                # 首次采集 / 断点续传
  uv run python crawl_bf.py --force        # 从头重采
  uv run python crawl_bf.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.beifang import BeifangCollector

if __name__ == "__main__":
    main(BeifangCollector(), "北方大数据交易平台商品采集")
