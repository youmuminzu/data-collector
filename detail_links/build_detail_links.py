"""生成「商品列表卡片 → 商品详情页」跳转链接对照成果。

数据来源：2026-10-03 用 Playwright 实机打开 9 个站点的列表页、点击商品卡片，
捕获跳转后的 URL（含新标签页），并逐个校验 URL 里的 ID 对应的列表字段。

产出：
  - 详情页跳转链接.csv   每站一行：URL 模板、打开方式、详情数据接口
  - 详情链接参数明细.csv  每个占位参数一行：含义、取值规则、来源字段
"""

from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).parent

# 站点 -> 链接模板
LINKS = [
    {
        "站点": "北京大数据交易所",
        "站点代号": "bjidex",
        "列表页": "https://mall.bjidex.com/transaction-management/data-mall",
        "详情页URL模板": "https://mall.bjidex.com/transaction-management/data-product-details?productId={productId}",
        "打开方式": "新标签页（列表页 URL 不变）",
        "占位参数": "productId",
        "卡片热区": ".product-item（标题 .product-item__title、供方 .product-item__org 均可点）",
        "详情页数据接口": "需签名鉴权：先 POST /iam/api/sms-manage/getSecretKey；直接调商品接口返 401",
        "样例": "productId=e79998a79f7e1d49d9d23a6a91e80d43（标讯数据…）",
        "备注": "卡片任意位置点击都跳同一 productId；详情页数据接口带签名，裸调 401",
    },
    {
        "站点": "上海数据交易所",
        "站点代号": "chinadep",
        "列表页": "https://nidts.chinadep.com/trading-market/product",
        "详情页URL模板": "https://nidts.chinadep.com/trading-market/product/detail?id={id}&type={type}&from=admin&productType=2",
        "打开方式": "同标签路由跳转",
        "占位参数": "id, type",
        "卡片热区": ".ProductCardContainer",
        "详情页数据接口": "type=1 → GET /dex-api/daep/broker/product/registerDetail/{id}；type=2 → GET /dex-api/daep/broker/product/home/detail?id={id}&industryCenter=",
        "样例": "id=6829&type=1（已登记）；id=7387&type=2（可交易）",
        "备注": "type 必须与实际状态一致，已登记商品用 type=2 会打开空白页；productType 实测 1/2/3 无差异",
    },
    {
        "站点": "杭州数据交易所",
        "站点代号": "hzdex",
        "列表页": "https://mall.hzdex.cn/data-exchange",
        "详情页URL模板": "https://mall.hzdex.cn/data-exchange/{productId}?from=%2Fdata-exchange",
        "打开方式": "同标签路由跳转",
        "占位参数": "productId, from",
        "卡片热区": ".hot-product_title__eARqw",
        "详情页数据接口": "GET https://www.hzcsds.com/api/portal-web/v3/dataProductRegister/selectByProductId?productId={productId}&dataSource=0",
        "样例": "691330127MA28NJBQ8X3301HZ0139565",
        "备注": "用 productId（25 位业务编码），不是 id（纯数字 117406300140097）",
    },
    {
        "站点": "广东数据交易所",
        "站点代号": "cantonde",
        "列表页": "https://www.cantonde.com/sjjy.html#/list",
        "详情页URL模板": "https://www.cantonde.com/sjjy.html#/detail?id={id}",
        "打开方式": "新标签页（hash 路由）",
        "占位参数": "id",
        "卡片热区": ".prj-sjjy-fr（卡片内的 <a>）",
        "详情页数据接口": "POST https://www.cantonde.com/si/sjjy/detail1  body {\"CPID\": id}",
        "样例": "id=8376",
        "备注": "id 是自增 ID，不是 CPBH 产品编号（CDE202601CPA00114）",
    },
    {
        "站点": "贵阳大数据交易所",
        "站点代号": "gzdex",
        "列表页": "https://www.gzdex.com.cn/market/（自动跳转 /market/list）",
        "详情页URL模板": "https://www.gzdex.com.cn/market/detail/{id}",
        "打开方式": "同标签路由跳转",
        "占位参数": "id",
        "卡片热区": ".card-title",
        "详情页数据接口": "GET https://www.gzdex.com.cn/apaas/serviceapp/v3/servicemarket/detail?serviceId={id}",
        "样例": "id=5504",
        "备注": "详情页路径是 /market/detail/{id}，与列表页 /market/list 同级",
    },
    {
        "站点": "福建大数据交易平台",
        "站点代号": "fjbdex",
        "列表页": "https://trade.fjbdex.com/ltywpt/dataMarket",
        "详情页URL模板": "https://trade.fjbdex.com/ltywpt/data-market/detail?time={timestamp}&id={id}&isXxjssc={isXxjssc}",
        "打开方式": "同标签路由跳转",
        "占位参数": "id, time, isXxjssc",
        "卡片热区": ".item.item-hover",
        "详情页数据接口": "GET https://trade.fjbdex.com/ltywpt-api/api/data-portal-center/portal/catentry/queryById?id={id}&userId=&type={1|3}",
        "样例": "time=1790997234356&id=1780890734680420353&isXxjssc=false",
        "备注": "time 为点击时刻毫秒时间戳，可省略；isXxjssc 决定接口 type：false→1、true→3",
    },
    {
        "站点": "郑州数据交易中心",
        "站点代号": "zzbdex",
        "列表页": "https://market.zzbdex.com/trade/product",
        "详情页URL模板": "https://market.zzbdex.com/trade/product/{productType}/{id}",
        "打开方式": "同标签路由跳转",
        "占位参数": "productType, id",
        "卡片热区": ".product-item",
        "详情页数据接口": "GET https://market.zzbdex.com/data-deal-admin/frontDeskHomePage/frontPageProductDetail/{id}",
        "样例": "/trade/product/dataSet/2056990028951306240",
        "备注": "productType 是路径段：dataSet(365)/dataApi(156)/dataApp(45)/dataReport(1)",
    },
    {
        "站点": "北方大数据交易平台",
        "站点代号": "datadmz",
        "列表页": "https://exchange.datadmz.com:30101/datadmz/tradeFloor/list?removeSideBar=true",
        "详情页URL模板": "https://exchange.datadmz.com:30101/datadmz/tradeFloor/dataProductDetail/{productId}?removeSideBar=true",
        "打开方式": "同标签跳转，未登录被重定向到 /datadmz/login",
        "占位参数": "productId, removeSideBar",
        "卡片热区": ".product-card",
        "详情页数据接口": "登录后才可见",
        "样例": "dataProductDetail/8bf0c86cffbf4ed2b77672513bba34a7?removeSideBar=true",
        "备注": "列表点击直接跳登录页；URL 本身 HTTP 200 有效。路由模板取自 main.ebf52252.js",
    },
    {
        "站点": "海南省数据产品超市",
        "站点代号": "datadex",
        "列表页": "https://transaction.datadex.cn/app/dataMarket",
        "详情页URL模板": "https://transaction.datadex.cn/app/buyApi?id={proResourceId}",
        "打开方式": "新标签页",
        "占位参数": "id",
        "卡片热区": ".asset-list-item",
        "详情页数据接口": "POST https://transaction.datadex.cn/api/resource/showResourceInfo  body {\"resourceId\": proResourceId}",
        "样例": "id=2bc5242408284b5c8017da10884d5074",
        "备注": "所有资源类型统一走 /app/buyApi；用 proResourceId，不是 proResourceInfoId（常为空）",
    },
]

