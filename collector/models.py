"""公共数据结构

单独成模块是为了让 base.py 与 client.py 都能引用而不产生循环导入。
"""

from __future__ import annotations

from dataclasses import dataclass, field


class CircuitBroken(Exception):
    """触发熔断：立即停止采集，已抓到的数据和进度全部保留。"""


def make_key(row: dict, fields: tuple[str, ...]) -> str:
    """按指定字段组合生成去重主键。

    不是所有站点都有可靠的唯一 id（如上海站的 id 来自各来源系统，全局会碰撞），
    因此允许用多个字段组合来标识一条记录。
    """
    return "|".join("" if row.get(f) is None else str(row.get(f)) for f in fields)


@dataclass
class PageRequest:
    """一次分页请求的描述，与具体 HTTP 库解耦。"""

    url: str
    method: str = "POST"
    json_body: dict | None = None
    params: dict | None = None


@dataclass
class PageResult:
    """站点解析后的统一分页结果。"""

    rows: list[dict] = field(default_factory=list)
    total: int | None = None
    page_echo: int | None = None  # 后端回显的页码，用于校验分页是否真的生效
