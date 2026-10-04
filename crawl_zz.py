"""郑州数据交易中心 —— 数据商品采集入口

用法：
  uv run python crawl_zz.py                # 首次采集 / 断点续传
  uv run python crawl_zz.py --force        # 从头重采
  uv run python crawl_zz.py --max-pages 3  # 调试
"""

from collector.cli import main
from collector.sites.zhengzhou import ZhengzhouCollector

if __name__ == "__main__":
    main(ZhengzhouCollector(), "郑州数据交易中心商品采集")
