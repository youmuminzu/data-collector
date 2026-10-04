"""数据采集公共库

站点无关的通用能力（限速、熔断、断点续传、落盘）都在这里，
具体交易所只需在 collector/sites/ 下实现各自的请求与解析逻辑。
"""

from .base import BaseCollector, CircuitBroken, PageRequest, PageResult
from .client import PoliteClient
from .storage import CsvSink, Progress

__all__ = [
    "BaseCollector",
    "CircuitBroken",
    "PageRequest",
    "PageResult",
    "PoliteClient",
    "CsvSink",
    "Progress",
]
