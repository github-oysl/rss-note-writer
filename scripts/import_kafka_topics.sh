#!/usr/bin/env bash
set -euo pipefail

#
# 函数说明：打印脚本用法
# 输入：无
# 输出：标准输出打印使用说明
# 返回：0
usage() {
  cat <<'EOF'
用法: import_kafka_topics.sh --dest <HOST:PORT> --manifest <FILE> [--bin <KAFKA_BIN_DIR>]
      [--skip-existing] [--rf-cap <N>] [--config-whitelist <CSV>] [--dry-run]

示例:
  ./import_kafka_topics.sh --dest dest:9092 --manifest ./topics_manifest.lst --bin /opt/kafka/bin --skip-existing \
    --config-whitelist "cleanup.policy,min.insync.replicas" --dry-run

参数说明:
  --dest                目标集群 bootstrap-server (Kafka 2.6.1)
  --manifest            行式清单文件路径（由导出脚本生成）
  --bin                 Kafka bin 目录路径（包含 kafka-topics.sh/kafka-configs.sh），可选
  --skip-existing       目标已存在则跳过创建（默认开启）
  --rf-cap              复制因子上限；不设置则不降级
  --config-whitelist    白名单键集合 CSV，仅这些键会被应用（示例：cleanup.policy,min.insync.replicas）
  --dry-run             仅打印将执行的命令，不实际执行
EOF
}

# 通用日志函数
log()  { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
err()  { echo "[ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

# 默认参数
DEST_BOOTSTRAP=""
MANIFEST_FILE=""
KAFKA_BIN_DIR=""
SKIP_EXISTING=1
RF_CAP=""
CONFIG_WHITELIST=""  # CSV
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
      --dest) DEST_BOOTSTRAP="$2"; shift 2 ;;
      --manifest) MANIFEST_FILE="$2"; shift 2 ;;
      --bin) KAFKA_BIN_DIR="$2"; shift 2 ;;
      --skip-existing) SKIP_EXISTING=1; shift 1 ;;
      --rf-cap) RF_CAP="$2"; shift 2 ;;
      --config-whitelist) CONFIG_WHITELIST="$2"; shift 2 ;;
      --dry-run) DRY_RUN=1; shift 1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "未知参数: $1" ;;
    esac
  done
  [[ -z "$DEST_BOOTSTRAP" ]] && die "必须指定 --dest"
  [[ -z "$MANIFEST_FILE" ]] && die "必须指定 --manifest"
  [[ ! -f "$MANIFEST_FILE" ]] && die "清单文件不存在: $MANIFEST_FILE"
}

# 全局 CLI 路径变量
a_topics=""
a_configs=""

#
# 函数说明：定位 kafka-topics.sh / kafka-configs.sh 并校验可执行性
# 输入：使用全局变量 KAFKA_BIN_DIR
# 输出：设置全局变量 a_topics 与 a_configs
# 返回：0 或失败退出
locate_cli() {
  local t c
  if [[ -n "$KAFKA_BIN_DIR" ]]; then
    t="$KAFKA_BIN_DIR/kafka-topics.sh"
    c="$KAFKA_BIN_DIR/kafka-configs.sh"
  else
    t="$(command -v kafka-topics.sh || true)"
    c="$(command -v kafka-configs.sh || true)"
  fi
  [[ -z "$t" || ! -x "$t" ]] && die "未找到可执行的 kafka-topics.sh，请用 --bin 指定或加入 PATH"
  [[ -z "$c" || ! -x "$c" ]] && die "未找到可执行的 kafka-configs.sh，请用 --bin 指定或加入 PATH"
  a_topics="$t"; a_configs="$c"
  log "使用 kafka-topics.sh: $a_topics"
  log "使用 kafka-configs.sh: $a_configs"
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
# 函数说明：检查目标集群连通性
# 输入：使用全局变量 DEST_BOOTSTRAP
# 输出：无
# 返回：0 或失败退出
check_connectivity() {
  log "检查目标集群连通性: $DEST_BOOTSTRAP"
  run_with_timeout "$a_topics --bootstrap-server \"$DEST_BOOTSTRAP\" --list > /dev/null" || die "无法连接目标集群"
}

#
# 函数说明：检查目标是否已存在 Topic
# 输入：$1=topic 名称
# 输出：无
# 返回：0 已存在；1 不存在
dest_topic_exists() {
  local t="$1"
  run_with_timeout "$a_topics --bootstrap-server \"$DEST_BOOTSTRAP\" --list | grep -Fx \"$t\" >/dev/null" && return 0 || return 1
}

#
# 函数说明：解析清单行并输出四个字段
# 输入：$1=清单行（topic|partitions|rf|k=v,k2=v2）
# 输出：通过 echo 打印四段，或在调用处赋值
# 返回：0 或失败退出
parse_manifest_line() {
  local line="$1"
  local topic pc rf cfgs
  topic="${line%%|*}"; line="${line#*|}"
  pc="${line%%|*}";   line="${line#*|}"
  rf="${line%%|*}";   cfgs="${line#*|}"
  echo "$topic|$pc|$rf|$cfgs"
}

#
# 函数说明：根据白名单过滤配置集合，返回逗号分隔的 k=v 集合
# 输入：$1=原始 cfgs（逗号分隔），$2=白名单 CSV
# 输出：打印过滤后的逗号分隔字符串（可能为空）
# 返回：0
filter_cfgs_by_whitelist() {
  local cfgs="$1"; local wl="$2"
  [[ -z "$cfgs" || -z "$wl" ]] && { echo ""; return 0; }
  local IFS=',' filtered="" key val kv w
  for kv in $cfgs; do
    [[ -z "$kv" ]] && continue
    key="${kv%%=*}"; val="${kv#*=}"
    # 精确匹配白名单键
    for w in ${wl//,/ } ; do
      if [[ "$key" == "$w" ]]; then
        if [[ -z "$filtered" ]]; then filtered="$key=$val"; else filtered="$filtered,$key=$val"; fi
        break
      fi
    done
  done
  echo "$filtered"
}

#
# 函数说明：创建 Topic（可带部分白名单配置），必要时降级复制因子
# 输入：$1=topic $2=partitions $3=rf $4=whitelist_cfgs（逗号分隔）
# 输出：执行创建命令或打印 DRY-RUN 命令
# 返回：0 或失败退出
create_topic_with_configs() {
  local t="$1" pc="$2" rf="$3" wlcfgs="$4"
  local rf_use="$rf"
  if [[ -n "$RF_CAP" ]]; then
    if [[ "$rf_use" -gt "$RF_CAP" ]]; then
      warn "复制因子 $rf_use 超出 rf-cap=$RF_CAP，降为 $RF_CAP（Topic: $t）"
      rf_use="$RF_CAP"
    fi
  fi

  local cmd="$a_topics --bootstrap-server \"$DEST_BOOTSTRAP\" --create --topic \"$t\" --partitions \"$pc\" --replication-factor \"$rf_use\""
  if [[ -n "$wlcfgs" ]]; then
    local IFS=','; for kv in $wlcfgs; do
      [[ -z "$kv" ]] && continue
      cmd="$cmd --config \"$kv\""
    done
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] $cmd"
    return 0
  fi

  if eval "$cmd"; then
    log "创建成功: $t (partitions=$pc, rf=$rf_use)"
    return 0
  fi

  warn "创建（带配置）失败，尝试仅创建基础信息: $t"
  cmd="$a_topics --bootstrap-server \"$DEST_BOOTSTRAP\" --create --topic \"$t\" --partitions \"$pc\" --replication-factor \"$rf_use\""
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] $cmd"
    return 0
  fi
  eval "$cmd" || die "创建失败: $t"
}

