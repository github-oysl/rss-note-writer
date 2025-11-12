#!/usr/bin/env python3
"""
ck_compare.py

一个可直接执行的脚本：对比两个不同 ClickHouse 数据源在指定时间区间内、同名表（显式 `db.table`）的数据量是否一致。

特性与约束：
- 仅使用 Python 标准库与本机 `clickhouse-client` 执行查询。
- 时间区间采用左闭右开 `[start, end)`，时区以服务器时区为准。
- 当区间恰为 1 分钟（60 秒）时，进行“秒级”差异对比并生成秒级差异 CSV；否则进行分钟级差异对比。
- 差异 CSV 仅在发现差异时生成，列为：`metricTime, src_count, dst_count`。
  
退出码约定：
- 0：两端总量一致
- 2：两端总量不一致（已输出差异 CSV，若存在差异）
- 1：执行错误（参数/连接/查询失败等）
"""

import argparse
import csv
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    返回：argparse.Namespace 包含两端连接信息、表名、时间区间、输出格式与 CSV 输出路径等。
    """
    parser = argparse.ArgumentParser(
        description="对比两端 ClickHouse 同名表在指定区间的 count(*) 是否一致；必要时输出差异 CSV",
    )

    # 通用设置
    parser.add_argument("--client-bin", default="clickhouse-client", help="clickhouse-client 可执行路径")
    parser.add_argument("--format", choices=["text", "json", "both"], default="both", help="终端输出格式")
    parser.add_argument("--csv-out", default=None, help="差异 CSV 输出路径（不指定则自动生成）")
    parser.add_argument("--verbose", action="store_true", help="打印更多调试信息")

    # 源侧连接
    parser.add_argument("--src1-host", required=True)
    parser.add_argument("--src1-port", type=int, default=9000)
    parser.add_argument("--src1-db", default="default")
    parser.add_argument("--src1-user", default="default")
    parser.add_argument("--src1-password", default="")
    parser.add_argument("--src1-secure", action="store_true")

    # 目标侧连接
    parser.add_argument("--src2-host", required=True)
    parser.add_argument("--src2-port", type=int, default=9000)
    parser.add_argument("--src2-db", default="default")
    parser.add_argument("--src2-user", default="default")
    parser.add_argument("--src2-password", default="")
    parser.add_argument("--src2-secure", action="store_true")

    # 任务参数
    parser.add_argument("--table", required=True, help="显式库表名，例如 db.table")
    parser.add_argument("--start", required=True, help="开始时间（YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）")
    parser.add_argument("--end", required=True, help="结束时间（YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS），左闭右开")

    return parser.parse_args()


def parse_dt(s: str) -> datetime:
    """解析日期字符串为 datetime（不含时区），支持多种常用格式。

    支持：
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DDTHH:MM:SS
    """
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间字符串: {s}")


def sql_literal(s: str) -> str:
    """安全包装 SQL 字符串字面量，转义单引号。

    返回：适合拼接到 SQL 的 `'value'` 字面量字符串。
    """
    return "'" + s.replace("'", "''") + "'"


class Connection:
    """ClickHouse 连接参数的轻量封装。"""

    def __init__(self, host: str, port: int, db: str, user: str, password: str, secure: bool, client_bin: str):
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = password
        self.secure = secure
        self.client_bin = client_bin


def build_client_cmd(conn: Connection, query: str, fmt: str) -> List[str]:
    """构造 clickhouse-client 命令参数列表。

    参数：
    - conn: Connection 对象
    - query: 要执行的 SQL 语句
    - fmt: 输出格式（如 'CSV' 或 'CSVWithNames'）

    返回：用于 `subprocess.run` 的参数数组
    """
    cmd = [
        conn.client_bin,
        "--host",
        conn.host,
        "--port",
        str(conn.port),
        "--user",
        conn.user,
        "--password",
        conn.password,
        "--database",
        conn.db,
        "--query",
        query,
        "--format",
        fmt,
    ]
    if conn.secure:
        cmd.append("--secure")
    return cmd


def run_query(conn: Connection, query: str, fmt: str, verbose: bool = False) -> str:
    """执行查询并返回标准输出文本。

    异常：
    - FileNotFoundError：`clickhouse-client` 不存在
    - RuntimeError：返回码非零时抛出，消息中包含 stderr
    """
    cmd = build_client_cmd(conn, query, fmt)
    if verbose:
        print(f"[DEBUG] run: {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError("未找到 clickhouse-client，请确认已安装且 --client-bin 路径正确")
    if p.returncode != 0:
        raise RuntimeError(f"查询失败（{p.returncode}）: {p.stderr.strip()}")
    return p.stdout


def build_total_sql(table: str, start: str, end: str) -> str:
    """构造总量查询 SQL（应用 `[start, end)` 过滤）。"""
    return (
        f"SELECT count(*) AS cnt FROM {table} "
        f"WHERE metricTime >= parseDateTimeBestEffort({sql_literal(start)}) "
        f"AND   metricTime <  parseDateTimeBestEffort({sql_literal(end)})"
    )


def build_bucket_sql(table: str, start: str, end: str, granularity: str) -> str:
    """构造聚合桶查询 SQL。

    参数：
    - granularity: 'minute' 或 'second'
    """
    if granularity == "second":
        interval = "INTERVAL 1 SECOND"
    elif granularity == "minute":
        interval = "INTERVAL 1 MINUTE"
    else:
        raise ValueError("未知粒度，应为 'minute' 或 'second'")

    return (
        f"SELECT toStartOfInterval(metricTime, {interval}) AS bucket, count(*) AS cnt FROM {table} "
        f"WHERE metricTime >= parseDateTimeBestEffort({sql_literal(start)}) "
        f"AND   metricTime <  parseDateTimeBestEffort({sql_literal(end)}) "
        f"GROUP BY bucket ORDER BY bucket"
    )


def parse_total_csv(text: str) -> int:
    """解析总量查询 CSV 输出为整数计数。"""
    # 允许 CSV 或 CSVWithNames；若存在表头，跳过
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0
    # 如果首行可解析为数字，则直接返回；否则跳过首行作为表头
    try:
        return int(float(lines[0].split(",")[0]))
    except ValueError:
        # 跳过表头，读取下一行
        if len(lines) < 2:
            raise ValueError("总量查询输出异常：缺少数据行")
        return int(float(lines[1].split(",")[0]))


def parse_bucket_csv(text: str) -> Dict[str, int]:
    """解析桶查询 CSVWithNames 输出为 {bucket -> count} 映射。

    假设列名为 `bucket,cnt`，`bucket` 为 `YYYY-MM-DD HH:MM:SS` 字符串。
    """
    rows = []
    for row in csv.reader(text.splitlines()):
        if not row:
            continue
        rows.append(row)
    if not rows:
        return {}
    header = rows[0]
    # 判断是否包含表头
    start_idx = 0
    if header and (header[0].lower() == "bucket" or header[0].lower() == "metricTime"):
        start_idx = 1
    out: Dict[str, int] = {}
    for r in rows[start_idx:]:
        # 兼容可能的空行或不足列
        if len(r) < 2:
            continue
        bucket = r[0].strip()
        try:
            cnt = int(float(r[1]))
        except ValueError:
            # 若第一列是表头则跳过
            continue
        out[bucket] = cnt
    return out


def diff_maps(src: Dict[str, int], dst: Dict[str, int]) -> List[Tuple[str, int, int]]:
    """对齐桶集合并返回差异项列表。

    返回：[(bucket, src_cnt, dst_cnt)] 仅包含 src_cnt != dst_cnt 的条目。
    """
    keys = set(src.keys()) | set(dst.keys())
    diff: List[Tuple[str, int, int]] = []
    for k in sorted(keys):
        s = src.get(k, 0)
        d = dst.get(k, 0)
        if s != d:
            diff.append((k, s, d))
    return diff 


def write_csv(rows: List[Tuple[str, int, int]], path: Path) -> None:
    """写出差异 CSV 文件，列为 metricTime, src_count, dst_count。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metricTime", "src_count", "dst_count"])
        for r in rows:
            w.writerow(list(r))


