"""数据分类（category 表）映射配置。

两层结构：
  1. 统一维度：全站通用的 35 个语义类别，对应 category 表的行
  2. 站点原始「标签名」 → 统一维度 id：把 9 个交易所各自的分类写法翻译过来

统一维度清单由 dimensions/统一维度集合.csv 语义归并得来，
站点原始条目来自 dimensions/站点维度条目明细.csv（193 条）。

──────────────────────────────────────────────────────────────
为什么用「标签名」而不是「分类 code」做映射（2026-10-04 改动）
──────────────────────────────────────────────────────────────

原先是 CODES2DIMS：每站一份 code→维度 的表，9 份合计 193 条。有三个问题：

  1. 部分站点列表接口根本不回显 code（郑州 sceneCode 恒 null、贵阳 sectors 恒 0），
     只能先「名称 → 反查 code → 再查 code → 维度」，绕一圈
  2. code 是站点内部实现，站点一改就全废；而且同样 diligence 换来的是不可读的配置
  3. 各站 code 分隔符五花八门更容易配错（曾经把广东 YYCJ 配成 ";"，实际是空格）

改成按标签名映射后：

  ✅ 193 条 → **120 条**，而且是**全站共享一张扁平表**，不再按站分9份
  ✅ 跨站零冲突：193 个「站点-标签」对去重后只有 118 个名字，
     且同名标签从没有被不同站映射到不同维度（已实测验证）
  ✅ 新站点接入成本趋近于零：只要它的标签用的是常见说法，直接命中现有条目
  ✅ 顺带修正：广东 YYCJMC 用**空格**分隔（原 code 方案配错成 ";"，导致漏判）

代价与边界（如实记录）：
  ⚠️ 依赖站点返回的是可读文本。纯 ID 型接口不适用。
  ⚠️ 站点换了标签文案（如「交通运输」改「交通物流」）要补一条 —— 但补一条全站受益。
  ⚠️ 无法识别的自由文案会被丢弃；编译 degree 由 build_products.py 的 unknown 统计暴露。
"""

# ---------------------------------------------------------------- 统一维度

# 统一维度的 id，顺序即 category 表的插入顺序（决定前端展示顺序）
DIMS_ID = [
    "manufacturing",
    "government_governance",
    "healthcare",
    "energy_power",
    "finance",
    "transportation_logistics",
    "culture_tourism",
    "legal_services",
    "cross_border",
    "retail_ecommerce",
    "ai_service",
    "information_communication",
    "education",
    "scientific_research",
    "real_estate",
    "automobile",
    "hospitality",
    "construction",
    "mining",
    "agriculture",
    "leasing_business",
    "resident_services",
    "credit_service",
    "eco_environment",
    "statistics",
    "meteorology",
    "others",
    "emergency_safety",
    "media_marketing",
    "geospatial",
    "all_scenarios",
    "tobacco",
    "intellectual_property",
    "ceramics",
    "international_organization",
]

# 统一维度的中文名，即归并后的语义名称。
# 同时也是 product 表 tags 字段的取值来源 —— tags 存的是归并后的 35 个维度名，
# 不再是各站自己的原始标签文案。
DIMS_NAME = {
    "manufacturing": "制造业与工业",
    "government_governance": "政务与城市治理",
    "healthcare": "医疗健康",
    "energy_power": "能源电力",
    "finance": "金融业",
    "transportation_logistics": "交通运输、仓储与物流",
    "culture_tourism": "文化旅游与文体娱乐",
    "legal_services": "司法与法律服务",
    "cross_border": "跨境与外贸",
    "retail_ecommerce": "批发零售与电子商务",
    "ai_service": "人工智能与智能服务",
    "information_communication": "信息传输、软件与通信",
    "education": "教育",
    "scientific_research": "科学研究与技术服务业",
    "real_estate": "房地产业",
    "automobile": "汽车",
    "hospitality": "住宿和餐饮业",
    "construction": "建筑业",
    "mining": "采矿业",
    "agriculture": "农林牧渔",
    "leasing_business": "租赁和商务服务业",
    "resident_services": "居民服务与生活服务业",
    "credit_service": "信用服务",
    "eco_environment": "生态环保与绿色低碳",
    "statistics": "统计与社会统计",
    "meteorology": "气象服务",
    "others": "其他与综合",
    "emergency_safety": "应急管理与公共安全",
    "media_marketing": "新闻传媒与市场营销",
    "geospatial": "地理空间与遥感",
    "all_scenarios": "全场景/不限",
    "tobacco": "烟草",
    "intellectual_property": "知识产权",
    "ceramics": "陶瓷",
    "international_organization": "国际组织",
}

