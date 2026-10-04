"""生成「应用 / 行业」筛选维度对照表与语义合并后的统一维度集合。

三个产物：
  dimensions/站点维度条目明细.csv   9 家交易所全部可选条目 + 传参 + 行字段
  dimensions/统一维度集合.csv        35 个语义合并后的无重复条目 + 各站原始写法
  （配合 dimensions/README.md 阅读）

数据来源全部为 2026-10-03 实测：浏览器点击抓包取到真实请求体，
再用接口回测校验（当次过滤条数与页面计数逐项吻合）。
"""

from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 站点元数据
# key: 站点简称
META = {
    "北京": dict(
        site="bjidex", page="https://mall.bjidex.com/transaction-management/data-mall",
        dim="应用领域", dict_api="POST https://api.bjidex.com/iam/api/dict/data/findDicByCode  body={'dictCode':'product_field'}",
        list_api="POST https://api.bjidex.com/product/api/productIndex/getProductList",
        field="goodsArea", value_type="数组[str]，取字典 dictValue",
        row_field="（列表不回显）", row_sample="—",
        note="另有一组「应用行业」用 goodsIndustry（国标门类码 0~19），与本维度不同；"
             "列表里的 goodsApplyScene 是自由标签词（实测 1846 种），不是应用领域字典",
    ),
    "杭州": dict(
        site="hzdex", page="https://mall.hzdex.cn/data-exchange",
        dim="应用领域", dict_api="（无公开字典接口，前端硬编码；由商品 applicationFields/applicationFieldsCn 反推）",
        list_api="GET https://mall.hzdex.cn/api/uniformItem/mall/search",
        field="applicationFields", value_type="字符串，两位数字 01~16",
        row_field="applicationFields / applicationFieldsCn", row_sample='["03"] / ["医疗"]',
        note="逗号分隔多值时前端显示为多个值；单值过滤，多值需多次请求",
    ),
    "上海": dict(
        site="chinadep", page="https://nidts.chinadep.com/trading-market/product",
        dim="应用场景", dict_api="GET https://nidts.chinadep.com/dex-api/dex-es/query/all/stat  → data.sector",
        list_api="POST https://nidts.chinadep.com/dex-api/dex-es/query/all/search",
        field="sectorName", value_type="字符串，中文标签本身",
        row_field="sectorName", row_sample='["其他"]',
        note="页面 UI 显示的条数（如金融服务 4489）与 API 回测完全一致",
    ),
    "郑州": dict(
        site="zzbdex", page="https://market.zzbdex.com/trade/product",
        dim="应用场景", dict_api="GET https://market.zzbdex.com/data-deal-admin/bmpApi/dictApiInfoByDictType?dictType=scene_code",
        list_api="POST https://market.zzbdex.com/data-deal-admin/frontDeskHomePage/frontPageProduct",
        field="sceneCode", value_type="字典 id（整数），不是 dictValue",
        row_field="sceneName（sceneCode 恒为 null）", row_sample='"文旅,教育,综合,信用,政务,时空,交通,住建,金融,制造,三农"',
        note="坑点：传 dictValue（如 '01'）返回 0 条，必须传 dict.id（如 197）",
    ),
    "广东": dict(
        site="cantonde", page="https://www.cantonde.com/sjjy.html#/list",
        dim="行业分类", dict_api="POST https://www.cantonde.com/si/sjjy/sjscDicts  → data.YYCJDict",
        list_api="POST https://www.cantonde.com/si/sjjy/list",
        field="YYCJ", value_type="字符串，取字典 value（100/1~25/99）",
        row_field="YYCJ / YYCJMC", row_sample='"1;5;24;11" （分号分隔的代码串）',
        note="接口字典 27 项，页面首屏展开列出 20 项；余下 7 项同样可用且与商品卡标签一致",
    ),
    "海南": dict(
        site="datadex", page="https://transaction.datadex.cn/app/dataMarket",
        dim="行业分类", dict_api="GET https://transaction.datadex.cn/api/resource/procommontags/searchBy?tagFidCode=industryType",
        list_api="POST https://transaction.datadex.cn/api/resource/searchBy",
        field="industry", value_type="字符串，标签 id（32 位十六进制）",
        row_field="proIndustryType", row_sample="列表返回恒为空值",
        note="另有「场景分类」「所属领域」两组独立标签（tagFidCode = scene / productDomain）",
    ),
    "贵阳": dict(
        site="gzdex", page="https://www.gzdex.com.cn/market/",
        dim="使用场景", dict_api="（无独立字典接口，前端静态；id 由逐个点击实在渲面的筛选项取得）",
        list_api="GET https://www.gzdex.com.cn/apaas/serviceapp/v3/servicemarket/dataShop/list",
        field="dataDomains", value_type="字符串，整数 id 491~510",
        row_field="sectors_name（sectors 恒为 0）", row_sample='"水利、环境和公共设施管理业,农、林、牧、渔业,交通运输、仓储和邮政业"',
        note="参数是复数 dataDomains，写成单数 dataDomain 会被静默忽略（返回全量 2018 条）",
    ),
    "福建": dict(
        site="fjbdex", page="https://trade.fjbdex.com/ltywpt/dataMarket",
        dim="所属行业", dict_api="GET https://trade.fjbdex.com/ltywpt-api/api/jeecg-system/sys/dict/getDictItems/industry_involved",
        list_api="GET https://trade.fjbdex.com/ltywpt-api/api/data-portal-center/portal/catentry/list",
        field="industryInvolved", value_type="字符串，字典 value（32 位十六进制）",
        row_field="（列表不回显）", row_sample="仅返回 category/attribute/themeId，与行业无关",
        note="筛选确实生效（如教育 → 7 条），但列表接口不回显行业字段",
    ),
    "北方": dict(
        site="datadmz", page="https://exchange.datadmz.com:30101/datadmz/tradeFloor/list",
        dim="应用行业", dict_api="GET https://exchange.datadmz.com:30101/api/product/sysIndustry/list",
        list_api="POST https://exchange.datadmz.com:30101/api/product/dataMarket/selectProductList",
        field="useIndustry", value_type="数组[str]，取字典 id（A01~A28）",
        row_field="useIndustry / useIndustryName", row_sample='"A03" / "能源"',
        note="只认 id，传中文名返回空；另有 useScene/useSceneStr 表示使用场景",
    ),
}

