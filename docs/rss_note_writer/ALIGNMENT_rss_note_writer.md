# ALIGNMENT_rss_note_writer

## 项目上下文分析
- **现有项目结构**：项目位于 d:\CODE\python，包含 .trae/rules、config、docs、scripts 等文件夹。docs 文件夹下有之前的任务文档，如 ck_compare 和 kafka_topics_mirror。
- **技术栈**：主要为 Python 项目，可能涉及脚本自动化。现有脚本包括 ck_compare.py、export_kafka_topics.sh 和 import_kafka_topics.sh，表明支持 Python 和 Shell 脚本。
- **架构模式**：项目似乎聚焦于数据处理和自动化脚本，无复杂后端架构。依赖关系包括可能的外部 API 调用。
- **代码模式和约定**：现有代码为 Python 脚本，需保持简洁、可读。文档使用 Markdown 格式存储在 docs/ 下。
- **业务域和数据模型**：涉及数据一致性验证、Kafka 主题镜像等，当前任务为 RSS 链接获取和 API 数据写入，属于数据采集和集成领域。

## 原始需求
用户要求：获取 RSS 订阅的原始链接信息，然后每 10 秒调用一次指定接口进行数据写入。
- 接口 URL：https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream (POST)
- 参数示例：{"attachments":[{"size":100,"type":"link","url":"https://quaily.com/op7418/p/aigc-weekly-fourteen-four-renewal-discount-starts"}],"content":"","entry_type":"ai","note_type":"link","source":"web","topic_id":"2328688","topic_directory_id":"2717188"}
- 请求头：包括 Authorization Bearer token、User-Agent 等。

## 边界确认（明确任务范围）
- **范围内**：开发一个 Python 脚本，从指定 RSS 源获取链接，如果检测到更新,每10S 调用一次接口，写入更新的每一条原始链接。
- **范围外**：不涉及 UI 开发、不处理 API 响应后的进一步逻辑（如错误重试超出基本处理）、不包括部署到生产环境。
- **假设**：RSS 源需要用户指定；Authorization token 等敏感信息需从 .env 文件加载；脚本运行在本地。

## 需求理解（对现有项目的理解）
- 与现有项目对齐：类似于 ck_compare.py 的数据处理脚本，可以扩展为自动化任务。使用 Python requests 库进行 API 调用，feedparser 处理 RSS。
- 集成方案：脚本独立运行，无需修改现有文件，但可放置在 scripts/ 下。
- 潜在挑战：RSS 源未指定、token 管理、率限（每 10s 调用）、错误处理。

## 疑问澄清（存在歧义的地方）
- RSS 订阅源的具体 URL 是什么？（未提供，需要确认）
 A:这个需要支持配置 每个RSS 订阅源 对应一个topic_id 和 topic_directory_id 
- topic_id 和 topic_directory_id 是否固定，或需动态获取？
 A:手动按配置获取
- Authorization Bearer token 如何获取/更新？是否需要用户提供？
 A: 现在默认用户提供，但需要预留获取方法 方便后续迭代
- X-Request-ID 是否需要动态生成？
 A:需要
- 接口调用频率每 10s，是否无限循环或有停止条件？
 A: 不无限循环 每个RSS 链接最多写入10次，超过的不要
- 如果 RSS 链接耗尽，如何处理？
 A: 如果链接耗尽，执行下一个RSS订阅配置，如果全部配置都已经同步，退出程序，并打印完成提示够
- 参数中的 "size":100 是否固定，或基于实际链接计算？
  A:固定

这些疑问需要澄清以形成精确规范。