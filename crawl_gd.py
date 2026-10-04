"""广东数据交易所 —— 数据商品采集入口

约 11 万条、pageSize 上限 100，全量约 1100+ 页，耗时较长，建议后台跑：
  uv run python crawl_gd.py
  uv run python crawl_gd.py --force        # 从头重采
  uv run python crawl_gd.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.guangdong import GuangdongCollector

if __name__ == "__main__":
    main(GuangdongCollector(), "广东数据交易所商品采集")
