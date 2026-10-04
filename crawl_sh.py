"""上海数据交易所 —— 数据商品采集入口

用法：
  uv run python crawl_sh.py                # 首次采集 / 断点续传
  uv run python crawl_sh.py --force        # 忽略进度，从头重采
  uv run python crawl_sh.py --max-pages 3  # 只抓前 3 页（调试）
"""

from collector.cli import main
from collector.sites.shanghai import ShanghaiCollector

if __name__ == "__main__":
    main(ShanghaiCollector(), "上海数据交易所商品采集")
