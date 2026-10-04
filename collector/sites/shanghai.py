"""上海数据交易所

页面：https://nidts.chinadep.com/trading-market/product
接口：POST https://nidts.chinadep.com/dex-api/dex-es/query/all/search

要点：
  - 分页参数名是 pageNum（与北京的 pageNo 相反）
  - pageSize 硬上限 100，传 200/500 也只回 100，totalPage 恒为 87
  - 业务成功码是 200，不是 0
  - 无需登录即可读取
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://nidts.chinadep.com"
LIST_PATH = "/dex-api/dex-es/query/all/search"


class ShanghaiCollector(BaseCollector):
    site = "chinadep"
    page_size = 100
    # 主键 = id + serviceType，两者缺一不可：
    #   - id 单键会碰撞：上海聚合了「登记库」和「交易库」两套各自自增的 id 空间，
    #     实测 828 个 id 撞号（如 id=6761 同时是「全国企业资质证书信息(已登记)」
    #     和「司南万象(可交易)」两个完全无关的商品）；id 还有短自增和 19 位雪花两种形态。
    #   - serviceType 是库标识（已登记 / 可交易），与详情页链接的 type 参数一一对应
    #     （type=1 走 registerDetail，type=2 走 home/detail）。这 828 组撞号 100% 靠它区分，
    #     实测 (id, serviceType) 唯一数 = 8681 = 记录总数。它不是状态字段，不会随业务流转变化。
    # 不要用「商品名+供方+发布时间」这类业务字段组合：实测会误合并同名同供方同时间的
    # 不同商品（id=2061147820246315009 与 2061147842006364162 被当成一条丢掉）。
    key_fields = ("id", "serviceType")
    success_code = 200

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/trading-market/product",
    }

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="POST",
            json_body={"pageNum": page, "pageSize": self.page_size},
        )

    def parse(self, payload: dict) -> PageResult:
        data = payload.get("data") or {}
        return PageResult(
            rows=data.get("list") or [],
            total=data.get("total"),
            page_echo=data.get("pageNum"),
        )
