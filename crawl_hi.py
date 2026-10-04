"""海南省数据产品超市 —— 数据商品采集入口

海南站的列表接口**不回显行业分类**（proIndustryType 恒为空），所以采集分两步：
  1. 全量列表
  2. 按行业分类 20 个维度逐个筛选，反推每个商品属于哪些行业，
     合并出 industry / industry_code 两列写回 CSV

用法：
  uv run python crawl_hi.py                # 全量 + 维度，断点续传
  uv run python crawl_hi.py --dims-only    # 全量已跑完，只补维度列
  uv run python crawl_hi.py --skip-dims    # 只要全量列表
  uv run python crawl_hi.py --force        # 从头重采
  uv run python crawl_hi.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.hainan import HainanCollector

if __name__ == "__main__":
    main(HainanCollector(), "海南省数据产品超市商品采集（含行业分类维度）")
