"""给已采集完成的 CSV 补出维度编码列。

适用场景：列表接口只回显维度中文名、不回显编码的站点（郑州 sceneName / 贵阳 sectors_name）。
后来在采集器里加了自动补列，但**改代码之前就已经抓完的 CSV 里没有这两列**，
用本脚本原地补上，不必重抓一遍数据。

补列逻辑直接复用采集器的 `normalize()`，保证与以后新采集的输出完全一致。

用法：
    uv run python tools/patch_dim_code.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from collector.sites.guiyang import GuiyangCollector
from collector.sites.zhengzhou import ZhengzhouCollector

ENCODING = "utf-8-sig"
COLLECTORS = [ZhengzhouCollector, GuiyangCollector]


def patch(cls) -> None:
    c = cls()
    if not (c.dim_echo_column and c.dim_code_column and c.dim_name_to_code):
        return
    if not c.csv_path.exists():
        print(f"[skip] {c.site} 主 CSV 不存在：{c.csv_path}")
        return

    df = pd.read_csv(c.csv_path, dtype=str).fillna("")
    if c.dim_echo_column not in df.columns:
        print(f"[warn] {c.site} 缺少回显列 {c.dim_echo_column}，跳过")
        return

    # 走采集器同一套逻辑，避免脚本和采集器两套翻译规则跑偏
    patched = c.normalize(df.to_dict("records"))
    df[c.dim_code_column] = patched[c.dim_code_column].values

    # 把编码列紧挨着放在名称列后面，方便对照
    cols = list(df.columns)
    cols.remove(c.dim_code_column)
    cols.insert(cols.index(c.dim_echo_column) + 1, c.dim_code_column)
    df = df[cols]

    hit = int((df[c.dim_code_column] != "").sum())
    try:
        df.to_csv(c.csv_path, index=False, encoding=ENCODING)
        target = c.csv_path
    except PermissionError:
        target = c.data_dir / f"{c.site}_products_with_code.csv"
        df.to_csv(target, index=False, encoding=ENCODING)
        print(f"[warn] {c.csv_path.name} 被占用（可能正用 Excel 打开），已改写到 {target.name}")

    print(f"{c.site}：{c.dim_echo_column} → {c.dim_code_column} 已写入 {target}")
    print(f"  共 {len(df)} 行，其中 {hit} 行有编码，空 {len(df) - hit} 行")


def main() -> None:
    for cls in COLLECTORS:
        patch(cls)


if __name__ == "__main__":
    main()
