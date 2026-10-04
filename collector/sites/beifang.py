"""北方大数据交易平台

页面：https://exchange.datadmz.com:30101/datadmz/tradeFloor/list
接口：POST https://exchange.datadmz.com:30101/api/product/dataMarket/selectProductList

要点：
  - 非标准端口 30101，证书链不完整，需关掉 SSL 校验（verify=False）
  - 分页参数 pageNum，pageSize 上限至少 500，总量 1189 条
  - total 返回的是字符串，需转 int
  - 业务成功码 200
  - sourcePlatform 传空数组即默认全部平台
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://exchange.datadmz.com:30101"
LIST_PATH = "/api/product/dataMarket/selectProductList"


class BeifangCollector(BaseCollector):
    site = "datadmz"
    page_size = 100
    key_fields = ("productId",)
    success_code = 200
    verify = False  # 该站证书链不完整

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/datadmz/tradeFloor/list",
    }

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="POST",
            json_body={
                "name": "",
                "listPlatform": "01",
                "pageNum": page,
                "pageSize": self.page_size,
                "dataSource": [],
                "useIndustry": [],
                "dataProductType": [],
                "sourcePlatform": [],
            },
        )

    def parse(self, payload: dict) -> PageResult:
        rows = payload.get("rows") or []
        total = payload.get("total")
        try:
            total = int(total) if total is not None else None
        except (TypeError, ValueError):
            total = None
        return PageResult(
            rows=rows,
            total=total,
            page_echo=None,  # 该接口不回显页码
        )