#
# 函数说明：对白名单配置执行追加（alter）
# 输入：$1=topic $2=whitelist_cfgs（逗号分隔）
# 输出：执行追加命令或打印 DRY-RUN 命令
# 返回：0
alter_topic_configs() {
  local t="$1" wlcfgs="$2"
  [[ -z "$wlcfgs" ]] && return 0
  local cmd="$a_configs --bootstrap-server \"$DEST_BOOTSTRAP\" --entity-type topics --entity-name \"$t\" --alter --add-config \"$wlcfgs\""
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] $cmd"
    return 0
  fi
  eval "$cmd" || warn "更新配置失败（可能为只读/不支持的配置）: $t"
}

#
# 函数说明：处理一个清单条目（完整创建流程）
# 输入：$1=清单行
# 输出：创建与配置追加的执行日志
# 返回：0
process_manifest_entry() {
  local line="$1"
  [[ -z "$line" ]] && return 0
  local parsed="$(parse_manifest_line "$line")"
  local topic="${parsed%%|*}"; parsed="${parsed#*|}"
  local pc="${parsed%%|*}"; parsed="${parsed#*|}"
  local rf="${parsed%%|*}"; local cfgs="${parsed#*|}"

  # 过滤到白名单配置集合
  local wlcfgs
  wlcfgs="$(filter_cfgs_by_whitelist "$cfgs" "$CONFIG_WHITELIST")"

  # 存在性检查
  if dest_topic_exists "$topic"; then
    if [[ "$SKIP_EXISTING" -eq 1 ]]; then
      log "目标已存在，跳过创建: $topic"
      return 0
    fi
  fi

  # 创建并追加白名单配置
  create_topic_with_configs "$topic" "$pc" "$rf" "$wlcfgs"
  alter_topic_configs "$topic" "$wlcfgs"
}

#
# 函数说明：主流程
# 输入：脚本参数
# 输出：执行日志
# 返回：0 或失败退出
main() {
  parse_args "$@"
  locate_cli
  check_connectivity

  log "目标集群: $DEST_BOOTSTRAP"
  log "清单文件: $MANIFEST_FILE"
  [[ -n "$RF_CAP" ]] && log "复制因子上限: $RF_CAP"
  [[ -n "$CONFIG_WHITELIST" ]] && log "配置白名单: $CONFIG_WHITELIST" || log "配置白名单为空：不应用任何配置键"
  [[ "$DRY_RUN" -eq 1 ]] && log "DRY-RUN 模式，仅打印命令"

  while IFS= read -r line || [[ -n "$line" ]]; do
    process_manifest_entry "$line"
  done < "$MANIFEST_FILE"

  log "全部处理完成"
}

main "$@"