# ------------------------------------------------------- 条目：(值, 名称, 归一)
BJ = [  # 北京 应用领域 dictCode=product_field
    ("0", "工业", "制造业与工业"), ("1", "政务", "政务与城市治理"), ("2", "医疗", "医疗健康"),
    ("3", "能源", "能源电力"), ("4", "金融", "金融业"), ("5", "交通", "交通运输、仓储与物流"),
    ("6", "文旅", "文化旅游与文体娱乐"), ("7", "司法", "司法与法律服务"), ("8", "跨境", "跨境与外贸"),
    ("9", "电子商务", "批发零售与电子商务"), ("10", "智能服务", "人工智能与智能服务"),
    ("11", "互联网/IT/电子/通信", "信息传输、软件与通信"), ("12", "教育", "教育"),
    ("13", "交通/物流/贸易/零售", "交通运输、仓储与物流"), ("14", "学术科研", "科学研究与技术服务业"),
    ("15", "房地产", "房地产业"), ("16", "汽车", "汽车"), ("17", "医疗卫生", "医疗健康"),
    ("18", "广告/传媒/文化/体育", "文化旅游与文体娱乐"), ("19", "能源化工", "能源电力"),
    ("20", "政府/公共事业", "政务与城市治理"), ("21", "住宿/餐饮", "住宿和餐饮业"),
    ("22", "建筑/房产", "建筑业"), ("23", "采矿", "采矿业"), ("24", "交通/物流", "交通运输、仓储与物流"),
    ("25", "贸易/零售", "批发零售与电子商务"), ("26", "工业制造", "制造业与工业"),
    ("27", "农/林/牧/渔", "农林牧渔"), ("28", "水力/电力/热力/燃气", "能源电力"),
    ("29", "租赁/商务", "租赁和商务服务业"), ("30", "居民服务", "居民服务与生活服务业"),
]

