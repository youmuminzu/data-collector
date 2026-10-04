"""贵阳大数据交易所 —— 数据商品采集入口

用法：
  uv run python crawl_gy.py                # 首次采集 / 断点续传
  uv run python crawl_gy.py --force        # 从头重采
  uv run python crawl_gy.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.guiyang import GuiyangCollector

if __name__ == "__main__":
    main(GuiyangCollector(), "贵阳大数据交易所商品采集")
