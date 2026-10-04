"""北京大数据交易所 —— 数据商品采集入口

北京站的列表接口**不回显应用领域**，所以采集分两步：
  1. 全量列表（uuid 等 23 个字段）
  2. 按应用领域 31 个维度逐个筛选，反推每个商品属于哪些领域，
     合并出 goods_area / goods_area_code 两列写回 CSV

用法：
  uv run python crawl_bj.py                # 全量 + 维度，断点续传
  uv run python crawl_bj.py --dims-only    # 全量已跑完，只补维度列
  uv run python crawl_bj.py --skip-dims    # 只要全量列表
  uv run python crawl_bj.py --force        # 忽略进度，从头重采
  uv run python crawl_bj.py --max-pages 3  # 只抓前 3 页（调试）
"""

from collector.cli import main
from collector.sites.beijing import BeijingCollector

if __name__ == "__main__":
    main(BeijingCollector(), "北京大数据交易所商品采集（含应用领域维度）")