HZ = [  # 杭州 应用领域（无字典接口，01~16）
    ("01", "政府/公共", "政务与城市治理"), ("02", "AI", "人工智能与智能服务"),
    ("03", "医疗", "医疗健康"), ("04", "信用", "信用服务"), ("05", "金融", "金融业"),
    ("06", "商业", "批发零售与电子商务"), ("07", "交通", "交通运输、仓储与物流"),
    ("08", "教育", "教育"), ("09", "农业", "农林牧渔"), ("10", "环保", "生态环保与绿色低碳"),
    ("11", "统计", "统计与社会统计"), ("12", "气象", "气象服务"), ("13", "监管", "政务与城市治理"),
    ("14", "科创", "科学研究与技术服务业"), ("15", "通讯", "信息传输、软件与通信"),
    ("16", "其他", "其他与综合"),
]

SH = [  # 上海 应用场景（data.sector）
    ("应急管理", "应急管理", "应急管理与公共安全"), ("工业制造", "工业制造", "制造业与工业"),
    ("金融服务", "金融服务", "金融业"), ("品牌营销", "品牌营销", "新闻传媒与市场营销"),
    ("城市治理", "城市治理", "政务与城市治理"), ("商贸流通", "商贸流通", "批发零售与电子商务"),
    ("文化旅游", "文化旅游", "文化旅游与文体娱乐"), ("其他", "其他", "其他与综合"),
    ("教育服务", "教育服务", "教育"), ("娱乐体育", "娱乐体育", "文化旅游与文体娱乐"),
    ("绿色低碳", "绿色低碳", "生态环保与绿色低碳"), ("交通运输", "交通运输", "交通运输、仓储与物流"),
    ("医疗健康", "医疗健康", "医疗健康"), ("科技创新", "科技创新", "科学研究与技术服务业"),
    ("现代农业", "现代农业", "农林牧渔"), ("气象服务", "气象服务", "气象服务"),
]

ZZ = [  # 郑州 应用场景（dictType=scene_code，取 id）
    ("195", "三农", "农林牧渔"), ("196", "制造", "制造业与工业"), ("197", "金融", "金融业"),
    ("198", "住建", "建筑业"), ("199", "交通", "交通运输、仓储与物流"),
    ("200", "文旅", "文化旅游与文体娱乐"), ("201", "时空", "地理空间与遥感"),
    ("202", "政务", "政务与城市治理"), ("203", "零售", "批发零售与电子商务"),
    ("204", "医疗", "医疗健康"), ("2243", "通信", "信息传输、软件与通信"),
    ("2244", "能源", "能源电力"), ("2245", "环保", "生态环保与绿色低碳"),
    ("2246", "信用", "信用服务"), ("2247", "企服", "租赁和商务服务业"),
    ("2248", "综合", "其他与综合"), ("2257", "教育", "教育"),
]

