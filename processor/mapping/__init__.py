"""mapping 汇总入口。

分文件是为了维护方便，对外仍然是一整个命名空间 ——
原来写的 `from processor.mapping import MARKET_ID, DIMS_NAME` 不用改。

分三个文件的理由：
    market.py    字典表，配好基本不动
    category.py  同样是字典表（35 项统一维度 + 一张全站共享的标签名 → 维度字典）
    product.py   9 站 × 20 个目标字段 = 180+ 条 ETL 规则，要反复对着 CSV 改

product.py 的变更频率比另外两个高一个数量级，混在一起会导致
改一处商品映射时要在 800 行文件里翻字典表。
"""

from .market import (
    MARKET_ID,
    MARKET_NAME,
    MARKET_SHORTNAME,
    MARKET_SITE,
    MARKET_SITE_REVERSE,
    MARKET_TABLE_COLUMNS_VALUE,
    source_csv_path,
)
from .category import (
    DIMS_ID,
    DIMS_NAME,
    LABEL2DIM,
    MULTI,
    dim_labels,
    labels_to_dims,
)
from .product import (
    CATEGORY_FALLBACK,
    CATEGORY_SOURCES,
    DETAIL_URL_FILLERS,
    DETAIL_URL_TPL,
    PRODUCT_COLUMNS,
    PRODUCT_MAP,
    SOURCE_KEY,
    build_detail_url,
    build_source_key,
    consumed_source_columns,
    resolve_category,
    split_by_map,
)

__all__ = [
    # market
    "MARKET_ID",
    "MARKET_SITE",
    "MARKET_SITE_REVERSE",
    "MARKET_NAME",
    "MARKET_SHORTNAME",
    "MARKET_TABLE_COLUMNS_VALUE",
    "source_csv_path",
    # category
    "DIMS_ID",
    "DIMS_NAME",
    "LABEL2DIM",
    "MULTI",
    "labels_to_dims",
    "dim_labels",
    # product
    "SOURCE_KEY",
    "PRODUCT_MAP",
    "PRODUCT_COLUMNS",
    "CATEGORY_SOURCES",
    "DETAIL_URL_TPL",
    "DETAIL_URL_FILLERS",
    "CATEGORY_FALLBACK",
    "build_source_key",
    "build_detail_url",
    "resolve_category",
    "split_by_map",
    "consumed_source_columns",
    # 自检
    "check",
]


def check() -> list[str]:
    """配置一致性自检。返回问题描述列表，空列表表示没问题。

    建议在每一批处理任务启动时跑一次 —— 这类配置错了不会报错，
    只会悄悄产出缺失/NULL 的数据，等到发现往往已经入库了。
    """
    problems: list[str] = []

    # 各映射表覆盖所有交易所
    for name, table in (
        ("MARKET_SITE", MARKET_SITE),
        ("MARKET_NAME", MARKET_NAME),
        ("MARKET_SHORTNAME", MARKET_SHORTNAME),
        ("CATEGORY_SOURCES", CATEGORY_SOURCES),
        ("SOURCE_KEY", SOURCE_KEY),
        ("PRODUCT_MAP", PRODUCT_MAP),
    ):
        missing = [m for m in MARKET_ID if m not in table]
        if missing:
            problems.append(f"{name} 缺少交易所: {missing}")

    # 统一维度 id 和 name 必须一一对应
    if set(DIMS_ID) != set(DIMS_NAME):
        only_id = set(DIMS_ID) - set(DIMS_NAME)
        only_name = set(DIMS_NAME) - set(DIMS_ID)
        problems.append(f"DIMS_ID / DIMS_NAME 不一致: 仅 ID 有 {only_id}, 仅 NAME 有 {only_name}")

    # 标签名 → 维度，目标必须是已定义的统一维度
    bad = {l: d for l, d in LABEL2DIM.items() if d not in DIMS_NAME}
    if bad:
        problems.append(f"LABEL2DIM 指向未定义的维度: {bad}")

    # 统一维度至少要有标签用到，否则是冗余条目
    unused = [d for d in DIMS_ID if d not in set(LABEL2DIM.values())]
    if unused:
        problems.append(f"以下统一维度没有任何标签映射到: {unused}")

    return problems
