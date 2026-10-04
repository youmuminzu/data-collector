"""贵阳大数据交易所

页面：https://www.gzdex.com.cn/market/
接口：GET https://www.gzdex.com.cn/apaas/serviceapp/v3/servicemarket/dataShop/list

要点：
  - 不需要按分类遍历：不传 serviceType1 时返回全量 2018 条
    （分类明细：数据产品和服务 1035、数据资源 719、算法模型 115、高质量数据集 93）
  - 分页参数是 page / size（不是 pageNo / pageSize）
  - 总数在响应顶层的 total，不在 data 里
  - 成功标志是 success=1，没有 code 字段，因此覆盖 check_success
"""

from __future__ import annotations

from collector.base import BaseCollector
from collector.models import PageRequest, PageResult

BASE_URL = "https://www.gzdex.com.cn"
LIST_PATH = "/apaas/serviceapp/v3/servicemarket/dataShop/list"


class GuiyangCollector(BaseCollector):
    site = "gzdex"
    page_size = 100
    key_fields = ("id",)
    success_code = None

    # 列表只回显 sectors_name（中文名），sectors 列恒为整数 0，不是编码，只能靠名称反查。
    # 491~510 是国标 20 门类；4/26/28/338 是站点自定义场景标签，商品数很少（2~5 条）
    # 但确实可筛选——扫描 dataDomains 全量编号（1~600）才定位到，页面下拉里看不到。
    # 全部经「逐个筛选 + 结果集 sectors_name 求交集」实测校验，与 dimensions/站点维度
    # 条目明细.csv 的贵阳段一致。
    dim_echo_column = "sectors_name"
    dim_code_column = "sectors_code"
    dim_name_to_code = {
        "科技创新": "4", "智慧城市": "26", "生活服务": "28", "其他场景": "338",
        "农、林、牧、渔业": "491", "采矿业": "492", "制造业": "493",
        "电力、热力、燃气及水生产和供应业": "494", "建筑业": "495",
        "批发和零售业": "496", "交通运输、仓储和邮政业": "497", "住宿和餐饮业": "498",
        "信息传输、软件和信息技术服务业": "499", "金融业": "500", "房地产业": "501",
        "租赁和商务服务业": "502", "科学研究和技术服务业": "503",
        "水利、环境和公共设施管理业": "504", "居民服务、修理和其他服务业": "505",
        "教育": "506", "卫生和社会工作": "507", "文化、体育和娱乐业": "508",
        "公共管理、社会保障和社会组织": "509", "国际组织": "510",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/market/",
    }

    def check_success(self, payload: dict) -> None:
        """该站用 success=1 表示成功，没有 code 字段。"""
        if payload.get("success") != 1:
            raise RuntimeError(
                f"业务失败 success={payload.get('success')} "
                f"errMsg={payload.get('errMsg')}"
            )

    def build_request(self, page: int) -> PageRequest:
        return PageRequest(
            url=f"{BASE_URL}{LIST_PATH}",
            method="GET",
            params={
                "serviceType1": "",
                "serviceType2s": "",
                "serviceType3s": "",
                "orderBy": 0,
                "serviceName": "",
                "ifTryOut": "",
                "page": page,
                "size": self.page_size,
            },
        )

    def parse(self, payload: dict) -> PageResult:
        rows = payload.get("data") or []
        return PageResult(
            rows=rows,
            total=payload.get("total"),
            page_echo=payload.get("page"),
        )