GD = [  # 广东 行业分类（YYCJDict）
    ("100", "全场景", "全场景/不限"), ("1", "交通运输", "交通运输、仓储与物流"),
    ("2", "烟草", "烟草"), ("3", "智慧金融", "金融业"), ("4", "智能建筑", "建筑业"),
    ("5", "安全服务", "应急管理与公共安全"), ("6", "公共服务", "政务与城市治理"),
    ("7", "法律服务", "司法与法律服务"), ("8", "通信运营商", "信息传输、软件与通信"),
    ("9", "医疗健康", "医疗健康"), ("10", "知识产权", "知识产权"),
    ("11", "智慧城市", "政务与城市治理"), ("12", "新闻传媒", "新闻传媒与市场营销"),
    ("13", "智能制造", "制造业与工业"), ("14", "新零售", "批发零售与电子商务"),
    ("15", "陶瓷", "陶瓷"), ("16", "能源电力", "能源电力"),
    ("17", "绿色低碳", "生态环保与绿色低碳"), ("18", "地理遥感", "地理空间与遥感"),
    ("19", "汽车", "汽车"), ("20", "咨询服务", "租赁和商务服务业"),
    ("21", "培训教育", "教育"), ("22", "农林牧渔", "农林牧渔"),
    ("23", "文化旅游", "文化旅游与文体娱乐"), ("24", "气象服务", "气象服务"),
    ("25", "人工智能", "人工智能与智能服务"), ("99", "其他", "其他与综合"),
]

HI = [  # 海南 行业分类（tagFidCode=industryType）
    ("4f70e3bff987eed986df4dd941e0bbaf", "农、林、牧、渔业", "农林牧渔"),
    ("6c81ec3b0911506fa3c2540dfdf4c795", "采矿业", "采矿业"),
    ("872c9287c6d47d1e777200b3bde9d19a", "制造业", "制造业与工业"),
    ("ed3e750a82336caf79f506c7210c40fc", "电力、热力、燃气及水生产和供应业", "能源电力"),
    ("1fea75deac97b01671e54a71c1477951", "建筑业", "建筑业"),
    ("d25d160e738d832cb52448beb30ce585", "交通运输、仓储和邮政业", "交通运输、仓储与物流"),
    ("6da5a33a959f67b6d33a7256126cba8f", "信息传输、软件和信息技术服务业", "信息传输、软件与通信"),
    ("5de2731f3f111b7969e4d22f91b11561", "批发和零售业", "批发零售与电子商务"),
    ("d7a2b682cb974778e2a7a2bb211b0c29", "住宿和餐饮业", "住宿和餐饮业"),
    ("57d5e08e8e5e6d7dc09aa5b478f7aa5c", "金融业", "金融业"),
    ("adbfd2943ddedf4ffdee6abe610825fd", "房地产业", "房地产业"),
    ("fd2f53323aa809b1531458322d220fa4", "租赁和商务服务业", "租赁和商务服务业"),
    ("8575bdc6ef45c49e3475badb5346a81d", "科学研究和技术服务业", "科学研究与技术服务业"),
    ("c7eb10447dec90ff6212d91801173967", "水利、环境和公共设施管理业", "生态环保与绿色低碳"),
    ("be8896468595c7eeadf4aa382a6249c3", "居民服务、修理和其他服务业", "居民服务与生活服务业"),
    ("951d360695f48281874c5c9bff141081", "教育", "教育"),
    ("6f4b340c869f5397d7b7450092d33a46", "卫生和社会工作", "医疗健康"),
    ("614f12fea396b601dd4966e6c960bb90", "文化、体育和娱乐业", "文化旅游与文体娱乐"),
    ("8c30bb9bdfdb567c42fa52550ad90504", "公共管理、社会保障和社会组织", "政务与城市治理"),
    ("743f2ae7f2a0cfab200e2655d38ed7ea", "国际组织", "国际组织"),
]

