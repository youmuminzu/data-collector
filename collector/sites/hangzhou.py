"""杭州数据交易所

页面：https://mall.hzdex.cn/data-exchange
接口：GET https://mall.hzdex.cn/api/uniformItem/mall/search

要点：
  - Next.js 站点，但 __NEXT_DATA__ 只有骨架，数据靠客户端请求
  - 分页参数 pageNo，pageSize 上限至少 500（按站点惯例取 100）
  - frontCategoryId 传任意值都不影响 total（实测 0/1/2/20 均为 3197），
    即默认就是全量商品，无需分类遍历
  - 响应没有业务码字段，靠 data 是否为空判断；成功时 success_code 设为 None
  - productId 全局唯一，可直接做主键
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://mall.hzdex.cn"
LIST_PATH = "/api/uniformItem/mall/search"


class HangzhouCollector(BaseCollector):
    site = "hzdex"
    page_size = 100
    key_fields = ("productId",)
    success_code = None  # 该接口成功响应不含 code 字段

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/data-exchange",
    }

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="GET",
            params={
                "frontCategoryId": 20,
                "keyword": "",
                "pageNo": page,
                "pageSize": self.page_size,
            },
        )

    def parse(self, payload: dict) -> PageResult:
        data = payload.get("data")
        if not data:
            raise RuntimeError(f"响应缺少 data：{str(payload)[:120]}")
        return PageResult(
            rows=data.get("data") or [],
            total=data.get("total"),
            page_echo=None,  # 该接口不回显页码
        )
