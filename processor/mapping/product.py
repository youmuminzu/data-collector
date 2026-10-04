"""商品（product 表）字段映射配置。

对应表结构：
    CREATE TABLE product (
        product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_data_key  TEXT,   -- 交易所网站里的商品主键
        title         TEXT,   -- 名称/标题
        description   TEXT,   -- 描述
        tags          TEXT,   -- 归并后的统一维度名，多个用 || 隔开
        market_id     TEXT,   -- 所属交易所
        category_id   TEXT,   -- 统一维度 id，多个用 || 隔开；无值归为 others
        source        TEXT,   -- 数源机构
        detail_url    TEXT    -- 详情页地址
    );

⚠️ tags 存的是**统一维度的中文名**（35 项归并结果），不是各站原始标签文案。
缘故站点标签粒度参差（"AI"/"人工智能"、"交通"/"交通运输"），直接入库既读不懂、
也没法做跨站筛选。现在 tags 与 category_id 同源、一一对应，tags 只是给人看的那一列。

映射方向：**目标字段 → (源字段, 转换函数)**。
product 表只有 8 个目标字段，而 9 站源字段合计 319 个，
按目标字段组织更紧凑，也和「源 > 目标」的分析顺序一致。

规模参考（2026-10-03 实况）：9 站 CSV 合计 **319 个字段，共有列名 0 个**——
连一个同名列都没有，只能一家一家配：

  站点         列数    行数
  chinadep      12    8681   ← 最窄
  fjbdex        22    1265
  bjidex        25    2825
  datadmz       27    1189
  hzdex         28    3197
  zzbdex        29     567
  cantonde      45   20000
  gzdex         50    2018
  datadex       81    2832   ← 最宽
"""

import re
from typing import NamedTuple

from processor.transforms import clean_text

from .category import MULTI, dim_labels, labels_to_dims

# ------------------------------------------------------------------ 主键

# 各站能唯一确定一条商品的源字段。
# 与采集侧 collector/sites/*.py 的 key_fields **必须保持一致**，改一边要同步另一边。
#
# 上海为什么是两个字段：后端是「登记库」和「交易库」两套独立自增 id，会撞号
# （实测 828 组 id 撞号），只有加上 serviceType 才能唯一定位。
# 曾踩过的坑：早先用 (商品名, 供应商, 发布时间) 组合键，把两条同名同供方同时间的
# 「电梯产业链结构文本训练数据」误合并成一条，丢了数据。
SOURCE_KEY = {
    "beifang": ("productId",),
    "beijing": ("uuid",),
    "fujian": ("id",),
    "guangdong": ("ID",),          # 大写 ID，不是产品编号 CPBH
    "guiyang": ("id",),
    "hainan": ("proResourceId",),  # 不是 proResourceInfoId（后者常为空）
    "hangzhou": ("productId",),    # 不是自增 id
    "shanghai": ("id", "serviceType"),   # ← 唯一一个组合主键
    "zhengzhou": ("id",),
}


def build_source_key(row: dict, market_id: str, sep: str = "::") -> str | None:
    """按 SOURCE_KEY 拼出 raw_data_key。

    单字段站直接返回该列的值；上海这类组合键用 sep 拼接。
    任一组成字段为空则返回 None —— 主键残缺的记录不能入库，必须单独捞出来看。
    """
    values = []
    for col in SOURCE_KEY.get(market_id, ()):
        v = clean_text(row.get(col))
        if not v:
            return None
        values.append(v)
    return sep.join(values) if values else None


# ------------------------------------------------------------ 详情页 URL

# 占位符直接写源列名，填充时用 str.format(**row)。
# 来自 detail_links/详情页跳转链接.csv（实机点击捕获，非推测）。
DETAIL_URL_TPL = {
    "beifang": (
        "https://exchange.datadmz.com:30101/datadmz/tradeFloor/"
        "dataProductDetail/{productId}?removeSideBar=true"
    ),
    "beijing": (
        "https://mall.bjidex.com/transaction-management/"
        "data-product-details?productId={uuid}"
    ),
    "fujian": (
        "https://trade.fjbdex.com/ltywpt-api/api/data-portal-center/"
        "portal/catentry/queryById?id={id}&userId=&type={type}"
    ),
    "guangdong": "https://www.cantonde.com/sjjy.html#/detail?id={ID}",
    "guiyang": "https://www.gzdex.com.cn/market/detail/{id}",
    "hainan": "https://transaction.datadex.cn/app/buyApi?id={proResourceId}",
    "hangzhou": "https://mall.hzdex.cn/data-exchange/{productId}?from=%2Fdata-exchange",
    "shanghai": (
        "https://nidts.chinadep.com/trading-market/product/detail"
        "?id={id}&type={url_type}&from=admin&productType=2"
    ),
    "zhengzhou": "https://market.zzbdex.com/trade/product/{productType}/{id}",
}