GB20 = [  # 国标 20 门类（贵阳 id 491~510，福建为 18 项子集 +「其他」）
    # 顺序必须严格按国标门类 A→T：贵阳的 id 是 491+i 直接派生的，
    # 顺序排错会让整段编码与名称错位。2026-10-03 用 dataDomains 逐个筛选、
    # 取结果集 sectors_name 交集反推校验过（原先把「批发和零售业」排到了
    # 「交通运输」之后，导致 496~499 全部错位，已修正）。
    ("农、林、牧、渔业", "农林牧渔"), ("采矿业", "采矿业"), ("制造业", "制造业与工业"),
    ("电力、热力、燃气及水生产和供应业", "能源电力"), ("建筑业", "建筑业"),
    ("批发和零售业", "批发零售与电子商务"),
    ("交通运输、仓储和邮政业", "交通运输、仓储与物流"),
    ("住宿和餐饮业", "住宿和餐饮业"),
    ("信息传输、软件和信息技术服务业", "信息传输、软件与通信"),
    ("金融业", "金融业"), ("房地产业", "房地产业"), ("租赁和商务服务业", "租赁和商务服务业"),
    ("科学研究和技术服务业", "科学研究与技术服务业"),
    ("水利、环境和公共设施管理业", "生态环保与绿色低碳"),
    ("居民服务、修理和其他服务业", "居民服务与生活服务业"), ("教育", "教育"),
    ("卫生和社会工作", "医疗健康"), ("文化、体育和娱乐业", "文化旅游与文体娱乐"),
    ("公共管理、社会保障和社会组织", "政务与城市治理"), ("国际组织", "国际组织"),
]

# 贵阳除国标 20 门类外还挂着 4 个自定义场景标签。它们的 id 不在 491~510 段里，
# 是扫描 dataDomains 全量编号（1~600）后才定位到的，商品数很少（2~5 条）但确实可筛选。
GY_EXTRA = [
    ("4", "科技创新", "科学研究与技术服务业"),
    ("26", "智慧城市", "政务与城市治理"),
    ("28", "生活服务", "居民服务与生活服务业"),
    ("338", "其他场景", "其他与综合"),
]
GY = GY_EXTRA + [(str(491 + i), n, c) for i, (n, c) in enumerate(GB20)]  # 贵阳 使用场景

FJ = [  # 福建 所属行业
    ("22ce692367aa4f11b331675a0d069697", "电力、热力、燃气及水生产和供应业", "能源电力"),
    ("74c5130ad6b1494799600151a0763553", "水利、环境和公共设施管理业", "生态环保与绿色低碳"),
    ("a1c35ee7645747cb8e701b7eacc1b9d5", "教育", "教育"),
    ("27cc2652dcb845f7925368a773266c32", "卫生和社会工作", "医疗健康"),
    ("9046d122b2b74f69ab961db41d561517", "其他", "其他与综合"),
    ("4fc6abd83a7c484aa78a377d5f3a1075", "制造业", "制造业与工业"),
    ("1abaacb59d2445f29f548c8a017ae6b4", "文化、体育和娱乐业", "文化旅游与文体娱乐"),
    ("138306c78f624fe5baf013819c3ccbc8", "交通运输、仓储和邮政业", "交通运输、仓储与物流"),
    ("5b1b3af8977742a9ac5f5b5399cd47de", "建筑业", "建筑业"),
    ("9ae9180b8c1c48359fdf3d6237726e43", "信息传输、软件和信息技术服务业", "信息传输、软件与通信"),
    ("23b0ac091a374152b098a557b64ce3ae", "科学研究和技术服务业", "科学研究与技术服务业"),
    ("c4098a5616c94b2d97cd1a7600b0f4e6", "批发和零售业", "批发零售与电子商务"),
    ("e11d30bc59404b238571849b0d53f906", "房地产业", "房地产业"),
    ("bed80cc07f6b4dff959bbc1e8a68f126", "金融业", "金融业"),
    ("8f3325f6e80943c4bbc6b4f963c0a464", "公共管理、社会保障和社会组织", "政务与城市治理"),
    ("11017935448d4ed5aa7d61fe677cd688", "农、林、牧、渔业", "农林牧渔"),
    ("85fb3760e5a04122b46418d56c07bff1", "租赁和商务服务业", "租赁和商务服务业"),
    ("8a53a767da8c426eae52261f1dd4495f", "采矿业", "采矿业"),
]

