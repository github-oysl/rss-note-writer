# ACCEPTANCE_kafka_topics_mirror

## 概述
- 阶段：Automate → Assess（本次为初始验收记录骨架）
- 目标：验证导出/导入脚本在 Kafka 2.6.1 下的可用性与一致性
- 已实现：
  - `scripts/export_kafka_topics.sh`（行式清单导出、排除规则、dry-run）
  - `scripts/import_kafka_topics.sh`（创建 Topic、仅追加白名单配置、skip-existing、rf-cap 可选、dry-run）

## 验收范围与标准
- `导出`：
  - 生成行式清单格式：`topic|partitions|rf|k=v,k2=v2`
  - 实际导出的 `Configs` 字段仅包含显式配置；无配置时为空或省略
  - 支持 `--exclude-list` 与 `--exclude-regex` 过滤，并在 dry-run 模式下正确打印操作
- `导入`：
  - 连接目标集群 `--bootstrap-server <host:port>` 正常
  - 对于清单中的每一行：
    - 若目标已存在且 `--skip-existing` 开启（默认），则跳过创建
    - 若不存在：创建 Topic 并应用白名单配置（仅限 `--config-whitelist` 中的键）
    - `rf-cap` 未设置时不降级；若设置且超出则降级为 `rf-cap` 值
  - `dry-run` 模式仅打印将执行的命令，不产生副作用
  - 对只读或不兼容配置的处理：打印警告并继续，不中断整体流程

## 环境与前置条件
- Kafka 版本：2.6.1（CLI 使用 `--bootstrap-server`）
- 运行环境：Linux/WSL，`bash`、`grep`、`awk` 可用
- Kafka CLI：确保 `kafka-topics.sh` 与 `kafka-configs.sh` 在 `PATH` 或通过 `--bin` 指定

## 验证用例（建议顺序）
1. 导出（源集群）：
   - 命令：
     - `scripts/export_kafka_topics.sh --src SRC:9092 --out ./topics_manifest.lst --exclude-list __consumer_offsets,__transaction_state --dry-run`
   - 期望：打印将要导出的主题列表与行式清单预览
   - 实际导出：去掉 `--dry-run`，生成 `topics_manifest.lst`
2. 导入（目标集群，dry-run）：
   - 命令：
     - `scripts/import_kafka_topics.sh --dest DEST:9092 --manifest ./topics_manifest.lst --config-whitelist cleanup.policy,min.insync.replicas --dry-run`
   - 期望：打印所有将执行的创建与配置追加命令，且仅包含白名单键
3. 导入（目标集群，实际执行）：
   - 命令：
     - `scripts/import_kafka_topics.sh --dest DEST:9092 --manifest ./topics_manifest.lst --skip-existing --config-whitelist cleanup.policy,min.insync.replicas`
   - 期望：
     - 新主题被创建，分区数与复制因子与清单一致（或在设定了 `rf-cap` 时按上限降级）
     - 白名单配置键被追加生效
4. 验证：
   - `kafka-topics.sh --bootstrap-server DEST:9092 --describe --topic <t>` 检查分区数与复制因子
   - `kafka-configs.sh --bootstrap-server DEST:9092 --entity-type topics --entity-name <t> --describe` 检查白名单键存在且值一致

## 验证结果（占位）
- 导出验证：待执行
- 导入 dry-run 验证：待执行
- 导入实际执行：待执行
- 配置白名单验证：待执行

## 已知限制与注意事项
- 不更新已存在主题的配置（用户共识要求：仅创建并追加白名单配置）
- 未设置 `--config-whitelist` 时不应用任何配置键
- 设定 `--rf-cap` 时可能降低复制因子以适配目标 broker 数量
- 对只读/不兼容配置的追加会失败，脚本记录警告并继续
- 初版未持久化“失败清单”文件，后续可按需要补充

## 后续动作
- 执行上述验证用例并在本文件记录结果
- 根据需要补充失败清单输出与更详细的 README 使用说明