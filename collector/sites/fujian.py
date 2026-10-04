"""福建大数据交易平台

页面：https://trade.fjbdex.com/ltywpt/dataMarket
接口：GET https://trade.fjbdex.com/ltywpt-api/api/data-portal-center/portal/catentry/list

要点：
  - type 参数区分商品形态：1=数据集 958 条、3=AI模型 307 条；
    **不传 type 时返回全量 1265 条**，无需按类型分别抓取
  - 分页参数 pageNo / pageSize，数据键是 result.records
  - 业务成功码 200
  - **列表接口不回显所属行业**，商品归属只能按 industryInvolved 逐个维度筛选反推，
    见下方 dimensions（18 项，传值是字典 value，32 位十六进制）
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://trade.fjbdex.com"
LIST_PATH = "/ltywpt-api/api/data-portal-center/portal/catentry/list"


# 所属行业字典：GET .../jeecg-system/sys/dict/getDictItems/industry_involved
# 传字典的 value（32 位十六进制），不是 dictCode
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("11017935448d4ed5aa7d61fe677cd688", "农、林、牧、渔业"),
    ("8a53a767da8c426eae52261f1dd4495f", "采矿业"),
    ("4fc6abd83a7c484aa78a377d5f3a1075", "制造业"),
    ("22ce692367aa4f11b331675a0d069697", "电力、热力、燃气及水生产和供应业"),
    ("5b1b3af8977742a9ac5f5b5399cd47de", "建筑业"),
    ("c4098a5616c94b2d97cd1a7600b0f4e6", "批发和零售业"),
    ("138306c78f624fe5baf013819c3ccbc8", "交通运输、仓储和邮政业"),
    ("9ae9180b8c1c48359fdf3d6237726e43", "信息传输、软件和信息技术服务业"),
    ("bed80cc07f6b4dff959bbc1e8a68f126", "金融业"),
    ("e11d30bc59404b238571849b0d53f906", "房地产业"),
    ("85fb3760e5a04122b46418d56c07bff1", "租赁和商务服务业"),
    ("23b0ac091a374152b098a557b64ce3ae", "科学研究和技术服务业"),
    ("74c5130ad6b1494799600151a0763553", "水利、环境和公共设施管理业"),
    ("a1c35ee7645747cb8e701b7eacc1b9d5", "教育"),
    ("27cc2652dcb845f7925368a773266c32", "卫生和社会工作"),
    ("1abaacb59d2445f29f548c8a017ae6b4", "文化、体育和娱乐业"),
    ("8f3325f6e80943c4bbc6b4f963c0a464", "公共管理、社会保障和社会组织"),
    ("9046d122b2b74f69ab961db41d561517", "其他"),
)


class FujianCollector(BaseCollector):
    site = "fjbdex"
    page_size = 100
    key_fields = ("id",)
    success_code = 200

    # 列表不回显所属行业 → 按维度逐个筛选反推
    dim_field = "industryInvolved"
    dim_label = "所属行业"
    dim_output_column = "industry_involved"
    dimensions = DIMENSIONS

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/ltywpt/dataMarket",
    }

    def build_request(self, page: int) -> PageRequest:
        params = {
            "labelId": "",
            "sceneId": "",
            "level": "",
            "sortType": "",
            "assetCategory": "",
            "dataType": "",
            "industryInvolved": "",
            "pageNo": page,
            "pageSize": self.page_size,
            "type": "",
            "sort": "",
        }
        if self.dim_filter:
            params.update(self.dim_filter)
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="GET",
            params=params,
        )

    def parse(self, payload: dict) -> PageResult:
        res = payload.get("result") or {}
        return PageResult(
            rows=res.get("records") or [],
            total=res.get("total"),
            page_echo=res.get("pageNo"),
        )
