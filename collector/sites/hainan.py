"""海南省数据产品超市（海南数据交易所）

页面：https://transaction.datadex.cn/app/dataMarket
接口：POST https://transaction.datadex.cn/api/resource/searchBy

要点：
  - 分页同时要传 paging 对象和 pageNo/pageSize，缺一不可
  - pageSize 上限至少 500（页面默认 12），总量 2832 条
  - 业务成功码 0，数据在 data.list，总数 data.total
  - proResourceId 唯一，可直接做主键
  - **列表接口不回显行业分类**（proIndustryType 恒为空），商品归属只能按 industry
    逐个维度筛选反推，见下方 dimensions（20 项，传值是标签 id，32 位十六进制）
"""

from __future__ import annotations

import time

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://transaction.datadex.cn"
LIST_PATH = "/api/resource/searchBy"


# 行业分类标签：POST https://transaction.datadex.cn/api/listCommonConfig/RESOURCE_TYPE
# 一类的标签 id（32 位十六进制）；页面另有「场景分类」「所属领域」两组，是不同 tagFidCode
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("4f70e3bff987eed986df4dd941e0bbaf", "农、林、牧、渔业"),
    ("6c81ec3b0911506fa3c2540dfdf4c795", "采矿业"),
    ("872c9287c6d47d1e777200b3bde9d19a", "制造业"),
    ("ed3e750a82336caf79f506c7210c40fc", "电力、热力、燃气及水生产和供应业"),
    ("1fea75deac97b01671e54a71c1477951", "建筑业"),
    ("d25d160e738d832cb52448beb30ce585", "交通运输、仓储和邮政业"),
    ("6da5a33a959f67b6d33a7256126cba8f", "信息传输、软件和信息技术服务业"),
    ("5de2731f3f111b7969e4d22f91b11561", "批发和零售业"),
    ("d7a2b682cb974778e2a7a2bb211b0c29", "住宿和餐饮业"),
    ("57d5e08e8e5e6d7dc09aa5b478f7aa5c", "金融业"),
    ("adbfd2943ddedf4ffdee6abe610825fd", "房地产业"),
    ("fd2f53323aa809b1531458322d220fa4", "租赁和商务服务业"),
    ("8575bdc6ef45c49e3475badb5346a81d", "科学研究和技术服务业"),
    ("c7eb10447dec90ff6212d91801173967", "水利、环境和公共设施管理业"),
    ("be8896468595c7eeadf4aa382a6249c3", "居民服务、修理和其他服务业"),
    ("951d360695f48281874c5c9bff141081", "教育"),
    ("6f4b340c869f5397d7b7450092d33a46", "卫生和社会工作"),
    ("614f12fea396b601dd4966e6c960bb90", "文化、体育和娱乐业"),
    ("8c30bb9bdfdb567c42fa52550ad90504", "公共管理、社会保障和社会组织"),
    ("743f2ae7f2a0cfab200e2655d38ed7ea", "国际组织"),
)


class HainanCollector(BaseCollector):
    site = "datadex"
    page_size = 100
    key_fields = ("proResourceId",)
    success_code = 0

    # 列表不回显行业分类 → 按维度逐个筛选反推
    dim_field = "industry"
    dim_label = "行业分类"
    dim_output_column = "industry"
    dimensions = DIMENSIONS

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/app/dataMarket",
    }

    def build_request(self, page: int) -> PageRequest:
        size = self.page_size
        body = {
            "timestamp": int(time.time() * 1000),
            "index": 0,
            "saleFeesType": "",
            "sceneSecondTag": "",
            "sceneThirdTag": "",
            "paging": {"current": page, "size": size, "total": 0},
            "pageNo": page,
            "searchKey": "",
            "pageSize": size,
        }
        if self.dim_filter:
            body.update(self.dim_filter)
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="POST",
            json_body=body,
        )

    def parse(self, payload: dict) -> PageResult:
        data = payload.get("data") or {}
        return PageResult(
            rows=data.get("list") or [],
            total=data.get("total"),
            page_echo=data.get("current"),
        )