# 模板里不是源列的派生占位符。
# 上海 type 决定走哪个详情接口：1=已登记 → registerDetail，2=可交易 → home/detail。
# 填错会白页，必须和 serviceType 对应。
DETAIL_URL_FILLERS = {
    "shanghai": {
        "url_type": lambda r: {"已登记": "1", "可交易": "2"}.get(
            (r.get("serviceType") or "").strip(), "1"
        )
    },
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def build_detail_url(market_id: str, row: dict) -> str | None:
    """生成详情页 URL。任一占位符对应的源字段为空则返回 None，不产出半截 URL。"""
    tpl = DETAIL_URL_TPL.get(market_id)
    if not tpl:
        return None
    ctx = {k: ("" if v is None else str(v)) for k, v in row.items()}
    for key, fn in DETAIL_URL_FILLERS.get(market_id, {}).items():
        ctx[key] = str(fn(row) or "")
    # 关键占位符缺失就别造坏链接（福建的 userId 是设计上空着，不参与校验）
    for name in _PLACEHOLDER.findall(tpl):
        if not ctx.get(name, "").strip():
            return None
    try:
        return tpl.format(**ctx)
    except KeyError:
        return None


# -------------------------------------------------------- 分类维度翻译

# 各站「分类标签文案」的来源列，按优先级排列。
#
# 取哪一列：**优先用站点自己的行业/领域/场景分类**，而不是TAG/自定义标签列 ——
# 后者是商品自己打的关键词（如 aiTag、tagsStr），粒度不一、同义词泛滥，
# 不适合做统一筛选项。
#
# 为什么不再按站配一套「源列 + code 列」：
#   原先 category_id 取自 code 列（如 goods_area_code / industry_involved_code / scene_code），
#   其中郑州、贵阳根本没有 code，得先「名称→反查 code→再映射」，绕一大圈。
#   现在直接按标签文案查共享字典 LABEL2DIM，源列少一半，也和 tags 共用同一个来源。
#
# 分隔符（实测得出，别凭直觉改）：
#   "|"  北京 / 福建 / 海南  —— 采集侧按维度筛选生成的多值列
#   ","  北方 / 贵阳 / 郑州  —— 列表接口原生回显
#   "、" 杭州 / 上海
#   " "  广东  ← 容易漏：YYCJMC 是**空格**分隔（"公共服务 新零售"），不是分号也不是竖线
#
# ⚠️ 顿号歧义：国标行业名（"信息传输、软件和信息技术服务业"）自带顿号，
#    但杭州/上海用它做分隔符。按 "|" 走的福建、海南不受影响 —— 这也是为什么要逐站实测。
CATEGORY_SOURCES: dict[str, list[tuple[str, str]]] = {
    "beifang":   [("useIndustryName", ",")],
    "beijing":   [("goods_area", "|")],
    "fujian":    [("industry_involved", "|")],
    "guangdong": [("YYCJMC", " ")],
    "guiyang":   [("sectors_name", ",")],
    "hainan":    [("industry", "|")],
    # 杭州主列有 47% 为空，industry（国标行业名，斜杠分隔）非空且 100% 可兜住，
    # 实测能把 others 从 47.1% 降到 0%。取舍不了就删掉第二项，直接归 others。
    "hangzhou":  [("applicationFieldsCn", "、"), ("industry", "/")],
    "shanghai":  [("sectorName", "、")],
    "zhengzhou": [("sceneName", ",")],
}

# 无分类时归入的统一维度 id（表要求 category_id NOT NULL）
CATEGORY_FALLBACK = "others"


class CategoryResult(NamedTuple):
    """一类商品解析出的分类结果。

    ids        统一维度 id，|| 连接
    tags       对应统一维度中文名，|| 连接（product 表 tags 字段的值）
    unknown    字典里没有的自由文案，交给上层统计
    is_fallback True = 一个维度都没翻出来，被兜底成 others；
                 False = 站点确实给了分类（可能它自己就归类为「其他」）

    为什么要区分 is_fallback：两者最终 category_id 都是 others，但成因完全不同 ——
    前者是数据缺口需要修复，后者是站点的真实分类，混在一起会看不出该改什么。
    """

    ids: str
    tags: str
    unknown: list[str]
    is_fallback: bool


def resolve_category(row: dict, market_id: str) -> CategoryResult:
    """一行数据 → CategoryResult。

    tags 与 category_id 同源，一次算完：tags 存统一维度中文名（不再搬运站点原始
    标签文案），category_id 存对应 id。多个来源列时取第一个能翻出维度的列。
    """
    tried_unknown: list[str] = []
    for col, sep in CATEGORY_SOURCES.get(market_id, []):
        dims, unknown = labels_to_dims(row.get(col), sep)
        tried_unknown.extend(unknown)
        if dims:
            return CategoryResult(
                MULTI.join(dims), MULTI.join(dim_labels(dims)), tried_unknown, False
            )
    return CategoryResult(
        CATEGORY_FALLBACK,
        MULTI.join(dim_labels([CATEGORY_FALLBACK])),
        tried_unknown,
        True,
    )


# ------------------------------------------------------------- 字段映射表

# { 目标字段: (源字段, 转换函数) 或 [(源字段, 转换函数), ...] }
#
#   源字段    —— 该站 CSV 里的表头，一字不差
#   转换函数  —— transforms.py 里的清洗函数，或 lambda；None 表示原样搬运
#
# 约定：
#   1. 写成列表表示「主列 + 备选列」：主列有值就用主列，主列为空才回退备选列。
#      （dict 里不能写两个同名 key，所以必须写成列表）
#   2. raw_data_key / detail_url 不写在这里 —— 分别由 build_source_key() /
#      build_detail_url() 生成，避免两处产出同一字段打架。
#   3. tags / category_id **也不写在这里** —— 两者同源，都由 resolve_category() 算。
#      tags 存的是统一维度的中文名（不再搬运站点原始标签），category_id 是对应 id，
#      「这一列该取谁」由 CATEGORY_SOURCES 统一管，不散落在各站映射里。
#   4. 没被任何映射消费的源字段不会丢 —— 会进 raw_data 兜底字段。
#      （注意 consumed_source_columns() 也把 CATEGORY_SOURCES 的列算进去了）

PRODUCT_MAP: dict[str, dict[str, object]] = {
    # ---------------------------------------------------------------- 北方
    "beifang": {
        "title":       ("productName", clean_text),
        "description": ("dataProductDesc", clean_text),
        "source":      ("supplyName", clean_text),
    },
    # ---------------------------------------------------------------- 北京
    "beijing": {
        "title":       ("goodsName", clean_text),
        "description": ("goodsBriefIntroduce", clean_text),
        "source":      ("orgName", clean_text),
    },
    # ---------------------------------------------------------------- 福建
    "fujian": {
        "title":       ("name", clean_text),
        "description": ("introduction", clean_text),
        "source":      ("supplierName", clean_text),
    },
    # ---------------------------------------------------------------- 广东
    "guangdong": {
        "title":       ("CPMC", clean_text),
        "description": ("CPMS", clean_text),
        "source":      ("KHQC", clean_text),
    },
    # ---------------------------------------------------------------- 贵阳
    "guiyang": {
        "title":       ("name", clean_text),
        "description": ("descript", clean_text),
        "source":      ("enterprise_name", clean_text),
    },
    # ---------------------------------------------------------------- 海南
    "hainan": {
        "title":       ("proResourceName", clean_text),
        "description": ("proResourceDesc", clean_text),
        "source":      ("companyName", clean_text),
    },
    # ---------------------------------------------------------------- 杭州
    "hangzhou": {
        "title":       ("productName", clean_text),
        "description": ("productDesc", clean_text),
        "source":      ("orgName", clean_text),
    },
    # ---------------------------------------------------------------- 上海
    "shanghai": {
        "title":       ("dataName", clean_text),
        "description": ("dataContent", clean_text),
        "source":      ("supplierCompanyName", clean_text),
    },
    # ---------------------------------------------------------------- 郑州
    "zhengzhou": {
        "title":       ("name", clean_text),
        "description": ("introduce", clean_text),
        "source":      ("ctName", clean_text),
    },
}

# 目标字段的输出顺序（CSV 列序）
PRODUCT_COLUMNS = [
    "raw_data_key",
    "title",
    "description",
    "tags",
    "market_id",
    "category_id",
    "source",
    "detail_url",
]

# 允许写进 raw_data 兜底的额外字段（默认只存未映射字段）
RAW_DATA_ENABLED = True


def _as_rules(rule) -> list[tuple]:
    """把单条规则或规则列表统一成列表。"""
    if not rule:
        return []
    if isinstance(rule, tuple):
        return [rule]
    return list(rule)


def consumed_source_columns(market_id: str) -> set[str]:
    """该站被映射消费掉的源列名集合（用来算 raw_data 兜底字段）。"""
    cols = set(SOURCE_KEY.get(market_id, ()))
    # tags / category_id 不在 PRODUCT_MAP 里，但它们的源列同样算「已消费」
    for col, _sep in CATEGORY_SOURCES.get(market_id, []):
        cols.add(col)
    for target, rule in PRODUCT_MAP.get(market_id, {}).items():
        for src_col, _ in _as_rules(rule):
            cols.add(src_col)
    return cols


def split_by_map(row: dict, market_id: str) -> tuple[dict, dict]:
    """把一行 CSV 数据拆成 (已映射字段, 未映射字段)。

    主列 + 备选列的兜底：**主列有值才写入，为空才回退备选列**；
    都空则留 None。转换函数抛异常只让该字段置 None，不中断整批处理。
    """
    mapping = PRODUCT_MAP.get(market_id, {})
    mapped: dict = {}
    for target, rule in mapping.items():
        for src_col, func in _as_rules(rule):
            raw_value = row.get(src_col)
            try:
                value = func(raw_value) if func else raw_value
                if isinstance(value, str):
                    value = value.strip() or None
            except Exception:
                value = None
            if value is not None and value != "":
                mapped[target] = value
                break            # 主列有值就用主列，不再看备选列
            if target not in mapped:
                mapped[target] = None

    known = consumed_source_columns(market_id)
    raw = {k: v for k, v in row.items() if k not in known and v not in (None, "")}
    return mapped, raw
