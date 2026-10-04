"""把 9 个交易所的原始 CSV 转成 product 表结构的统一 CSV。

产出（都在 processeddata/ 下，每个交易所固定只留两份）：
    {market_id}_new.csv     本次产出
    {market_id}_old.csv     上一版（跑下一次时自动降级，更老的丢弃）
    product_files.json      所有文件的 file_name / updated_at / upload_at

为什么要用固定的 old/new 而不是时间戳：时间戳会让每跑一次就多 9 个文件，
调试期堆到几十份。这里只需要「上一版」用于比对增量，不需要完整历史。

用法：
    uv run python processor/build_products.py

为什么产物用 CSV 而不是 JSON：商品数据量是 4 万级，JSON 的重复键名会让文件
比 CSV 大很多（market / category 那种字典表才用 JSON）。
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from processor.mapping import MARKET_ID, MARKET_SITE  # noqa: E402
from processor.mapping import check  # noqa: E402
from processor.mapping.product import (  # noqa: E402
    PRODUCT_COLUMNS,
    build_detail_url,
    build_source_key,
    resolve_category,
    split_by_map,
)

OUT_DIR = ROOT / "processor" / "processeddata"
ENCODING = "utf-8-sig"
STAMP = "%Y%m%d%H%M%S"
NEW_TAG = "_new"   # 本次产出
OLD_TAG = "_old"   # 上一版


def rotate_output(market_id: str) -> tuple[str, Path, str]:
    """滚动保留两份：本次写 _new.csv，上一份降为 _old.csv，更老的丢掉。

    返回 (file_name, out_path, note)。note 非空表示发生了降级，需要提示用户。
    """
    new_name = f"{market_id}{NEW_TAG}.csv"
    old_name = f"{market_id}{OLD_TAG}.csv"
    new_path = OUT_DIR / new_name
    old_path = OUT_DIR / old_name

    # 清掉更早的时间戳产物，保证该交易所目录下永远只有两份
    for stale in OUT_DIR.glob(f"{market_id}_*.csv"):
        if stale.name == new_name or stale == old_path:
            continue
        try:
            stale.unlink()
        except OSError:
            pass  # 被 Excel 占着就先放过，下次跑再收

    if not new_path.exists():
        return new_name, new_path, ""

    # 上一版存在 → 降级为 old
    try:
        if old_path.exists():
            old_path.unlink()
        new_path.replace(old_path)
    except OSError as exc:
        # 上一版被 Excel 独占：不动它，本次另存时间戳文件，避免丢数据
        stamp = datetime.now().strftime(STAMP)
        fallback = f"{market_id}_{stamp}.csv"
        return fallback, OUT_DIR / fallback, f"上一版被占用（{exc}），本次另存为 {fallback}"
    return new_name, new_path, ""


def flatten(value) -> str:
    """压平换行和连续空白，避免 CSV 里出现物理多行。"""
    if value is None:
        return ""
    return " ".join(str(value).split())


def process(market_id: str, now: datetime) -> dict:
    site = MARKET_SITE[market_id]
    src = ROOT / "data" / f"{site}_products.csv"
    out_name, out_path, note = rotate_output(market_id)

    stats = {
        "market_id": market_id,
        "read": 0,
        "written": 0,
        "no_key": 0,            # 主键残缺，跳过
        "no_url": 0,            # 详情页 URL 拼不出来
        "cat_others": 0,        # category_id 落到 others（含站点自己归类为「其他」的）
        "cat_fallback": 0,      # 其中真正「一个维度都没翻出来」被兜底的
        "dup_key": 0,
        "unknown_labels": None,  # Counter：字典里没有的自由文案，用于发现该补什么词条
    }

    unknown: Counter[str] = Counter()

    with src.open(encoding=ENCODING, newline="") as f:
        rows = list(csv.DictReader(f))
    stats["read"] = len(rows)

    seen: set[str] = set()
    with out_path.open("w", encoding=ENCODING, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRODUCT_COLUMNS)
        writer.writeheader()
        for row in rows:
            key = build_source_key(row, market_id)
            if not key:
                stats["no_key"] += 1
                continue
            if key in seen:
                stats["dup_key"] += 1
                continue
            seen.add(key)

            mapped, _raw = split_by_map(row, market_id)
            url = build_detail_url(market_id, row)
            if not url:
                stats["no_url"] += 1

            # tags 与 category_id 同源计算：tags 存统一维度中文名，category_id 存 id
            cat = resolve_category(row, market_id)
            unknown.update(cat.unknown)

            mapped["raw_data_key"] = key
            mapped["market_id"] = market_id
            mapped["detail_url"] = url
            mapped["category_id"] = cat.ids
            mapped["tags"] = cat.tags
            if cat.ids == "others":
                stats["cat_others"] += 1
            if cat.is_fallback:
                stats["cat_fallback"] += 1

            writer.writerow({c: flatten(mapped.get(c)) for c in PRODUCT_COLUMNS})
            stats["written"] += 1

    stats["unknown_labels"] = unknown
    return {
        "file_name": out_name,
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "upload_at": "",
        "_stats": stats,
        "_note": note,
    }


def main() -> int:
    problems = check()
    if problems:
        print("配置自检发现问题：")
        for p in problems:
            print("  -", p)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()

    entries = []
    print(
        f"{'交易所':<12}{'读入':>7}{'写出':>7}{'主键缺失':>9}{'重复':>6}"
        f"{'无URL':>7}{'归其他':>7}{'其中兜底':>9}"
    )
    print("-" * 66)
    for market_id in MARKET_ID:
        # 采集失败的站点没有源文件，跳过而不是整个崩掉（CI 里常见）
        src = ROOT / "data" / f"{MARKET_SITE[market_id]}_products.csv"
        if not src.exists():
            print(f"! 缺少 {src.name}，跳过 {market_id}")
            continue
        info = process(market_id, now)
        s = info["_stats"]
        print(
            f"{market_id:<14}{s['read']:>7}{s['written']:>7}"
            f"{s['no_key']:>9}{s['dup_key']:>6}{s['no_url']:>7}"
            f"{s['cat_others']:>7}{s['cat_fallback']:>9}"
        )
        if info["_note"]:
            print(f"    ! {market_id}: {info['_note']}")
        entries.append(info)

    # 写索引文件
    index = [
        {"file_name": e["file_name"], "updated_at": e["updated_at"], "upload_at": e["upload_at"]}
        for e in entries
    ]
    idx_path = OUT_DIR / "product_files.json"
    with idx_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # 未识别的自由文案合并统计：用来决定要不要往 LABEL2DIM 里补词条
    total_unknown: Counter[str] = Counter()
    for e in entries:
        total_unknown += e["_stats"]["unknown_labels"]
    if total_unknown:
        hit_rows = sum(total_unknown.values())
        print(f"\n未在 LABEL2DIM 命中的自由文案：{len(total_unknown)} 种 / 出现 {hit_rows} 次")
        print("（多为单件商品的自定义关键词，故意不收进字典。出现次数多的才值得补录）")
        for label, n in total_unknown.most_common(10):
            print(f"    {label:<24} {n:>5}")
        if len(total_unknown) > 10:
            print(f"    ... 还有 {len(total_unknown) - 10} 种")
    else:
        print("\n所有标签均已在 LABEL2DIM 命中 ✓")

    total = sum(e["_stats"]["written"] for e in entries)
    print("-" * 66)
    print(f"合计写出 {total} 条")
    print(f"索引 → {idx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