# ----------------------------------------------- 站点原始标签名 → 统一维度

# 全站共享的一张扁平字典：原始标签名 → 统一维度 id。
#
# 来源：dimensions/站点维度条目明细.csv 的「条目名称」列，
#       按其「语义归并」列反查到这里的 DIMS_ID。
# 排序：按统一维度分组（组内的中文注释就是该维度的展示名），便于按语义查找。
#
# 维护约定：
#   - **加新标签时先想清楚是不是通用说法**。是通用的就放这里，全站受益；
#     只在某一站出现、且明显是该站自由文案的，建议不收 —— 那是噪声。
#   - 同名标签在所有站含义一致，这是共享表成立的前提（已用 193 条条目验证，零冲突）。
#     如果将来出现同名不同义，才需要拆回按站分表。
#   - 字典里放的是**归一化后**的形状：全半角、首尾空格由 split_multi() 处理，这里保持原样。
# ── 来源一：9 站页面筛选下拉里实际存在的分类写法 ─────────────────────────
# 从 dimensions/站点维度条目明细.csv 的「条目名称」列提取，按其「语义归并」反查到 DIMS_ID。
# 193 个「站点-条目」对去重后是 118 个名字，且不冲突，所以能压成一张共享表。
_SITE_LABELS: dict[str, str] = {
    # 制造业与工业
    "制造": "manufacturing",
    "制造业": "manufacturing",
    "工业": "manufacturing",
    "工业制造": "manufacturing",
    "智能制造": "manufacturing",
    # 政务与城市治理
    "公共服务": "government_governance",
    "公共管理、社会保障和社会组织": "government_governance",
    "城市治理": "government_governance",
    "政务": "government_governance",
    "政府/公共": "government_governance",
    "政府/公共事业": "government_governance",
    "智慧城市": "government_governance",
    "监管": "government_governance",
    # 医疗健康
    "医疗": "healthcare",
    "医疗健康": "healthcare",
    "医疗卫生": "healthcare",
    "卫生和社会工作": "healthcare",
    # 能源电力
    "水力/电力/热力/燃气": "energy_power",
    "电力、热力、燃气及水生产和供应业": "energy_power",
    "能源": "energy_power",
    "能源化工": "energy_power",
    "能源电力": "energy_power",
    # 金融业
    "智慧金融": "finance",
    "金融": "finance",
    "金融业": "finance",
    "金融服务": "finance",
    # 交通运输、仓储与物流
    "交通": "transportation_logistics",
    "交通/物流": "transportation_logistics",
    "交通/物流/贸易/零售": "transportation_logistics",
    "交通运输": "transportation_logistics",
    "交通运输、仓储和邮政业": "transportation_logistics",
    "物流": "transportation_logistics",
    # 文化旅游与文体娱乐
    "娱乐体育": "culture_tourism",
    "广告/传媒/文化/体育": "culture_tourism",
    "文化、体育和娱乐业": "culture_tourism",
    "文化旅游": "culture_tourism",
    "文旅": "culture_tourism",
    "旅游": "culture_tourism",
    # 司法与法律服务
    "司法": "legal_services",
    "法律服务": "legal_services",
    # 跨境与外贸
    "外贸": "cross_border",
    "跨境": "cross_border",
    # 批发零售与电子商务
    "商业": "retail_ecommerce",
    "商贸流通": "retail_ecommerce",
    "批发和零售业": "retail_ecommerce",
    "新零售": "retail_ecommerce",
    "电商": "retail_ecommerce",
    "电子商务": "retail_ecommerce",
    "贸易/零售": "retail_ecommerce",
    "零售": "retail_ecommerce",
    # 人工智能与智能服务
    "AI": "ai_service",
    "人工智能": "ai_service",
    "智能服务": "ai_service",
    # 信息传输、软件与通信
    "互联网/IT/电子/通信": "information_communication",
    "信息传输、软件和信息技术服务业": "information_communication",
    "通信": "information_communication",
    "通信运营商": "information_communication",
    "通讯": "information_communication",
    # 教育
    "培训教育": "education",
    "教育": "education",
    "教育服务": "education",
    "文化教育": "education",
    # 科学研究与技术服务业
    "学术科研": "scientific_research",
    "科创": "scientific_research",
    "科学研究和技术服务业": "scientific_research",
    "科技创新": "scientific_research",
    "科研教育": "scientific_research",
    # 房地产业
    "房地产": "real_estate",
    "房地产业": "real_estate",
    # 汽车
    "汽车": "automobile",
    # 住宿和餐饮业
    "住宿/餐饮": "hospitality",
    "住宿和餐饮业": "hospitality",
    # 建筑业
    "住建": "construction",
    "建筑": "construction",
    "建筑/房产": "construction",
    "建筑业": "construction",
    "智能建筑": "construction",
    # 采矿业
    "采矿": "mining",
    "采矿业": "mining",
    # 农林牧渔
    "三农": "agriculture",
    "农/林/牧/渔": "agriculture",
    "农、林、牧、渔业": "agriculture",
    "农业": "agriculture",
    "农林牧渔": "agriculture",
    "现代农业": "agriculture",
    # 租赁和商务服务业
    "企业": "leasing_business",
    "企服": "leasing_business",
    "咨询": "leasing_business",
    "咨询服务": "leasing_business",
    "租赁/商务": "leasing_business",
    "租赁和商务服务业": "leasing_business",
    # 居民服务与生活服务业
    "居民服务": "resident_services",
    "居民服务、修理和其他服务业": "resident_services",
    "生活服务": "resident_services",
    # 信用服务
    "信用": "credit_service",
    # 生态环保与绿色低碳
    "水利、环境和公共设施管理业": "eco_environment",
    "环保": "eco_environment",
    "生态环保": "eco_environment",
    "绿色低碳": "eco_environment",
    # 统计与社会统计
    "社会统计": "statistics",
    "统计": "statistics",
    # 气象服务
    "气象": "meteorology",
    "气象服务": "meteorology",
    # 其他与综合
    "以上均不属于": "others",
    "其他": "others",
    "其他场景": "others",
    "综合": "others",
    # 应急管理与公共安全
    "安全服务": "emergency_safety",
    "应急管理": "emergency_safety",
    # 新闻传媒与市场营销
    "品牌营销": "media_marketing",
    "新闻传媒": "media_marketing",
    "舆情": "media_marketing",
    # 地理空间与遥感
    "地理空间": "geospatial",
    "地理遥感": "geospatial",
    "时空": "geospatial",
    # 全场景/不限
    "全场景": "all_scenarios",
    # 烟草
    "烟草": "tobacco",
    # 知识产权
    "知识产权": "intellectual_property",
    # 陶瓷
    "陶瓷": "ceramics",
    # 国际组织
    "国际组织": "international_organization",
}

