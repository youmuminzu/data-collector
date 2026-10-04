"""按维度分别筛选采集，再把归属写回主 CSV

适用站点：北京 / 福建 / 海南 —— 这三家的列表接口**不回显行业字段**，
从全量列表反推不出商品归属，只能对每个维度值单独筛选一次，
按「该商品出现在哪个维度的结果里」反推它属于哪些维度。

流程：
    1. 遍历维度清单，每个维度从第一页翻到空页
    2. 命中的商品整行 + 维度写入 JSONL（增量落盘，支持断点续传）
    3. 全部抓完后按主键聚合，把维度列 merge 回主 CSV

一个商品可能命中多个维度，合并时用「、」连接（与列表字段的风格一致）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .base import DIM_SEP
from .client import PoliteClient
from .models import CircuitBroken, make_key
from .storage import ENCODING

# 多值分隔符不能用「、」：维度名自带顿号（农、林、牧、渔业 / 卫生和社会工作 等），
# 会和分隔符混在一起，无法还原是几个维度。用标签里不可能出现的竖线。
SEP = DIM_SEP


class DimensionRunner:
    def __init__(self, collector) -> None:
        self.c = collector
        self.raw_path: Path = collector.data_dir / f"{collector.site}_dim_raw.jsonl"
        self.state_path: Path = collector.state_dir / f"{collector.site}_dim_state.json"

    # ------------------------------------------------ 进度

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"[warn] 维度进度文件损坏，将重新开始：{self.state_path}")
        return {}

    def _save_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_raw(self, rows: list[dict], code: str, label: str) -> None:
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        with self.raw_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps({"code": code, "label": label, "row": row}, ensure_ascii=False) + "\n")

    # ------------------------------------------------ 采集

    def run(self, force: bool = False, max_pages: int = 0) -> int:
        c = self.c
        if not c.dimensions:
            print(f"[skip] {c.site} 未配置维度清单，跳过")
            return 0

        if force and self.raw_path.exists():
            self.raw_path.unlink()
        state = {} if force else self._load_state()

        print(f"\n=== {c.site} 按维度分别采集：{len(c.dimensions)} 个维度 ===")
        print(f"    筛选字段 {c.dim_field}   JSONL → {self.raw_path}")

        try:
            with PoliteClient(
                headers=c.headers,
                timeout=c.timeout,
                sleep_range=c.sleep_range,
                max_retry=c.max_retry,
                verify=c.verify,
            ) as client:
                for code, label in c.dimensions:
                    slot = state.setdefault(code, {"next_page": 1, "finished": False, "rows": 0})
                    if slot.get("finished"):
                        print(f"  [skip] {label}({code}) 已完成 {slot.get('rows', 0)} 条")
                        continue

                    c.apply_dimension(code)
                    page = max(1, int(slot.get("next_page", 1)))
                    count = int(slot.get("rows", 0))
                    prev_first = None
                    finished = False

                    while True:
                        if max_pages and page > max_pages:
                            print(f"  [stop] {label} 达到 --dim-max-pages {max_pages}")
                            break

                        client.wait()
                        payload = None
                        for attempt in range(1, c.max_retry + 1):
                            try:
                                payload = client.request(c.build_request(page))
                                c.check_success(payload)
                                break
                            except CircuitBroken as exc:
                                print(f"\n[熔断] {label} 第 {page} 页：{exc}")
                                raise
                            except Exception as exc:
                                print(f"    [retry {attempt}/{c.max_retry}] {label} 第 {page} 页失败：{exc}")
                                if attempt < c.max_retry:
                                    client.wait()

                        if payload is None:
                            print(f"  [fail] {label} 第 {page} 页连续失败，跳过该维度剩余页")
                            break

                        result = c.parse(payload)
                        if result.page_echo is not None and result.page_echo != page:
                            print(f"\n[熔断] 分页失效：请求 {page} 页回显 {result.page_echo}")
                            break

                        if not result.rows:
                            finished = True
                            break

                        if c.key_fields:
                            first = make_key(result.rows[0], c.key_fields)
                            if first == prev_first:
                                print(f"\n[熔断] {label} 第 {page} 页与上一页首条重复，分页可能失效")
                                break
                            prev_first = first

                        self._append_raw(result.rows, code, label)
                        count += len(result.rows)
                        page += 1
                        slot.update(next_page=page, rows=count)
                        self._save_state(state)

                    if finished:
                        slot["finished"] = True
                    slot.update(next_page=page, rows=count)
                    self._save_state(state)
                    print(f"  维度 {label:<24} {count:>5} 条" + ("  ✓" if finished else "  (未完成)"), flush=True)
        finally:
            c.apply_dimension(None)

        self.merge()
        return 0

    # ------------------------------------------------ 合并回主 CSV

    def merge(self) -> None:
        c = self.c
        if not self.raw_path.exists():
            print("[warn] 没有维度数据可合并")
            return
        if not c.csv_path.exists():
            print(f"[warn] 主 CSV 不存在，请先跑全量采集：{c.csv_path}")
            return

        label_col = c.dim_output_column
        code_col = f"{c.dim_output_column}_code"

        records = []
        with self.raw_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        labels: dict[str, list[str]] = {}
        codes: dict[str, list[str]] = {}
        raw_rows: dict[str, dict] = {}
        for rec in records:
            row = rec["row"]
            key = make_key(row, c.key_fields)
            if rec["label"] not in labels.setdefault(key, []):
                labels[key].append(rec["label"])
            if rec["code"] not in codes.setdefault(key, []):
                codes[key].append(rec["code"])
            raw_rows.setdefault(key, row)

        base = pd.read_csv(c.csv_path, dtype=str).fillna("")
        base_keys = [make_key(r, c.key_fields) for r in base.to_dict("records")]

        base[label_col] = [SEP.join(labels.get(k, [])) for k in base_keys]
        base[code_col] = [SEP.join(codes.get(k, [])) for k in base_keys]

        # 维度结果里出现、但主 CSV 里没有的商品（多半是全量采集后又上架的新品）
        missing = [k for k in raw_rows if k not in set(base_keys)]
        if missing:
            extra = c.normalize([raw_rows[k] for k in missing])
            extra[label_col] = [SEP.join(labels.get(k, [])) for k in missing]
            extra[code_col] = [SEP.join(codes.get(k, [])) for k in missing]
            extra = extra.reindex(columns=base.columns).fillna("")
            base = pd.concat([base, extra], ignore_index=True)
            print(f"[info] 维度结果中有 {len(missing)} 个商品不在主 CSV，已补入（建议择机 --force 重跑全量）")

        try:
            base.to_csv(c.csv_path, index=False, encoding=ENCODING)
            target = c.csv_path
        except PermissionError:
            # 多半是 CSV 正被 Excel 打开着，改写到副本，别让已抓到的数据白跑
            target = c.data_dir / f"{c.site}_products_with_dims.csv"
            base.to_csv(target, index=False, encoding=ENCODING)
            print(f"[warn] 主 CSV 被占用（可能正用 Excel 打开），已改写到 {target}")
            print("       关闭后重跑本命令即可写回主 CSV")

        hit = sum(1 for k in base_keys if labels.get(k))
        print("-" * 52)
        print(f"{c.site}：维度列已写入 {target}")
        print(f"  新增列 {label_col}（{c.dim_label} 中文标签，多值用「{SEP}」连接）、{code_col}（筛选传值）")
        print(f"  命中维度的商品 {hit}/{len(base_keys)} 条，未命中 {len(base_keys) - hit} 条（该商品未挂任何维度）")
