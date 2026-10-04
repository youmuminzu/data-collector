"""郑州数据交易中心

页面：https://market.zzbdex.com/trade/product
接口：POST https://market.zzbdex.com/data-deal-admin/frontDeskHomePage/frontPageProduct

要点：
  - pageSize 上限至少 500，总量 567 条
  - 业务成功码 0（注意是 0 不是 200）
  - 主键用 id，另有 assetCode 资产编号
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://market.zzbdex.com"
LIST_PATH = "/data-deal-admin/frontDeskHomePage/frontPageProduct"


class ZhengzhouCollector(BaseCollector):
    site = "zzbdex"
    page_size = 100
    key_fields = ("id",)
    success_code = 0

    # 列表只回显 sceneName（中文场景名），sceneCode 恒为 null，编码只能靠名称反查。
    # 下面这张表是 2026-10-03 逐个用 sceneCode 筛选、取结果集 sceneName 交集反推校验过的，
    # 与 dimensions/站点维度条目明细.csv 的郑州段一致。
    dim_echo_column = "sceneName"
    dim_code_column = "scene_code"
    dim_name_to_code = {
        "三农": "195", "制造": "196", "金融": "197", "住建": "198", "交通": "199",
        "文旅": "200", "时空": "201", "政务": "202", "零售": "203", "医疗": "204",
        "通信": "2243", "能源": "2244", "环保": "2245", "信用": "2246",
        "企服": "2247", "综合": "2248", "教育": "2257",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/trade/product",
    }

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="POST",
            json_body={
                "pageNum": page,
                "pageSize": self.page_size,
                "sceneCode": "",
                "tags": "",
                "industryZone": "",
                "areaCode": "",
                "productType": "",
                "dataType": "",
                "orderType": 0,
                "orderByComprehensive": 1,
            },
        )

    def parse(self, payload: dict) -> PageResult:
        data = payload.get("data") or {}
        if isinstance(data, list):  # 兜底：有时直接返回列表
            return PageResult(rows=data, total=None, page_echo=None)
        rows = data.get("list") or data.get("records") or []
        return PageResult(
            rows=rows,
            total=data.get("total"),
            page_echo=data.get("pageNum"),
        )