# ── 来源二：国标行业（GB/T 4754 大类 / 中类） ────────────────────────────
# 这批词不在任何站的筛选下拉里，而是杭州 industry 列回显的国标行业名
# （如 "软件和信息技术服务业"、"道路运输业"），出现在 3 千多条商品上。
#
# 收进来的理由：这是**国家标准词表**，不是某站的自定义文案 —— 只要还有别家用
# 国标行业名（贵阳、福建、海南用的就是国标门类），这批映射就能直接复用。
# 当初正是靠它们把杭州的兜底率从 47.1% 压到 0%。
GB_INDUSTRY: dict[str, str] = {
    # 农林牧渔
    "渔业": "agriculture",
    "林业": "agriculture",
    "畜牧业": "agriculture",
    "农、林、牧、渔专业及辅助性活动": "agriculture",
    # 采矿业
    "煤炭开采和洗选业": "mining",
    # 制造业
    "农副食品加工业": "manufacturing",
    "酒、饮料和精制茶制造业": "manufacturing",
    "纺织业": "manufacturing",
    "纺织服装、服饰业": "manufacturing",
    "皮革、毛皮、羽毛及其制品和制鞋业": "manufacturing",
    "文教、工美、体育和娱乐用品制造业": "manufacturing",
    "石油、煤炭及其他燃料加工业": "manufacturing",
    "化学原料和化学制品制造业": "manufacturing",
    "黑色金属冶炼和压延加工业": "manufacturing",
    "金属制品业": "manufacturing",
    "通用设备制造业": "manufacturing",
    "专用设备制造业": "manufacturing",
    "汽车制造业": "manufacturing",
    # 能源电力
    "电力、热力生产和供应业": "energy_power",
    "水的生产和供应业": "energy_power",
    # 建筑业
    "房屋建筑业": "construction",
    "土木工程建筑业": "construction",
    "建筑装饰、装修和其他建筑业": "construction",
    # 交通运输、仓储与物流
    "铁路运输业": "transportation_logistics",
    "道路运输业": "transportation_logistics",
    "水上运输业": "transportation_logistics",
    "航空运输业": "transportation_logistics",
    "多式联运和运输代理业": "transportation_logistics",
    "装卸搬运和仓储业": "transportation_logistics",
    "通用仓储": "transportation_logistics",
    # 信息传输、软件与通信
    "电信、广播电视和卫星传输服务": "information_communication",
    "互联网和相关服务": "information_communication",
    "互联网平台": "information_communication",
    "互联网生产服务平台": "information_communication",
    "软件和信息技术服务业": "information_communication",
    "信息技术咨询服务": "information_communication",
    "信息处理和存储支持服务": "information_communication",
    # 金融业
    "货币金融服务": "finance",
    "资本市场服务": "finance",
    "保险业": "finance",
    "其他金融业": "finance",
    # 房地产业 —— 国标把房地产归入房地产业，本批数据暂未见
    # 租赁和商务服务业
    "租赁业": "leasing_business",
    "商务服务业": "leasing_business",
    # 科学研究与技术服务业
    "研究和试验发展": "scientific_research",
    "专业技术服务业": "scientific_research",
    "科技推广和应用服务业": "scientific_research",
    # 生态环保与绿色低碳
    "生态保护和环境治理业": "eco_environment",
    "公共设施管理业": "eco_environment",
    "水利管理业": "eco_environment",
    # 医疗健康
    "卫生": "healthcare",
    # 文化旅游与文体娱乐
    "文化艺术业": "culture_tourism",
    "娱乐业": "culture_tourism",
    # 住宿和餐饮业
    "住宿业": "hospitality",
    "餐饮业": "hospitality",
    # 批发零售与电子商务
    "批发业": "retail_ecommerce",
    "零售业": "retail_ecommerce",
    # 政务与城市治理
    "国家机构": "government_governance",
    "中国共产党机关": "government_governance",
    "人民政协、民主党派": "government_governance",
    "群众团体、社会团体和其他成员组织": "government_governance",
    # 新闻传媒与市场营销
    "广播、电视、电影和录音制作业": "media_marketing",
    # 居民服务与生活服务业
    "其他服务业": "resident_services",
}

