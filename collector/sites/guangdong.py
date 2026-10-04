"""广东数据交易所（广州数据交易所）

页面：https://www.cantonde.com/sjjy.html#/list
接口：POST https://www.cantonde.com/si/sjjy/list

要点：
  - 无需登录，但会先取临时 token，列表接口本身直接可查
  - pageSize 硬上限 100（传 500/1000 也只回 100），总量约 11 万条 → 1100+ 页
  - 响应结构特殊：数据在 data（列表），总数在 extra.total
  - 字段是拼音缩写：CPMC 产品名、KHQC 供方全称、CPMS 描述、CPBH 产品编号、
    CPJG 价格、SJSJ 上架时间、CPZT 状态
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://www.cantonde.com"
LIST_PATH = "/si/sjjy/list"


class GuangdongCollector(BaseCollector):
    site = "cantonde"
    page_size = 100  # 后端硬上限
    key_fields = ("ID",)
    success_code = 200

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/sjjy.html",
    }

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="POST",
            json_body={
                "SORT": 0,
                "pageNo": page,
                "pageSize": self.page_size,
                "SSZQ": "5",
                "ISSW": 2,
                "KSRQ": "",
                "JSRQ": "",
            },
        )

    def parse(self, payload: dict) -> PageResult:
        rows = payload.get("data") or []
        extra = payload.get("extra") or {}
        total = extra.get("total")
        return PageResult(
            rows=rows,
            total=int(total) if total is not None else None,
            page_echo=None,  # 该接口不回显页码
        )
