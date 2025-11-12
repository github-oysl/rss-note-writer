# ALIGNMENT | ck_compare 数据量一致性校验脚本

本文档用于对齐“两个不同 ClickHouse 数据源，同名表在指定时间区间内数据量是否一致”的需求、边界、技术约束与验收标准，为后续架构与实现提供清晰规范。

## 项目上下文分析
- 运行环境：Linux，本地已安装并可调用 `clickhouse-client`。
- 代码位置：`d:\CODE\python`，将新增可直接执行的 Python 脚本。
- 现有目录：`docs/ck_compare/` 已存在；可扩展 `config/` 以支持可选配置。
- 技术栈与约束：
  - 必须使用本机 `clickhouse-client` 执行查询。
  - 参数来源于脚本入参（支持命令行传参），可选读取配置文件或环境变量。
  - 仅比较同名表在时间过滤条件下的 `count(*)`，不做数据内容逐条对比。

## 原始需求
- 目标：查询两个不同的 ClickHouse（可配置）并对比同名表的数据量是否一致。
- 过滤：按日期字段 `metricTime` 过滤。
- 时间区间：作为脚本入参或配置项传入。
- 表名：作为脚本入参或配置项传入。
- 查询执行方式：直接使用本机 `clickhouse-client`。

## 边界确认（明确任务范围）
- 范围内：
  - 通过 `clickhouse-client` 分别在两端 CK 执行 `SELECT count(*)`，带上 `metricTime` 的区间过滤。
  - 输出两端的计数和是否一致的结论，提供可读的终端输出与机器可读（JSON）摘要，并把有差异的数据生成CSV文件，记录两边的数据量值。
  - 可通过命令行参数配置两端连接信息（主机、端口、数据库、用户名、密码、是否 SSL）。
  - 当计数不一致时返回非零退出码以便在 CI 或批处理脚本中使用。
- 范围外：
  - 不进行数据取样或逐条比对。
  - 不进行自动重试、断路器或复杂容灾逻辑。
  - 不创建或修改数据库/表结构；假定两端表结构已存在且 `metricTime` 字段存在。

## 需求理解（对现有项目的理解）
- 用户希望“开箱即用、可直接执行”，因此脚本将：
  - 仅依赖标准库与本机 `clickhouse-client`；无需第三方 Python 包。
  - 通过命令行参数即可完成所有配置；可选从 `.env` 或 `config/ck_compare.yaml` 读取默认值。
  - 提供清晰的使用示例与错误信息。

## 疑问澄清（存在歧义的地方）
1. 时间区间的闭包规则：是否采用 `[start, end)`（左闭右开）还是 `[start, end]`？
  A:是否采用 `[start, end)`（左闭右开）
2. 时间与时区：`metricTime` 的时区约定是什么（UTC/本地/服务器时区）？
  A:服务器时区
3. 表名是否包含数据库前缀（如 `db.table`），如果传入不包含是否默认使用连接的 `--database`？
  A:包含
4. 是否需要支持额外过滤条件（如分区字段、其他 where 条件）？
  A:不需要
5. 输出格式偏好：是否需要仅 JSON，或同时提供人类可读文本与 JSON？
  A:查询到差异的数据 需要保存到一个CSV文件中，行的数据包括 meticTime（精确到分钟） 源数据库数据量，目标数据库数据量
6. 失败策略：当两端任意一端查询失败（连接/认证/语法），是否直接退出并返回错误码 1？

## 智能决策策略（优先基于常识与行业经验的默认设定）
- 默认采用 `[start, end)`（左闭右开）时间区间，避免边界记录重复统计。
- 时间格式支持：`YYYY-MM-DD` 与 `YYYY-MM-DD HH:MM:SS`，内部不做时区换算，按服务器时区执行，后续可通过参数控制 `--timezone`（若实际需要）。
- 表名传入不带数据库前缀时，默认使用各自连接的 `--database`；若传入 `db.table` 则以显式表名为准。
- 输出同时包含文本与 JSON 摘要（便于人读与自动化）。
- 查询失败时立即退出并返回错误码 1，并打印详细错误说明。
- 当计数不一致时返回错误码 2；一致时返回 0。

## 参数规范（草案）
- 连接一：`--src1-host`、`--src1-port`、`--src1-db`、`--src1-user`、`--src1-password`、`--src1-secure`（布尔）。
- 连接二：`--src2-host`、`--src2-port`、`--src2-db`、`--src2-user`、`--src2-password`、`--src2-secure`（布尔）。
- 任务参数：`--table`、`--start`、`--end`、`--format`（`text`/`json`/`both`，默认 `both`）、`--verbose`（布尔）。
- 可选：`--config`（例如 `config/ck_compare.yaml`）与 `.env`（从环境读取缺省值）。

## 示例用法（草案）
```powershell
python ck_compare.py \
  --src1-host 10.0.0.11 --src1-port 9000 --src1-db default --src1-user default --src1-password ***** \
  --src2-host 10.0.0.22 --src2-port 9000 --src2-db default --src2-user default --src2-password ***** \
  --table events \
  --start "2025-11-01" --end "2025-11-07" \
  --format both
```

## 验收标准（可测试）
- 在具备 `clickhouse-client` 的环境中，脚本可直接运行；不依赖额外 Python 包。
- 正确执行两端 `count(*)` 查询并应用 `[start, end)` 时间过滤。
- 终端输出包含两端计数与一致性结论；`--format json` 输出 JSON 摘要。
- 一致返回码为 0，不一致为 2，错误为 1。
- 对常见异常（连接失败、认证失败、表不存在、字段不存在）有明确错误信息。

## 下一步
- 请确认上述对齐是否符合预期；如无异议，将进入架构阶段并产出 DESIGN 文档，随后实现脚本。