def default_csv_name(table: str, start: str, end: str, granularity: str) -> Path:
    """生成差异 CSV 的默认文件名。"""
    safe_table = table.replace(".", "_")
    start_s = start.replace(":", "-").replace(" ", "T")
    end_s = end.replace(":", "-").replace(" ", "T")
    fname = f"ck_diff_{safe_table}_{granularity}_{start_s}_{end_s}.csv"
    return Path(fname)


def main() -> int:
    """主流程：解析参数、查询两端总量、必要时输出差异。

    返回：退出码（0/2/1）
    """
    args = parse_args()

    # 参数合法性与区间长度判断
    try:
        dt_start = parse_dt(args.start)
        dt_end = parse_dt(args.end)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1
    if dt_start >= dt_end:
        print("[ERROR] 开始时间必须早于结束时间")
        return 1

    interval_seconds = int((dt_end - dt_start).total_seconds())
    granularity = "second" if interval_seconds == 60 else "minute"

    # 构造连接信息
    src_conn = Connection(
        host=args.src1_host,
        port=args.src1_port,
        db=args.src1_db,
        user=args.src1_user,
        password=args.src1_password,
        secure=args.src1_secure,
        client_bin=args.client_bin,
    )
    dst_conn = Connection(
        host=args.src2_host,
        port=args.src2_port,
        db=args.src2_db,
        user=args.src2_user,
        password=args.src2_password,
        secure=args.src2_secure,
        client_bin=args.client_bin,
    )

    table = args.table
    # 简单校验显式 db.table
    if "." not in table:
        print("[ERROR] --table 必须为显式库表，例如 db.table")
        return 1

    # 总量查询
    sql_total = build_total_sql(table, args.start, args.end)
    try:
        src_total_text = run_query(src_conn, sql_total, fmt="CSV", verbose=args.verbose)
        dst_total_text = run_query(dst_conn, sql_total, fmt="CSV", verbose=args.verbose)
        src_total = parse_total_csv(src_total_text)
        dst_total = parse_total_csv(dst_total_text)
    except Exception as e:
        print(f"[ERROR] 总量查询失败：{e}")
        return 1

    equal = src_total == dst_total

    # 差异输出（仅在不一致时）
    diff_rows: List[Tuple[str, int, int]] = []
    csv_path: Optional[Path] = None
    if not equal:
        sql_bucket = build_bucket_sql(table, args.start, args.end, granularity=granularity)
        try:
            src_buckets_text = run_query(src_conn, sql_bucket, fmt="CSVWithNames", verbose=args.verbose)
            dst_buckets_text = run_query(dst_conn, sql_bucket, fmt="CSVWithNames", verbose=args.verbose)
            src_map = parse_bucket_csv(src_buckets_text)
            dst_map = parse_bucket_csv(dst_buckets_text)
            diff_rows = diff_maps(src_map, dst_map)
        except Exception as e:
            print(f"[ERROR] 差异明细查询失败：{e}")
            return 1

        if diff_rows:
            csv_path = Path(args.csv_out) if args.csv_out else default_csv_name(table, args.start, args.end, granularity)
            try:
                write_csv(diff_rows, csv_path)
            except Exception as e:
                print(f"[ERROR] 写出差异 CSV 失败：{e}")
                return 1

    # 输出
    summary = {
        "src_total": src_total,
        "dst_total": dst_total,
        "equal": equal,
        "granularity": granularity,
        "csv_path": str(csv_path) if csv_path else None,
        "diff_bucket_count": len(diff_rows),
    }

    if args.format in ("text", "both"):
        print("==== ck_compare summary ====")
        print(f"src_total: {src_total}")
        print(f"dst_total: {dst_total}")
        print(f"equal    : {equal}")
        print(f"granularity: {granularity}")
        if csv_path:
            print(f"diff csv : {csv_path}")
        if not equal and diff_rows:
            # 打印前若干条差异示例
            print("-- diff samples (up to 5) --")
            for b, s, d in diff_rows[:5]:
                print(f"{b} | src={s} dst={d}")

    if args.format in ("json", "both"):
        print(json.dumps(summary, ensure_ascii=False))

    return 0 if equal else 2


if __name__ == "__main__":
    sys.exit(main())