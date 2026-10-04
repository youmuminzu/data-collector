"""福建大数据交易平台 —— 数据商品采集入口

福建站的列表接口**不回显所属行业**，所以采集分两步：
  1. 全量列表（不传 type 即为全部 1265 条）
  2. 按所属行业 18 个维度逐个筛选，反推每个商品属于哪些行业，
     合并出 industry_involved / industry_involved_code 两列写回 CSV

用法：
  uv run python crawl_fj.py                # 全量 + 维度，断点续传
  uv run python crawl_fj.py --dims-only    # 全量已跑完，只补维度列
  uv run python crawl_fj.py --skip-dims    # 只要全量列表
  uv run python crawl_fj.py --force        # 从头重采
  uv run python crawl_fj.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.fujian import FujianCollector

if __name__ == "__main__":
    main(FujianCollector(), "福建大数据交易平台商品采集（含所属行业维度）")