BF = [  # 北方 应用行业
    ("A01", "农业", "农林牧渔"), ("A02", "制造业", "制造业与工业"), ("A03", "能源", "能源电力"),
    ("A04", "交通", "交通运输、仓储与物流"), ("A05", "物流", "交通运输、仓储与物流"),
    ("A06", "旅游", "文化旅游与文体娱乐"), ("A11", "金融", "金融业"), ("A12", "房地产", "房地产业"),
    ("A13", "建筑", "建筑业"), ("A14", "生活服务", "居民服务与生活服务业"),
    ("A15", "电商", "批发零售与电子商务"), ("A16", "生态环保", "生态环保与绿色低碳"),
    ("A17", "科研教育", "科学研究与技术服务业"), ("A18", "医疗健康", "医疗健康"),
    ("A19", "舆情", "新闻传媒与市场营销"), ("A20", "政务", "政务与城市治理"),
    ("A21", "地理空间", "地理空间与遥感"), ("A22", "社会统计", "统计与社会统计"),
    ("A23", "外贸", "跨境与外贸"), ("A24", "信用", "信用服务"), ("A25", "司法", "司法与法律服务"),
    ("A26", "通信", "信息传输、软件与通信"), ("A27", "咨询", "租赁和商务服务业"),
    ("A28", "企业", "租赁和商务服务业"),
]

DATA = [("北京", BJ), ("杭州", HZ), ("上海", SH), ("郑州", ZZ), ("广东", GD),
        ("海南", HI), ("贵阳", GY), ("福建", FJ), ("北方", BF)]

HEADER = ["交易所", "站点标识", "页面维度名", "条目名称", "筛选接口字段名", "传入字段值",
          "列表接口的字段", "列表返回样例", "语义归并", "备注"]


def build_detail():
    rows = []
    for site, items in DATA:
        m = META[site]
        for val, name, canon in items:
            rows.append([site, m["site"], m["dim"], name, m["field"], val,
                         m["row_field"], m["row_sample"], canon, ""])
        rows[-1][-1] = m["note"]  # 备注只在每组最后一行写一次，避免 CSV 冗余
    return rows


def build_unified(rows):
    order, agg = [], {}
    for r in rows:
        c = r[8]
        if c not in agg:
            agg[c] = {"sites": [], "items": []}
            order.append(c)
        agg[c]["sites"].append(r[0])
        agg[c]["items"].append(f"{r[0]}·{r[3]}")
    out = []
    for c in order:
        a = agg[c]
        sites = sorted(set(a["sites"]))
        out.append([c, len(sites), "、".join(sites), len(a["items"]), "；".join(a["items"])])
    return out


def write_csv(path, header, rows):
    """写 CSV；文件被 Excel 占用时改写到 _new 副本，别让算出来的结果白跑。"""
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        return path
    except PermissionError:
        alt = path.with_name(path.stem + "_new.csv")
        with alt.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"[warn] {path.name} 被占用（可能正用 Excel 打开），已改写到 {alt.name}")
        print("       关闭后重跑本脚本即可写回原文件")
        return alt


def main():
    detail = build_detail()
    unified = build_unified(detail)

    p1 = write_csv(
        OUT / "站点维度条目明细.csv",
        HEADER,
        detail,
    )
    p2 = write_csv(
        OUT / "统一维度集合.csv",
        ["统一维度", "覆盖站点数", "覆盖站点", "原始条目数", "各站点原始写法"],
        unified,
    )

    print(f"条目明细 {len(detail)} 行 → {p1}")
    print(f"统一维度 {len(unified)} 项 → {p2}")
    print()
    print(f"{'统一维度':<22}{'站数':>4}  原始条目")
    for r in unified:
        print(f"{r[0]:<22}{r[1]:>4}  {r[3]}")


if __name__ == "__main__":
    main()
