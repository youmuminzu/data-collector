"""北京大数据交易所

页面：https://mall.bjidex.com/transaction-management/data-mall
接口：POST https://api.bjidex.com/product/api/productIndex/getProductList

要点：
  - 分页参数名是 pageNo（不是 pageNum，传错会被静默忽略）
  - 后端上限 pageSize=500，但按页面显示粒度取 100 足够，且实测 100 更快（0.6s vs 9s）
  - 业务成功码 0
  - **列表接口不回显应用领域**，商品归属只能按 goodsArea 逐个维度筛选反推，
    见下方 dimensions（31 项，传值是字典 dictValue）
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://api.bjidex.com"
LIST_PATH = "/product/api/productIndex/getProductList"


# 应用领域字典：POST https://api.bjidex.com/iam/api/dict/data/findDicByCode
# body {"dictCode":"product_field"} → dictValue 0~30
# （页面另有「应用行业」用 goodsIndustry，国标门类 0~19，是另一套维度，别混）
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("0", "工业"), ("1", "政务"), ("2", "医疗"), ("3", "能源"), ("4", "金融"),
    ("5", "交通"), ("6", "文旅"), ("7", "司法"), ("8", "跨境"), ("9", "电子商务"),
    ("10", "智能服务"), ("11", "互联网/IT/电子/通信"), ("12", "教育"),
    ("13", "交通/物流/贸易/零售"), ("14", "学术科研"), ("15", "房地产"),
    ("16", "汽车"), ("17", "医疗卫生"), ("18", "广告/传媒/文化/体育"),
    ("19", "能源化工"), ("20", "政府/公共事业"), ("21", "住宿/餐饮"),
    ("22", "建筑/房产"), ("23", "采矿"), ("24", "交通/物流"), ("25", "贸易/零售"),
    ("26", "工业制造"), ("27", "农/林/牧/渔"), ("28", "水力/电力/热力/燃气"),
    ("29", "租赁/商务"), ("30", "居民服务"),
)


class BeijingCollector(BaseCollector):
    site = "bjidex"
    page_size = 100
    key_fields = ("uuid",)  # 北京站 uuid 全局唯一
    success_code = 0

    # 列表不回显应用领域 → 按维度逐个筛选反推
    dim_field = "goodsArea"
    dim_label = "应用领域"
    dim_output_column = "goods_area"
    dimensions = DIMENSIONS

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://mall.bjidex.com",
        "Referer": "https://mall.bjidex.com/transaction-management/data-mall",
    }

    def _dim_payload(self, code: str) -> dict:
        # 北京的应用领域筛选是数组
        return {self.dim_field: [code]}

    def build_request(self, page: int) -> PageRequest:
        body: dict = {"pageNo": page, "pageSize": self.page_size}
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
            rows=data.get("records") or [],
            total=data.get("total"),
            page_echo=data.get("pageNo"),
        )
