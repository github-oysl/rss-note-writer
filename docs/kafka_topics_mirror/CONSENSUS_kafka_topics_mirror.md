# CONSENSUS — kafka_topics_mirror

## 明确的需求描述
- 在目标 Kafka 集群上创建来源 Kafka 集群的“非内部” Topic，保持分区数、复制因子与显式 Topic 级配置的一致性；不迁移消息数据与消费者状态。
- 考虑网络隔离，导出与导入分别在不同服务器执行，通过离线清单文件对接。

## 验收标准
- 目标集群成功创建所有纳入范围的 Topic，分区数与复制因子与源一致（或在设定的 `rf-cap` 约束下合理降级）。
- 显式 Topic 配置同步到目标集群；对不可修改或不兼容配置进行跳过并记录。
- 脚本具备幂等性：已存在 Topic 默认不破坏，支持 `--skip-existing` 与 `--update-existing-configs` 控制。
- 提供 `--dry-run` 预览、详细日志与失败项汇总；导出/导入可在不同服务器独立执行。

## 技术实现方案与集成
- 脚本拆分：
  - 源端导出脚本 `export_kafka_topics.sh`：扫描 Topic 列表、过滤内部/系统 Topic，解析分区数、复制因子与显式配置，生成离线清单文件。
  - 目标端导入脚本 `import_kafka_topics.sh`：读取清单，检查存在性，批量创建 Topic 并追加显式配置，支持 `--rf-cap`、`--dry-run` 等。
- 优先使用 Kafka 官方 CLI：`kafka-topics.sh`、`kafka-configs.sh`；命令以 `--bootstrap-server` 方式兼容 Kafka 2.6.1。若需旧版 ZK 模式，将提供选项兼容。
- 集成约束：
  - 网络隔离：两脚本分别在源/目标服务器执行；清单文件经安全渠道传输。
  - 依赖工具：`bash`、`timeout`、`grep`、`awk`、`sed`；`jq` 为可选（仅在选择 JSON 清单格式时需要）。
  - 安全：不在脚本中写入敏感信息；凭证由环境/CLI 自行管理。

## 任务边界与限制
- 范围仅限 Topic 元信息与显式配置；不迁移消息数据、ACL、配额、消费者组偏移、分区副本精确分配。
- 默认排除内部/系统 Topic：以正则 `^(__|_).*` 与显式列表进行过滤。
- 不对已存在 Topic 执行破坏性操作（不缩分区、不降低复制因子），除非在创建阶段因 `rf-cap` 降级而生效于新建的 Topic。

## 关键决策点与当前取值（默认，可调整）
- 清单文件格式：
  - 采用“行式清单”：`<topic>|<partitions>|<rf>|<k=v,k2=v2>`（纯 Bash 解析，无额外依赖）。
  - 可切换为 JSON（需要 `jq`）（当前不启用）。
- 排除规则：
  - 正则：`^(__|_).*`。
  - 显式排除列表（默认）：`__consumer_offsets,__transaction_state,__cluster_metadata,__cluster_config,__producer_ids,_schemas,_confluent-metrics,__confluent.support.metrics,connect-configs,connect-offsets,connect-status`。
  - 额外排除：无（按你当前要求）。
- 复制因子策略：
  - `rf-cap` 暂未设置（不自动降级；如不可创建则提示失败并记录）。
  - 如需设置 `--rf-cap <N>`，当源 RF>N 时，为新建 Topic 降级到 N。
- 已存在 Topic 策略：
  - `--skip-existing` 跳过创建（按你要求）。
  - 不启用 `--update-existing-configs`（已存在 Topic 的配置不更新）。
- CLI 模式与版本兼容：默认 `--bootstrap-server`（Kafka 2.6.1 支持）；如确认旧版再启用 `--zookeeper` 分支。
- 并发与速率：默认串行创建（按你要求不并发）。
- Kafka `bin` 路径：在脚本顶部定义变量（例如 `KAFKA_BIN_DIR`），运行时可通过参数覆盖（例如 `--bin /opt/kafka/bin`）。
- 失败与容错：创建（带配置）失败则退化为仅创建基础信息，再 `kafka-configs.sh --alter` 追加配置；不兼容配置记录警告。

## 配置同步策略（明确）
- 导出端（源服务器）
  - 每个 Topic 执行：`kafka-topics.sh --bootstrap-server <SRC> --topic <t> --describe`，解析首行中的 `Configs:` 字段，仅收集“显式配置”键值（例如 `cleanup.policy=compact,retention.ms=604800000`）。
  - 清单文件行式格式：`<topic>|<partitions>|<rf>|<k=v,k2=v2>`，其中第四段为逗号分隔的配置集合，留空表示无显式配置。
- 导入端（目标服务器）
  - 创建阶段：对清单中的每个 `k=v`，以多个 `--config k=v` 的形式随创建命令传入：
    - `kafka-topics.sh --bootstrap-server <DEST> --create --topic <t> --partitions <N> --replication-factor <R> [--config k=v ...]`
  - 追加/校准阶段：若创建阶段某些配置未生效或需要显式追加，则执行：
    - `kafka-configs.sh --bootstrap-server <DEST> --entity-type topics --entity-name <t> --alter --add-config k=v,k2=v2`
  - 配置取舍：仅同步源端“显式配置”（来自 `Configs:` 字段），不写入默认值；跳过只读或不兼容项并记录；不处理集群级/只读参数。
- 已存在 Topic 时的策略（按你当前要求）
  - 仅执行存在性检查并跳过创建；不更新已存在 Topic 的配置（统一跳过）。

## 待确认的不确定性
1. 目标集群可承载的复制因子上限 `rf-cap`（是否需要设置降级）。
  A: 无需
2. 两端 Kafka `bin` 实际路径（例如 `/opt/kafka/bin`），是否具备 `timeout`；是否安装 `jq`（当前不需要）。
3. 是否有平台策略要求某些配置不允许修改（需列出清单以在导入时忽略）。
  A: 不需要 只追加白名单需要追加的配置，不追加全部配置，如retention.ms等

## 下一步
1. 你确认上述“默认取值”与“待确认项”，我将锁定本共识文档。
2. 进入架构阶段，输出 `DESIGN_kafka_topics_mirror.md`（架构图/数据流/接口契约）。
3. 进入原子化阶段，输出 `TASK_kafka_topics_mirror.md`（子任务、依赖与验收）。
4. 获批后实现导出/导入两脚本，附函数级注释与 `--dry-run`、日志能力，并提供使用指南。