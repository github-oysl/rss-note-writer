#!/usr/bin/env bash
set -euo pipefail

#
# 函数说明：打印脚本用法
# 输入：无
# 输出：标准输出打印使用说明
# 返回：0
usage() {
  cat <<'EOF'
用法: export_kafka_topics.sh --src <HOST:PORT> [--bin <KAFKA_BIN_DIR>]
      [--exclude-regex <REGEX>] [--exclude-list <CSV>] [--out <FILE>]
      [--dry-run]

示例:
  ./export_kafka_topics.sh --src src:9092 --bin /opt/kafka/bin --out topics_manifest.lst
  ./export_kafka_topics.sh --src src:9092 --exclude-list "__consumer_offsets,_schemas" --dry-run

参数说明:
  --src                源集群 bootstrap-server (Kafka 2.6.1)
  --bin                Kafka bin 目录路径（包含 kafka-topics.sh），可选
  --exclude-regex      排除 Topic 的正则，默认 '^(__|_).*'
  --exclude-list       显式排除列表 CSV，默认包含常见系统 Topic
  --out                输出清单文件路径，默认 './topics_manifest.lst'
  --dry-run            仅打印将生成的清单内容，不写入文件
EOF
}

# 通用日志函数
log()  { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
err()  { echo "[ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

# 默认参数
SRC_BOOTSTRAP=""
KAFKA_BIN_DIR=""
EXCLUDE_REGEX='^(__|_).*'
EXCLUDE_LIST='__consumer_offsets,__transaction_state,__cluster_metadata,__cluster_config,__producer_ids,_schemas,_confluent-metrics,__confluent.support.metrics,connect-configs,connect-offsets,connect-status'
OUT_FILE="./topics_manifest.lst"
DRY_RUN=0
CMD_TIMEOUT="15s"

#
# 函数说明：解析命令行参数
# 输入：脚本参数列表
# 输出：设置全局变量
# 返回：0 或失败退出
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --src) SRC_BOOTSTRAP="$2"; shift 2 ;;
      --bin) KAFKA_BIN_DIR="$2"; shift 2 ;;
      --exclude-regex) EXCLUDE_REGEX="$2"; shift 2 ;;
      --exclude-list) EXCLUDE_LIST="$2"; shift 2 ;;
      --out) OUT_FILE="$2"; shift 2 ;;
      --dry-run) DRY_RUN=1; shift 1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "未知参数: $1" ;;
    esac
  done
  [[ -z "$SRC_BOOTSTRAP" ]] && die "必须指定 --src"
}

# 全局 CLI 路径变量
a_topics=""

#
# 函数说明：定位 kafka-topics.sh 并校验可执行性
# 输入：使用全局变量 KAFKA_BIN_DIR
# 输出：设置全局变量 a_topics
# 返回：0 或失败退出
locate_cli() {
  local candidate
  if [[ -n "$KAFKA_BIN_DIR" ]]; then
    candidate="$KAFKA_BIN_DIR/kafka-topics.sh"
  else
    candidate="$(command -v kafka-topics.sh || true)"
  fi
  [[ -z "$candidate" || ! -x "$candidate" ]] && die "未找到可执行的 kafka-topics.sh，请用 --bin 指定或加入 PATH"
  a_topics="$candidate"
  log "使用 kafka-topics.sh: $a_topics"
}

#
# 函数说明：带超时执行命令，若系统无 timeout 则直接执行
# 输入：命令字符串
# 输出：命令标准输出
# 返回：命令返回码
run_with_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$CMD_TIMEOUT" bash -c "$*"
  else
    bash -c "$*"
  fi
}

#
# 函数说明：检查源集群连通性
# 输入：使用全局变量 SRC_BOOTSTRAP
# 输出：无
# 返回：0 或失败退出
check_connectivity() {
  log "检查源集群连通性: $SRC_BOOTSTRAP"
  run_with_timeout "$a_topics --bootstrap-server \"$SRC_BOOTSTRAP\" --list > /dev/null" || die "无法连接源集群"
}

#
# 函数说明：列出源集群所有 Topic
# 输入：使用全局变量 a_topics 与 SRC_BOOTSTRAP
# 输出：逐行打印 Topic 名称
# 返回：0 或失败退出
list_source_topics() {
  run_with_timeout "$a_topics --bootstrap-server \"$SRC_BOOTSTRAP\" --list"
}

#
# 函数说明：判断 Topic 是否匹配排除规则
# 输入：$1=topic 名称
# 输出：无
# 返回：0 表示应排除；1 表示不排除
should_exclude_topic() {
  local t="$1"
  if [[ "$t" =~ $EXCLUDE_REGEX ]]; then
    return 0
  fi
  local IFS=','
  for x in $EXCLUDE_LIST; do
    if [[ "$t" == "$x" ]]; then return 0; fi
  done
  return 1
}

#
# 函数说明：获取 Topic 元信息并解析为行式清单字段
# 输入：$1=topic 名称
# 输出：打印形如 "topic|partitions|rf|k=v,k2=v2" 的一行（不写文件）
# 返回：0 或失败退出
get_topic_manifest_line() {
  local t="$1"
  local dline
  dline="$(run_with_timeout "$a_topics --bootstrap-server \"$SRC_BOOTSTRAP\" --topic \"$t\" --describe | head -n1" || true)"
  [[ -z "$dline" ]] && die "无法获取 Topic 描述: $t"

  # 解析分区数与复制因子
  local pc rf cfgs
  pc="$(echo "$dline" | sed -n 's/.*PartitionCount:[[:space:]]*\([0-9]\+\).*/\1/p')"
  rf="$(echo "$dline" | sed -n 's/.*ReplicationFactor:[[:space:]]*\([0-9]\+\).*/\1/p')"
  cfgs="$(echo "$dline" | sed -n 's/.*Configs:[[:space:]]*\([^ ]\+\).*/\1/p')"
  [[ -z "$pc" || -z "$rf" ]] && die "解析失败: $t -> $dline"

  # 清洗 cfgs，允许为空
  if [[ -n "$cfgs" ]]; then
    cfgs="$(echo "$cfgs" | sed 's/[[:space:]]//g')"
  fi

  echo "$t|$pc|$rf|$cfgs"
}

#
# 函数说明：主流程
# 输入：脚本参数
# 输出：写入清单文件或打印 DRY-RUN 输出
# 返回：0 或失败退出
main() {
  parse_args "$@"
  locate_cli
  check_connectivity

  log "源集群: $SRC_BOOTSTRAP"
  log "排除正则: $EXCLUDE_REGEX"
  log "排除列表: $EXCLUDE_LIST"
  log "输出文件: $OUT_FILE"
  [[ "$DRY_RUN" -eq 1 ]] && log "DRY-RUN 模式，仅打印清单"

  local t line
  if [[ "$DRY_RUN" -eq 1 ]]; then
    list_source_topics | while read -r t; do
      [[ -z "$t" ]] && continue
      if should_exclude_topic "$t"; then
        log "跳过（排除规则匹配）: $t"
        continue
      fi
      line="$(get_topic_manifest_line "$t")"
      echo "$line"
    done
    exit 0
  fi

  : > "$OUT_FILE" || die "无法写入输出文件: $OUT_FILE"
  list_source_topics | while read -r t; do
    [[ -z "$t" ]] && continue
    if should_exclude_topic "$t"; then
      log "跳过（排除规则匹配）: $t"
      continue
    fi
    line="$(get_topic_manifest_line "$t")"
    echo "$line" >> "$OUT_FILE"
  done
  log "导出完成: $OUT_FILE"
}

main "$@"