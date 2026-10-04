"""数据清洗与统一化：把 9 个交易所各不相同的原始 CSV 转成可入库的统一格式。

    data/<site>_products.csv   ──►  product / category / market 表的插入数据
    （采集侧 collector/ 产出）        （产出到 processeddata/）

分层：
    mapping/      纯配置——源列名到目标字段的对应关系，改这里不用动代码
        market.py    交易所字典表（market 表）
        category.py  统一维度 + 各站 code 翻译（category 表）
        product.py   商品字段 ETL 规则（product 表）← 量最大，还在填
    transforms.py 通用清洗函数——被 mapping 引用，自身不依赖任何配置
    processeddata/  处理后的产出（供后续程序读取入库）

依赖方向单向：mapping → transforms，反过来不行。
"""
