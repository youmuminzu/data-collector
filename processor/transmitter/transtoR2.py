"""把 processor/processeddata 下的产物上传到 Cloudflare R2。

processor 的最后一个环节：清洗产出 CSV → 推到对象存储 → 回写上传时间。

用法（都在项目根目录跑）：
    uv run python processor/transmitter/transtoR2.py                     # 预览，不上传
    uv run python processor/transmitter/transtoR2.py market.json         # 只传这一个
    uv run python processor/transmitter/transtoR2.py --all               # 传全部产出
    uv run python processor/transmitter/transtoR2.py --all --include-old # 连 _old 也传
    uv run python processor/transmitter/transtoR2.py --all --prefix ""   # 放桶根目录
    uv run python processor/transmitter/transtoR2.py --all --force       # 忽略跳过

**什么时候才传**（核心规则）：比对 `updated_at` 与 `upload_at` 两个时间——
`upload_at` 为空（没传过），或 `updated_at` 晚于 `upload_at`（重新清洗过），才上传。
两者都没变就跳过，所以重复跑基本是零流量。

**不查远端、也不做「远端缺失就补传」**：别的程序消费完会删掉 R2 上的文件，
那是正常的下游流程，不是异常。一旦补传，它们就会反复拿到同一批数据反复处理。
要重新推一份，靠改 `updated_at`（重跑清洗）或 `--force`。

上传顺序是 **CSV 先、json 后**：json 要记本次上传时间，得等 CSV 传完才知道，
写完再传 json，远端和本地才是同一份内容。
被跳过的文件不会改写时间戳——没真传就不该记。

为什么默认前缀是 data_product_files/：桶就是按这个目录交付给下游的。
为什么不带参数时只预览：上传是外部写操作，先看清楚清单再动手。
为什么默认跳过 _old.csv：那是留给本地 diff 比对增量的，不是交付物。

配置读同目录的 R2keys.conf（已加入 .gitignore，密钥不入库）；
同名环境变量优先级更高，方便在服务器上不落盘地注入：
    R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET_NAME / R2_ENDPOINT_URL
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # processor/transmitter/ → 项目根
sys.path.insert(0, str(ROOT))

CONF_FILE = Path(__file__).resolve().parent / "R2keys.conf"
SRC_DIR = ROOT / "processor" / "processeddata"
DEFAULT_PREFIX = "data_product_files/"

# conf 里的键 → 环境变量名
ENV_KEYS = {
    "ACCOUNT_ID": "R2_ACCOUNT_ID",
    "ACCESS_KEY_ID": "R2_ACCESS_KEY_ID",
    "SECRET_ACCESS_KEY": "R2_SECRET_ACCESS_KEY",
    "BUCKET_NAME": "R2_BUCKET_NAME",
    "ENDPOINT_URL": "R2_ENDPOINT_URL",
}
REQUIRED = ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "BUCKET_NAME", "ENDPOINT_URL")

# 交付物清单：3 个字典/索引 json + 每站本次产出的 _new.csv
# 顺序即上传顺序：CSV 先传，json 垫后（写完时间戳再传，远端才和本地一致）
DICT_JSON = ("market.json", "category.json")          # 顶层带 upload_at 字段
INDEX_JSON = "product_files.json"                      # 每个条目带 upload_at 字段
DELIVER = (*DICT_JSON, INDEX_JSON)


def load_config(conf_path: Path = CONF_FILE) -> dict[str, str]:
    """解析 KEY = "VALUE" 形式的配置文件，环境变量优先。"""
    cfg: dict[str, str] = {}
    if conf_path.exists():
        for line in conf_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                cfg[key] = value
    for key, env in ENV_KEYS.items():
        env_value = os.environ.get(env)
        if env_value:
            cfg[key] = env_value
    missing = [k for k in REQUIRED if not cfg.get(k)]
    if missing:
        raise SystemExit(f"配置缺少必需的键：{', '.join(missing)}（检查 {conf_path.name}）")
    return cfg


def build_client(cfg: dict[str, str]):
    """R2 走的是 S3 兼容接口，region 固定 auto。"""
    import boto3
    from botocore.config import Config

    return boto3.session.Session().client(
        "s3",
        endpoint_url=cfg["ENDPOINT_URL"],
        aws_access_key_id=cfg["ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(
            retries={"max_attempts": 5, "mode": "standard"},
            connect_timeout=10,
            read_timeout=120,
        ),
    )


def collect(include_old: bool) -> list[Path]:
    """列出 processeddata 下的交付物：CSV 在前，json 垫后。"""
    files: list[Path] = sorted(SRC_DIR.glob("*_new.csv"))
    if include_old:
        files.extend(sorted(SRC_DIR.glob("*_old.csv")))
    files.extend(p for p in (SRC_DIR / n for n in DELIVER) if p.exists())
    return files


# ── 上传时间回写 ──────────────────────────────────────────────────────


def _load(path: Path, quiet: bool = False):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if not quiet:
            print(f"  ! 读取 {path.name} 失败：{exc}")
        return None


def _dump(path: Path, data) -> bool:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError as exc:
        print(f"  ! 写入 {path.name} 失败（被 Excel 占用？）：{exc}")
        return False


def stamped_bytes(path: Path, ts: str) -> bytes | None:
    """字典类 json 填好 upload_at 后的完整内容，本地文件不动。"""
    data = _load(path)
    if not isinstance(data, dict):
        print(f"  ! {path.name} 不是对象结构，跳过写时间戳")
        return None
    data["upload_at"] = ts
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def stamp_dict_file(path: Path, ts: str) -> bool:
    """只写本地：给 market.json / category.json 填顶层 upload_at。"""
    body = stamped_bytes(path, ts)
    if body is None:
        return False
    try:
        path.write_bytes(body)
        return True
    except OSError as exc:
        print(f"  ! 写入 {path.name} 失败（被 Excel 占用？）：{exc}")
        return False


def index_entry(file_name: str) -> dict | None:
    """在 product_files.json 里找某个文件的条目。"""
    path = SRC_DIR / INDEX_JSON
    if not path.exists():
        return None
    data = _load(path, quiet=True)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("file_name") == file_name:
                return item
    return None


def stamp_index(file_name: str, ts: str) -> bool:
    """product_files.json：给刚传完的那个文件条目填 upload_at。"""
    path = SRC_DIR / INDEX_JSON
    data = _load(path)
    if not isinstance(data, list):
        print(f"  ! {INDEX_JSON} 不是数组结构，跳过写时间戳")
        return False
    hit = False
    for item in data:
        if isinstance(item, dict) and item.get("file_name") == file_name:
            item["upload_at"] = ts
            hit = True
    if not hit:
        print(f"  ! {INDEX_JSON} 里没有 {file_name} 的条目，未记录上传时间")
        return False
    return _dump(path, data)


# ── 要不要传：看 updated_at 与 upload_at ──────────────────────────────


def _parse(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def read_stamps(path: Path) -> tuple[str | None, str | None]:
    """取某文件的 (updated_at, upload_at)。

    字典表（market/category）读自己的顶层字段；
    CSV 没有字段，去 product_files.json 里按 file_name 找。
    """
    if path.name in DICT_JSON:
        data = _load(path, quiet=True)
        if isinstance(data, dict):
            return data.get("updated_at"), data.get("upload_at")
        return None, None
    entry = index_entry(path.name)
    if entry:
        return entry.get("updated_at"), entry.get("upload_at")
    return None, None


def decide(path: Path, force: bool, index_dirty: bool) -> tuple[bool, str]:
    """判断要不要上传：upload_at 为空，或 updated_at 晚于 upload_at。"""
    if force:
        return True, "--force 强制重传"

    # 索引本身没有时间戳字段：本轮有文件更新过（内容已改）才传
    if path.name == INDEX_JSON:
        return (True, "本轮有文件更新") if index_dirty else (False, "索引内容无变化")

    updated, uploaded = read_stamps(path)
    if not uploaded:
        return True, "upload_at 为空（从未上传过）"
    if not updated:
        return True, "没有 updated_at，按未处理"

    u, p = _parse(updated), _parse(uploaded)
    if u is None or p is None:
        return True, f"时间格式异常 updated_at={updated} upload_at={uploaded}"
    if u > p:
        return True, f"已更新 {updated} > {uploaded}"
    return False, f"未更新 {updated} ≤ {uploaded}"


def content_type(path: Path) -> str:
    guess = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if guess.startswith("text/") or guess == "application/json":
        guess += "; charset=utf-8"
    return guess


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def upload(client, path: Path, bucket: str, prefix: str, stamp_ts: str | None = None):
    """上传单个文件。返回 (状态, 说明)。

    stamp_ts 只给字典类 json 用：先把 upload_at 填进要传的内容里再传，
    成功后才回写本地，这样远端和本地一致，传失败时本地时间戳不会乱。
    """
    key = f"{prefix}{path.name}"
    stamp_dict = stamp_ts is not None and path.name in DICT_JSON

    if stamp_dict:
        body = stamped_bytes(path, stamp_ts)
        if body is None:  # 读失败，退回传原文件
            body = path.read_bytes()
            stamp_dict = False
    else:
        body = path.read_bytes()
    size = len(body)

    started = time.perf_counter()
    try:
        client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type(path))
    except Exception as exc:  # noqa: BLE001
        return "失败", f"{type(exc).__name__}: {exc}"

    if stamp_dict:
        try:
            path.write_bytes(body)
        except OSError as exc:
            print(f"  ! {path.name} 已上传，但本地 upload_at 回写失败：{exc}")

    cost = time.perf_counter() - started
    speed = f" / {human(int(size / cost))}s" if size and cost > 0 else ""
    return "上传", f"{human(size)} / {cost:.1f}s{speed}"


def main() -> int:
    parser = argparse.ArgumentParser(description="上传 processeddata 产物到 Cloudflare R2")
    parser.add_argument("files", nargs="*", help="只上传这些文件（相对 processeddata 的文件名）")
    parser.add_argument("--all", action="store_true", help="上传全部产出")
    parser.add_argument("--include-old", action="store_true", help="连同 _old.csv 一起传")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"对象键前缀，默认 {DEFAULT_PREFIX}")
    parser.add_argument("--dry-run", action="store_true", help="只预览清单，不上传")
    parser.add_argument("--force", action="store_true", help="忽略时间判定，全部重传")
    args = parser.parse_args()

    cfg = load_config()
    bucket = cfg["BUCKET_NAME"]
    prefix = args.prefix

    # 决定要处理哪些文件
    if args.files:
        targets: list[Path] = []
        for name in args.files:
            p = SRC_DIR / name
            if not p.exists():
                print(f"找不到文件：{p}")
                return 1
            targets.append(p)
    elif args.all:
        targets = collect(args.include_old)
        if not targets:
            print(f"{SRC_DIR} 下没有可上传的产出")
            return 1
    else:
        # 不带参数就是预览
        args.dry_run = True
        targets = collect(args.include_old)

    total = sum(p.stat().st_size for p in targets)
    mode = "预览（未上传）" if args.dry_run else f"上传 → {cfg['ENDPOINT_URL']} / {bucket}"
    print(f"源文件目录：{SRC_DIR}")
    print(f"目标：{bucket}/{prefix}   {mode}")
    print(f"共 {len(targets)} 个文件，合计 {human(total)}")
    if args.dry_run:
        print("（确认无误后加 --all 真正上传，或指定单个文件名做验证）")
    print("-" * 74)
    print(f"{'文件':<34}{'大小':>10}  {'结果':<6}{'说明'}")
    print("-" * 74)

    client = None if args.dry_run else build_client(cfg)
    failed = 0
    uploaded = 0
    skipped = 0
    index_dirty = False   # 本轮是否改过 product_files.json
    for path in targets:
        size = path.stat().st_size
        need, reason = decide(path, args.force, index_dirty)

        if args.dry_run:
            status, detail = ("待传" if need else "跳过"), f"{reason} / 对象键 {prefix}{path.name}"
        elif not need:
            status, detail, skipped = "跳过", reason, skipped + 1
        else:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status, detail = upload(client, path, bucket, prefix, stamp_ts=ts)
            if status == "失败":
                failed += 1
            else:
                uploaded += 1
                # 只有真传了才记时间；CSV 写进索引，字典表已随内容一起传上去
                if path.suffix == ".csv":
                    if stamp_index(path.name, ts):
                        index_dirty = True
                        detail += f" / upload_at={ts}"
                elif path.name in DICT_JSON:
                    detail += f" / upload_at={ts}"
        print(f"{path.name:<34}{human(size):>10}  {status:<6}{detail}")

    print("-" * 74)
    if args.dry_run:
        print("预览结束，什么都没传。")
    else:
        print(f"上传 {uploaded} 个 / 跳过 {skipped} 个 / 失败 {failed} 个")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
