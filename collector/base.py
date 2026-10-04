"""采集器抽象基类

通用的采集流程（限速 → 请求 → 解析 → 去重 → 落盘 → 记进度 → 熔断判定）在这里固化。
新增一个交易所时，只需继承 BaseCollector 并实现两个方法：

    build_request(page)  —— 这一页该怎么发
    parse(payload)       —— 响应怎么读

其余（断点续传、熔断、CSV）全部继承。
"""

from __future__ import annotations

import abc
from pathlib import Path

import pandas as pd

from .client import PoliteClient
from .models import CircuitBroken, PageRequest, PageResult, make_key
from .storage import CsvSink, Progress

# 多值维度的分隔符。不能用「、」：维度名自带顿号（农、林、牧、渔业 / 卫生和社会工作 等），
# 会和分隔符混在一起分不清是几个维度。竖线在标签里不可能出现。
DIM_SEP = "|"


class BaseCollector(abc.ABC):
    # ---- 子类必须提供
    site: str = ""  # 站点标识，决定 CSV / 进度文件名

    # ---- 子类按需覆盖
    page_size: int = 100  # 每页条数，按站点实际上限设置
    # 去重主键字段组合。注意不是所有站点都有可靠唯一 id，
    # 上海站的 id 由各来源系统生成、全局会碰撞，必须用多字段组合
    key_fields: tuple[str, ...] = ()
    success_code: int | None = 0  # 业务成功码（北京 0，上海 200）
    headers: dict[str, str] = {}

    sleep_range: tuple[float, float] = (1.0, 2.0)  # 页间限速（秒）
    max_retry: int = 3
    max_consecutive_fail: int = 3
    timeout: float = 30
    verify: bool = True  # 少数站点证书链不完整，需要关掉校验

    # 单站点采集条数上限。个别站点库里数据极多（如广东 11 万条），
    # 全量拉取耗时过长且没必要，统一封顶；需要更多时可传 --max-rows 覆盖，
    # 传 0 表示不限制。
    max_rows: int = 20000

    # ---- 维度采集（列表接口不回显行业字段的站点才需要配）
    # 北京、福建、海南三家的列表返回里没有行业字段，拿不到商品归属，
    # 只能按维度逐个筛选再反推。配了 dimensions 的站点会在全量采集后自动跑一遍。
    dim_field: str = ""  # 列表接口的筛选字段名，如 goodsArea
    dim_label: str = ""  # 页面上的维度名，如「应用领域」
    dim_output_column: str = ""  # 写进 CSV 的列名，另会自动加一列 <列名>_code
    dimensions: tuple[tuple[str, str], ...] = ()  # (筛选传值, 中文标签)

    # ---- 维度编码反查（列表回显中文名、但不回显编码的站点才需要配）
    # 郑州、贵阳的列表只给维度名称（sceneName / sectors_name），编码列恒空，
    # 只能拿名称去查站点自己的维度字典，补出一列编码。
    dim_echo_column: str = ""  # 列表回显的维度名称列，多值用逗号分隔
    dim_code_column: str = ""  # 要补出来的编码列名，多值用 DIM_SEP 连接
    dim_name_to_code: dict[str, str] = {}  # {维度名称: 筛选传值}

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parent.parent
        self.data_dir = self.root / "data"
        self.state_dir = self.root / "state"
        self.csv_path = self.data_dir / f"{self.site}_products.csv"
        self.state_path = self.state_dir / f"{self.site}_state.json"
        self.dim_filter: dict | None = None  # 当前生效的维度筛选条件

    # ---------------------------------------------------------- 子类实现

    @abc.abstractmethod
    def build_request(self, page: int) -> PageRequest:
        """构造第 page 页的请求。"""

    @abc.abstractmethod
    def parse(self, payload: dict) -> PageResult:
        """把响应 JSON 解析成统一结果；业务码异常时抛 RuntimeError。"""

    # ---------------------------------------------------------- 可选覆盖

    def normalize(self, rows: list[dict]) -> pd.DataFrame:
        """默认把 list 字段拼成顿号分隔、压平换行；有特殊需求可覆盖。"""
        df = pd.json_normalize(rows)
        # 不要用 dtype != object 过滤：pandas 3.x 纯字符串列是 str dtype 而非 object，
        # 那样会把所有文本列跳过，导致换行压平失效
        for col in df.columns:
            df[col] = df[col].apply(self._flatten)
        return self._add_dim_code(df)

    def _add_dim_code(self, df: pd.DataFrame) -> pd.DataFrame:
        """把列表回显的维度中文名翻译成筛选传值，补一列编码。

        配了 dim_echo_column / dim_code_column / dim_name_to_code 才生效；
        查不到的名称会被跳过（保留为空），不会把脏数据写进去。
        """
        if not (self.dim_echo_column and self.dim_code_column and self.dim_name_to_code):
            return df
        if self.dim_echo_column not in df.columns:
            return df
        df[self.dim_code_column] = df[self.dim_echo_column].apply(self._lookup_codes)
        return df

    def _lookup_codes(self, value) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        codes: list[str] = []
        for name in value.split(","):
            code = self.dim_name_to_code.get(name.strip())
            if code and code not in codes:
                codes.append(code)
        return DIM_SEP.join(codes)

    @staticmethod
    def _flatten(value):
        if isinstance(value, list):
            return "、".join(str(v) for v in value)
        if isinstance(value, str):
            # 除了 \r\n 还要处理 Unicode 行分隔符，否则会撑破 CSV 行结构
            for ch in ("\r", "\n", "\u2028", "\u2029", "\x0b", "\x0c"):
                value = value.replace(ch, " ")
            return value.strip()
        return value

    def apply_dimension(self, code: str | None) -> None:
        """把维度筛选条件注入后续请求；传 None 表示清空（回到全量）。"""
        self.dim_filter = None if code is None else self._dim_payload(code)

    def _dim_payload(self, code: str) -> dict:
        return {self.dim_field: code}  # 北京是数组，会覆盖本方法

    def check_success(self, payload: dict) -> None:
        """校验业务码；上海是 200、北京是 0，由 success_code 控制。"""
        if self.success_code is None:
            return
        code = payload.get("code")
        if code not in (self.success_code, str(self.success_code)):
            raise RuntimeError(
                f"业务码异常 code={code} message={payload.get('message')}"
            )

    # ---------------------------------------------------------- 主流程

    def run(
        self,
        force: bool = False,
        max_pages: int = 0,
        max_rows: int | None = None,
    ) -> int:
        # 显式传值就用传的（0 表示不限制），没传则用类上的默认上限
        limit = self.max_rows if max_rows is None else max_rows

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        progress = Progress.load(self.state_path)
        progress.site = self.site

        if force:
            progress.reset()
            if self.csv_path.exists():
                self.csv_path.unlink()
            print(f"[info] --force 已清空 {self.site} 进度，从头采集")

        if progress.finished:
            print(
                f"[skip] {self.site} 上次已采集完成，共 {progress.fetched_rows} 条"
                f" → {self.csv_path}\n       需要重新采集请加 --force"
            )
            return 0

        sink = CsvSink(self.csv_path, progress.columns)
        seen = sink.seen_keys(self.key_fields, make_key)
        row_count = sink.row_count()  # 已落盘行数，断点续传时接着数

        start_page = max(1, progress.next_page)
        if start_page > 1:
            print(f"[resume] {self.site} 从第 {start_page} 页继续，已落盘 {len(seen)} 条")

        consecutive_fail = 0
        page = start_page
        prev_first_id = None
        total = progress.total
        reached_end = False
        limited = False

        with PoliteClient(
            headers=self.headers,
            timeout=self.timeout,
            sleep_range=self.sleep_range,
            max_retry=self.max_retry,
            verify=self.verify,
        ) as client:
            while True:
                if max_pages and (page - start_page) >= max_pages:
                    print(f"[stop] 已达到 --max-pages {max_pages} 限制")
                    break
                if limit and row_count >= limit:
                    limited = True
                    print(f"[stop] 已达到采集上限 {limit} 条")
                    break

                # ---- 限速
                client.wait()

                # ---- 请求 + 指数退避重试
                payload = None
                for attempt in range(1, self.max_retry + 1):
                    try:
                        req = self.build_request(page)
                        payload = client.request(req)
                        self.check_success(payload)
                        consecutive_fail = 0
                        break
                    except CircuitBroken as exc:
                        print(f"\n[熔断] {self.site} 第 {page} 页：{exc}")
                        raise
                    except Exception as exc:
                        print(
                            f"  [retry {attempt}/{self.max_retry}] "
                            f"{self.site} 第 {page} 页失败：{exc}"
                        )
                        if attempt < self.max_retry:
                            client.wait()

                if payload is None:
                    consecutive_fail += 1
                    print(f"  [fail] 第 {page} 页连续 {self.max_retry} 次失败")
                    if consecutive_fail >= self.max_consecutive_fail:
                        print(f"\n[熔断] 连续 {consecutive_fail} 页失败，停止采集")
                        break
                    page += 1
                    progress.next_page = page
                    progress.save(self.state_path)
                    continue

                # ---- 解析
                result = self.parse(payload)
                total = result.total if result.total is not None else total

                # ---- 分页失效判定：页码回显不符
                if result.page_echo is not None and result.page_echo != page:
                    print(
                        f"\n[熔断] 分页失效：请求第 {page} 页但回显 {result.page_echo}，"
                        f"请确认分页参数名是否正确"
                    )
                    break

                # ---- 空页 = 抓完
                if not result.rows:
                    reached_end = True
                    print(f"\n[done] 第 {page} 页返回空，采集结束")
                    break

                # ---- 分页失效兜底：相邻两页首条完全相同
                if self.key_fields:
                    first_key = make_key(result.rows[0], self.key_fields)
                    if first_key == prev_first_id:
                        print(f"\n[熔断] 第 {page} 页与上一页首条重复，分页可能失效")
                        break
                    prev_first_id = first_key

                # ---- 去重 + 落盘
                if self.key_fields:
                    fresh = [
                        r for r in result.rows
                        if make_key(r, self.key_fields) not in seen
                    ]
                    seen.update(make_key(r, self.key_fields) for r in result.rows)
                else:
                    fresh = result.rows
                if fresh:
                    sink.append(self.normalize(fresh))
                row_count += len(fresh)

                progress.total = total
                progress.fetched_rows = row_count
                progress.next_page = page + 1
                progress.columns = sink.columns
                progress.save(self.state_path)

                print(
                    f"  第 {page:>3} 页  本页 {len(result.rows):>3} 条 "
                    f"(新增 {len(fresh)})  累计 {row_count}/{total}",
                    flush=True,
                )
                page += 1

        # 空页终止才算真正抓完；不能用 len(seen) >= total 判定，
        # 因为后端索引可能含重复主键，去重后条数会小于 total
        progress.total = total
        # 空页终止、或主动设了条数上限，都算正常完成
        progress.finished = (reached_end or limited) and not max_pages
        progress.save(self.state_path)

        print("-" * 52)
        print(f"{self.site}：累计 {row_count} 条 / 总库 {total} 条")
        if limited:
            print(f"（已达单站点采集上限 {limit} 条，非全量）")
        elif total and row_count < total:
            print(f"注意：少 {total - row_count} 条，是重复记录被去重或深分页漂移，非漏抓")
        print(f"CSV   → {self.csv_path}")
        print(f"进度  → {self.state_path}")
        if not progress.finished:
            print("未完成，下次直接重跑本命令即可续传")
        return 0

    # ---------------------------------------------------------- 全量 + 维度

    def run_all(
        self,
        force: bool = False,
        max_pages: int = 0,
        max_rows: int | None = None,
        skip_dims: bool = False,
        dims_only: bool = False,
        dim_max_pages: int = 0,
    ) -> int:
        """全量采集 →（若配了维度清单）按维度分别采集 → 合并维度列。

        dims_only=True 时跳过全量，只跑维度并合并（全量已完成时用它）。
        """
        if not dims_only:
            self.run(force=force, max_pages=max_pages, max_rows=max_rows)
        if skip_dims or not self.dimensions:
            return 0
        from .dims import DimensionRunner

        return DimensionRunner(self).run(force=force, max_pages=dim_max_pages)
