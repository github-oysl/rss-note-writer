# ACCEPTANCE | ck_compare 数据量一致性校验脚本

本验收指南说明如何在本地验证脚本功能与行为。

## 环境前提
- Windows 环境已安装并可调用 `clickhouse-client`，或提供其完整路径。
- 两端 ClickHouse 可访问，且存在目标表与 `metricTime` 字段。

## 基本用法
```powershell
python ck_compare.py \
  --src1-host 10.0.0.11 --src1-port 9000 --src1-db default --src1-user default --src1-password ***** \
  --src2-host 10.0.0.22 --src2-port 9000 --src2-db default --src2-user default --src2-password ***** \
  --table db.table \
  --start "2025-11-01" --end "2025-11-07" \
  --format both
```

## 验收场景
1. 总量一致：
   - 期望：退出码 0；文本与 JSON 显示 `equal: true`；不生成差异 CSV。
2. 总量不一致（区间 ≥ 1 分钟）：
   - 期望：退出码 2；文本与 JSON 显示 `equal: false`；生成分钟级差异 CSV，列为 `metricTime, src_count, dst_count`，仅包含存在差异的分钟。
3. 总量不一致（区间 == 1 分钟）：
   - 期望：退出码 2；生成秒级差异 CSV（同样仅包含差异秒）。
4. 错误场景：
   - 连接/认证失败、表不存在或字段缺失等情况，脚本打印错误并退出码 1。

## 可选参数
- `--client-bin`: 指定 `clickhouse-client` 的路径。
- `--csv-out`: 指定差异 CSV 文件路径；不指定则自动生成 `ck_diff_{db_table}_{granularity}_{start}_{end}.csv`。
- `--verbose`: 打印执行的具体命令（便于排查）。
- `--format`: `text` / `json` / `both`（默认 `both`）。

## 注意事项
- 时间区间采用 `[start, end)`；请根据服务器时区传入时间字符串。
- `--table` 必须为显式 `db.table`。
- 差异 CSV 仅在存在差异时生成；无差异不生成文件。