# 合并后的完整字典。两块来源有重叠时以后者为准，便于把通用国标词放在后面兜底。
LABEL2DIM: dict[str, str] = {**_SITE_LABELS, **GB_INDUSTRY}

# 未进字典但确实在各站数据里出现的自由文案怎么处理：
# 直接丢弃 —— 它们大多是商品的自定义标签（如上海「工艺改善」「智能水表生产制造」），
# 一个词只对应一两件商品，收进字典是典型的过拟合，维护成本远大于收益。
# 这些丢弃情况会由 build_products.py 的 unknown 统计暴露出来，需要时再按需补录。
#
# 历史上唯一被正式收录的两条（上海列表数据里出现、页面下拉里没有）：
#   "以上均不属于" → others（57 件商品，是上海真实的「其他」类目）
#   "文化教育"     → education（2 件商品）

SEP_NONE = "\x00"  # 哨兵：表示不用分隔符拆分（单值字段）

MULTI = "||"  # product 表 tags / category_id 的多值分隔符


def labels_to_dims(raw_value: str, sep: str = "|") -> tuple[list[str], list[str]]:
    """把一段原始标签文本翻译成统一维度 id。

    raw_value 是 CSV 里那一列的取值，多值用 sep 分隔。
    返回 (维度 id 列表, 未识别的原始标签列表)，去重且保持首次出现顺序。

    翻译不了的标签会被丢弃而不是抛异常 —— 单条脏数据不该中断 4 万条的批处理，
    但会通过第二个返回值暴露出来，交给上层统计。
    """
    dims: list[str] = []
    unknown: list[str] = []
    for part in str(raw_value or "").split(sep):
        label = part.strip()
        if not label:
            continue
        dim = LABEL2DIM.get(label)
        if dim:
            if dim not in dims:
                dims.append(dim)
        else:
            unknown.append(label)
    return dims, unknown


def dim_labels(dim_ids: list[str]) -> list[str]:
    """统一维度 id 列表 → 统一维度中文名列表（product 表 tags 的取值）。"""
    return [DIMS_NAME[d] for d in dim_ids if d in DIMS_NAME]
