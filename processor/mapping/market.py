"""交易所（market 表）映射配置。

这里放的是**字典表**性质的配置：配好之后基本不会再动。
对应数据库 market 表。

约定：所有映射的 key 统一用 `market_id`（英文短名，如 "beijing"），
不用站点域名短名（如 "bjidex"）。两者通过 MARKET_SITE 转换。
"""

# market 表的 market_id，也是整个 processor 模块的主索引
MARKET_ID = [
    "beifang",
    "beijing",
    "fujian",
    "guangdong",
    "guiyang",
    "hainan",
    "hangzhou",
    "shanghai",
    "zhengzhou",
]

# market_id → 站点短名。
# 采集侧的数据文件命名是 data/<site>_products.csv，靠这个映射找到对应文件。
MARKET_SITE = {
    "beifang": "datadmz",
    "beijing": "bjidex",
    "fujian": "fjbdex",
    "guangdong": "cantonde",
    "guiyang": "gzdex",
    "hainan": "datadex",
    "hangzhou": "hzdex",
    "shanghai": "chinadep",
    "zhengzhou": "zzbdex",
}

# 站点短名 → market_id，反查用（从 CSV 文件名回到 market_id）
MARKET_SITE_REVERSE = {v: k for k, v in MARKET_SITE.items()}

MARKET_NAME = {
    "beifang": "北方大数据交易平台",
    "beijing": "北京大数据交易所",
    "fujian": "福建大数据交易平台",
    "guangdong": "广东数据交易所",
    "guiyang": "贵阳大数据交易所",
    "hainan": "海南省数据产品超市",
    "hangzhou": "杭州数据交易所",
    "shanghai": "上海数据交易所",
    "zhengzhou": "郑州数据交易中心",
}

MARKET_SHORTNAME = {
    "beifang": "北方",
    "beijing": "北京",
    "fujian": "福建",
    "guangdong": "广东",
    "guiyang": "贵阳",
    "hainan": "海南",
    "hangzhou": "杭州",
    "shanghai": "上海",
    "zhengzhou": "郑州",
}

# market 表字段 → 取值来源（按 market_id 索引的 dict）。
# 生成插入数据时按列取 MARKET_TABLE_COLUMNS_VALUE[col][market_id] 即可。
MARKET_TABLE_COLUMNS_VALUE = {
    "market_id": MARKET_ID,
    "name": MARKET_NAME,
    "short_name": MARKET_SHORTNAME,
}


def source_csv_path(market_id: str) -> str:
    """market_id → 该站的采集结果 CSV 路径（相对项目根）。"""
    return f"data/{MARKET_SITE[market_id]}_products.csv"