# 参数明细
PARAMS = [
    ("北京", "productId", "是", "e79998a79f7e1d49d9d23a6a91e80d43", "商品唯一标识", "列表 records[].uuid（32 位十六进制）"),
    ("上海", "id", "是", "6829", "商品登记 ID", "列表 records[].id（数字，与详情页接口 registerDetail/{id} 同源）"),
    ("上海", "type", "是", "1 / 2", "商品服务状态", "1=已登记，2=可交易；对应列表 serviceType 字段（已登记/可交易）。决定调哪个详情接口，填错会白页"),
    ("上海", "from", "否", "admin", "来源标识", "前端写死常量，实测不影响渲染与接口"),
    ("上海", "productType", "否", "2", "产品形态（未生效）", "前端写死常量；实测 1/2/3 页面与接口完全一致"),
    ("杭州", "productId", "是", "691330127MA28NJBQ8X3301HZ0139565", "商品业务编码", "列表 records[].productId（25 位），注意不是数字 id"),
    ("杭州", "from", "否", "%2Fdata-exchange", "来源路由", "encodeURIComponent 后的列表页路径，可省略"),
    ("广东", "id", "是", "8376", "商品自增 ID", "列表 ID 字段（数字）；不是 CPBH 产品编号，也不是 WBCPBH"),
    ("贵阳", "id", "是", "5504", "商品 ID", "列表 id 字段（数字），同时作为 serviceId 传给详情接口"),
    ("福建", "id", "是", "1780890734680420353", "商品 ID", "列表 id 字段（19 位雪花 ID）"),
    ("福建", "time", "否", "1790997234356", "点击时刻时间戳（毫秒）", "前端生成，用于绕缓存/埋点；省略后页面正常"),
    ("福建", "isXxjssc", "否", "false / true", "详情域标识", "false→详情接口 type=1，true→type=3；省略等同 false，页面渲染无差异"),
    ("郑州", "productType", "是", "dataSet / dataApi / dataApp / dataReport", "产品形态（路径段）", "列表 productType 字段；全站分布 dataSet 365、dataApi 156、dataApp 45、dataReport 1"),
    ("郑州", "id", "是", "2056990028951306240", "商品 ID", "列表 id 字段（19 位雪花 ID）"),
    ("北方", "productId", "是", "8bf0c86cffbf4ed2b77672513bba34a7", "商品 ID", "列表 productId 字段（32 位十六进制）"),
    ("北方", "removeSideBar", "否", "true", "隐藏侧边栏", "列表页同款参数，可省略（省略后带完整导航）"),
    ("海南", "id", "是", "2bc5242408284b5c8017da10884d5074", "资源 ID", "列表 proResourceId（32 位十六进制）；不是 proResourceInfoId"),
]


def write_csv(name: str, rows: list[dict], fields: list[str]) -> None:
    path = OUT / name
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"写入 {path}（{len(rows)} 行）")


def main() -> None:
    write_csv(
        "详情页跳转链接.csv",
        LINKS,
        [
            "站点",
            "站点代号",
            "列表页",
            "详情页URL模板",
            "打开方式",
            "占位参数",
            "卡片热区",
            "详情页数据接口",
            "样例",
            "备注",
        ],
    )
    write_csv(
        "详情链接参数明细.csv",
        [dict(zip(["站点", "参数名", "是否占位", "示例值", "含义", "取值来源/规则"], p)) for p in PARAMS],
        ["站点", "参数名", "是否占位", "示例值", "含义", "取值来源/规则"],
    )


if __name__ == "__main__":
    main()
