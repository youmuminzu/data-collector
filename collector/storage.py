"""进度记录与 CSV 落盘

断点续传靠这两样：Progress 记住「下一页从哪开始」，CsvSink 保证每页抓到即写盘。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ENCODING = "utf-8-sig"  # Excel 直接打开不乱码


class Progress:
    """采集进度，JSON 持久化。"""

    def __init__(
        self,
        site: str,
        total: int | None = None,
        next_page: int = 1,
        fetched_rows: int = 0,
        finished: bool = False,
        columns: list[str] | None = None,
        updated_at: str | None = None,
    ) -> None:
        self.site = site
        self.total = total
        self.next_page = next_page
        self.fetched_rows = fetched_rows
        self.finished = finished
        self.columns = columns or []
        self.updated_at = updated_at

    @classmethod
    def load(cls, path: Path) -> "Progress":
        if not path.exists():
            return cls(site=path.stem.replace("_state", ""))
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"[warn] 进度文件损坏，将重新开始：{path}")
            return cls(site=path.stem.replace("_state", ""))
        return cls(
            site=raw.get("site", ""),
            total=raw.get("total"),
            next_page=int(raw.get("next_page", 1)),
            fetched_rows=int(raw.get("fetched_rows", 0)),
            finished=bool(raw.get("finished", False)),
            columns=raw.get("columns") or [],
            updated_at=raw.get("updated_at"),
        )

    def reset(self) -> None:
        self.total = None
        self.next_page = 1
        self.fetched_rows = 0
        self.finished = False
        self.columns = []

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class CsvSink:
    """增量写 CSV：首次写入确定列顺序，之后严格按该顺序追加。"""

    def __init__(self, path: Path, columns: list[str] | None = None) -> None:
        self.path = path
        self.columns = columns or []

    def row_count(self) -> int:
        """已落盘的记录行数（正确跳过字段内嵌换行）。"""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0
        try:
            return len(pd.read_csv(self.path, dtype=str))
        except (ValueError, OSError):
            return 0

    def seen_keys(self, key_fields: tuple[str, ...], make_key) -> set[str]:
        """读取已落盘记录的主键，供断点续传去重。"""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return set()
        if not key_fields:
            return set()
        try:
            df = pd.read_csv(self.path, dtype=str)
        except (ValueError, OSError):
            return set()
        if any(f not in df.columns for f in key_fields):
            return set()
        return {make_key(row, key_fields) for row in df.to_dict("records")}

    def append(self, df: pd.DataFrame) -> None:
        if not self.columns:
            self.columns = list(df.columns)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.path, index=False, mode="w", encoding=ENCODING)
        else:
            df.reindex(columns=self.columns).to_csv(
                self.path, index=False, mode="a", header=False, encoding=ENCODING
            )
