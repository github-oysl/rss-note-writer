# ALIGNMENT — kafka_topics_mirror

## 项目上下文分析
- 环境与约束：源与目标 Kafka 集群可能网络不通，需在不同服务器分别执行“导出/导入”脚本，通过离线清单文件传递元数据。
- 技术栈与工具：优先使用 Kafka 自带 CLI（`kafka-topics.sh`、`kafka-configs.sh`）；可选工具 `timeout`、`grep`、`awk`、`sed`。如需 JSON 解析可使用 `jq`（若环境允许）。
- 目标范围：在目标集群创建源集群的“非内部” Topic，包含分区数、复制因子和显式 Topic 级配置；不迁移消息数据。
- 项目现状：仓库位于 Windows 开发环境；脚本将在 Linux 服务器上执行。已有 `docs/ck_compare` 无直接依赖本任务。

## 原始需求
在安装了 Kafka 的 Linux 系统上，获取当前 Kafka 的“非内部 Topic”信息，并在另一个 Kafka 上批量创建对应 Topic。考虑网络权限不通，导出与导入需拆分为不同脚本，在不同服务器运行。优先调用 `bin/kafka-topics.sh` 或其他 Kafka 官方命令行工具实现。

## 任务范围与边界确认
- 只处理“非内部/非系统” Topic。默认排除前缀为 `__` 或 `_` 的 Topic；显式排除常见系统 Topic（如 `__consumer_offsets`、`__transaction_state`、`_schemas`、`connect-*` 等）。
- 迁移的内容仅为基础元信息（分区数、复制因子）与显式配置（`cleanup.policy`、`retention.ms` 等）；不迁移消息数据、ACL、配额、消费者组状态、分区副本的精准分配。
- 兼容 Kafka 2.6/3.x（`--bootstrap-server`）。
- 目标集群的 broker 数量可能不同， 。
- 目标已存在 Topic 的处理：可选择跳过或只更新显式配置；不执行分区缩减或 RF 降级（避免破坏性操作）。

## 需求理解（对现有项目的理解）
- 我们将提供两套独立脚本：
  1) 导出脚本在源集群服务器上运行，扫描 Topic 列表、解析分区/复制因子/显式配置，生成离线“Topic 清单文件”。
  2) 导入脚本在目标集群服务器上运行，读取清单文件，按规则批量创建 Topic 并追加显式配置。
- 清单文件格式可选（详见“关键决策点”）：为兼容性与可维护性，优先使用不依赖额外解析器的行式格式（也可选 JSON + `jq`）。
- 强调可重复执行与可观测性：提供 `--dry-run` 查看将执行命令；日志明确记录成功/失败与跳过原因。

## 智能决策策略与初步决策
- 默认排除规则：正则 `^(__|_).*` + 显式排除列表（`__consumer_offsets,__transaction_state,__cluster_metadata,__cluster_config,__producer_ids,_schemas,_confluent-metrics,__confluent.support.metrics,connect-configs,connect-offsets,connect-status`）。
- 复制因子上限：提供 `--rf-cap`，当源 RF 大于目标可承载时自动降至上限（避免失败）。
- 已存在 Topic：默认跳过创建；可选 `--update-existing-configs` 更新显式配置（不改变分区数与 RF）。
- 兼容输出差异：`kafka-topics.sh --describe` 首行包含 `PartitionCount`、`ReplicationFactor`、`Configs`，脚本按多版本兼容解析。
- 异常与重试：创建失败时降级仅创建基础信息，再使用 `kafka-configs.sh --alter` 追加配置；仍失败则记录失败项以便人工处理。

## 结构化问题清单（需确认）
1. Kafka 版本与模式：源/目标集群是否为 KRaft 模式？版本号大致范围（2.x/3.x），是否仅支持 `--bootstrap-server`？
 A : 版本号 2.6.1 
2. 清单文件格式偏好：
   - 选项 B：行式清单（示例：`<topic>|<partitions>|<rf>|<k=v,k2=v2>`），导入端用 `bash` 原生解析，无额外依赖。
3. 排除清单：除默认规则外，是否还需排除 `connect-*`、`_schemas`、Confluent Metrics 等？请补充任何自定义前缀或具体 Topic。 
  A: 不需要
4. 复制因子策略：目标集群 broker 数量与期望上限（`rf-cap`）是多少？必要时是否允许降级复制因子？
5. 已存在 Topic 策略：是否启用 `--update-existing-configs` 同步显式配置？如目标配置与源冲突，倾向覆盖还是跳过？
  A: 跳过
6. 执行入口路径：两端服务器上 Kafka `bin` 的实际路径（例如 `/opt/kafka/bin`），是否有 `timeout` 或 `jq` 可用？
  A: 不确定 bin的实际路径做成变量 放在脚本开头
7. 内部/只读配置：是否有必须保留或禁止修改的配置项（例如 `min.insync.replicas`、只读参数）？
8. 并发与速率：是否允许并发创建（默认串行，稳定优先）？
  A: 不允许，topic不多 默认串行

## 初步技术方案（导出/导入拆分）
- 导出脚本（源服务器）：`export_kafka_topics.sh`
  - 扫描源集群 Topic 列表，按排除规则过滤。
  - 对每个 Topic 执行 `--describe`，解析分区数、复制因子和显式配置。
  - 生成清单文件：优先行式格式（无外部解析依赖）；可选 JSON。
  - 产出：`topics_manifest.lst`（或 `topics_manifest.json`）以及日志文件。
- 导入脚本（目标服务器）：`import_kafka_topics.sh`
  - 读取清单文件；对每个 Topic 检查是否存在。
  - 不存在则创建：`--create --partitions <N> --replication-factor <R>`，必要时应用 `--config` 参数。
  - 已存在且启用配置更新时：使用 `kafka-configs.sh --alter --add-config` 追加显式配置。
  - 提供 `--rf-cap`、`--dry-run`、`--skip-existing`、`--update-existing-configs` 等控制参数。

## 验收标准
- 在目标集群成功创建所有源集群的“非内部 Topic”，分区数与复制因子一致（或按约定降级至 `rf-cap`）。
- 显式 Topic 配置成功同步（不可写或不支持项允许跳过并记录）。
- 提供 `--dry-run` 预览输出与完整日志，脚本可重复执行、具备幂等性（已存在时不破坏）。
- 导出与导入脚本在不同服务器独立运行，靠离线清单文件完成对接。

## 集成与约束
- 仅依赖 Kafka 官方 CLI；尽量避免第三方工具依赖（`jq` 可选）。
- 不执行数据迁移与消费者状态迁移；不变更分区数量和 RF（除非 `rf-cap` 降级）。
- 如遇版本差异或只读配置导致失败，记录并提示人工处理。

## 风险与缓解
- 复制因子不匹配：通过 `--rf-cap` 降级；必要时脚本提示需要更多 broker。
- 配置不兼容：在创建后分步 `--alter` 追加，失败项记录并汇总。
- 网络与权限：脚本在各自服务器执行；清单文件通过安全渠道传输。
- CLI 输出差异：实现多版本解析与容错；必要时提供版本开关。

## 下一步
1. 请确认“结构化问题清单”的决策点（版本/模式、清单格式、排除列表、`rf-cap`、是否更新已存在配置、Kafka `bin` 路径等）。
2. 我将据此生成 `CONSENSUS_kafka_topics_mirror.md` 并进入架构与设计阶段（DESIGN 文档）。
3. 在达成共识后，编写并提交 `export_kafka_topics.sh` 与 `import_kafka_topics.sh`，包含函数级注释与 `--dry-run`、日志等能力。