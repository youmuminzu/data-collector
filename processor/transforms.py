"""通用清洗函数。

和 mapping/ 平级，被三个 mapping 模块共同引用（不只是 product 用）。
设计原则：
  - 每个函数都是「任意输入 → 规范值 或 None」，不抛异常
  - 脏数据返回 None，交给上层决定是丢弃还是进 raw_data
  - 不 import mapping 里的任何东西，避免循环依赖
"""

from __future__ import annotations

import re

_SPACES = re.compile(r"\s+")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def clean_text(value) -> str | None:
    """文本清洗：去首尾空白、压平内部换行/连续空白、空串转 None。"""
    if value is None:
        return None
    text = _SPACES.sub(" ", str(value)).strip()
    return text or None


def clean_int(value) -> int | None:
    """取整。输入像 "3.0" 这种浮点字符串也能处理。"""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def clean_float(value) -> float | None:
    """取浮点数。抓不到数字返回 None（比如 "面议"）。"""
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    m = _NUM.search(text)
    return float(m.group()) if m else None


def split_multi(value, sep: str = "|") -> list[str]:
    """多值字段拆成列表。

    采集侧多值统一用 "|" 分隔（不用顿号——"农、林、牧、渔业" 这种维度名自带顿号）。
    注意郑州/贵阳的列表原生字段是英文逗号分隔，这种要在 mapping 里单独指定 sep。
    """
    if not value:
        return []
    parts = [clean_text(p) for p in str(value).split(sep)]
    return [p for p in parts if p]


def join_multi(values: list[str]) -> str | None:
    """反向：列表拼回 "|" 分隔的字符串（写 CSV / 单列兜底时用）。"""
    items = [clean_text(v) for v in values or []]
    items = [v for v in items if v]
    return "|".join(items) or None


def strip_html(value) -> str | None:
    """去掉富文本里的 HTML 标签，保留纯文本。"""
    text = clean_text(value)
    if text is None:
        return None
    return clean_text(re.sub(r"<[^>]+>", "", text))


def truncate(value, limit: int = 1000) -> str | None:
    """截断到指定长度，超出部分丢弃（数据库列有长度限制时用）。"""
    text = clean_text(value)
    return text[:limit] if text else None
