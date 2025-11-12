# CONSENSUS_rss_note_writer

基于 ALIGNMENT_rss_note_writer.md 和用户提供的澄清，以下是最终共识文档。所有不确定性已通过用户反馈解决。

## 明确的需求描述
开发一个 Python 脚本，用于从多个配置的 RSS 订阅源获取原始链接信息。如果检测到 RSS 更新，每 10 秒调用一次指定 API 接口，写入更新的每一条链接数据。
- **RSS 配置**：支持多个 RSS 源，每个源对应一个 RSS URL、topic_id 和 topic_directory_id。这些配置需手动提供（例如通过配置文件）。
- **API 接口**：POST https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream
- **参数模板**：{"attachments":[{"size":100,"type":"link","url":"[RSS_LINK]"}],"content":"","entry_type":"ai","note_type":"link","source":"web","topic_id":"[CONFIG_ID]","topic_directory_id":"[CONFIG_DIR_ID]"}
  - "size" 固定为 100。
  - "url" 替换为 RSS 获取的实际链接。
  - 其他参数固定。
- **请求头**：包括动态生成的 X-Request-ID（例如基于时间戳）、用户提供的 Authorization Bearer token（从 .env 加载，预留未来动态获取接口）、固定 User-Agent 等（匹配示例）。
- **执行逻辑**：
  - 逐个处理 RSS 配置。
  - 获取 RSS 链接，最多写入 10 个链接（每 10s 调用一次 API）。
  - 如果一个 RSS 源链接耗尽（无新链接或已达 10 个），切换到下一个配置。
  - 所有配置同步完成后，退出程序并打印完成提示。
- **不无限循环**：有限次写入（每个链接最多 10 次？澄清为每个 RSS 链接最多写入 10 次，但逻辑上可能是每个 RSS 源最多处理 10 个链接）。

## 验收标准
- 脚本能从配置文件加载多个 RSS 配置（RSS URL、topic_id、topic_directory_id）。
- 正确解析 RSS，获取链接，并每 10s 发送 POST 请求写入数据（最多 10 个 per RSS？）。
- 处理链接耗尽：切换配置，所有完成时退出并打印消息。
- token 从 .env 加载，不硬编码。
- 请求头正确设置，包括动态 X-Request-ID。
- 错误处理：API 失败时日志记录，不崩溃。
- 单元测试覆盖 RSS 解析、API 调用、定时逻辑。
- 脚本运行无错误，输出日志清晰。

## 技术实现方案和技术约束和集成方案
- **技术栈**：Python 3.x，使用 feedparser 解析 RSS，requests 发送 API 调用，dotenv 管理 .env，time 或 schedule 实现定时。
- **约束**：
  - 与现有项目对齐：放置在 scripts/ 下，风格类似 ck_compare.py（简洁、可读）。
  - 敏感信息：token 等放入 .env，不提交 git。
  - 配置：使用 JSON 或 YAML 文件存储 RSS 配置（例如 config/rss_configs.json）。
  - 动态元素：X-Request-ID = int(time.time() * 1000)。
  - 预留：token 获取方法（未来可添加函数从 API 获取）。
- **集成方案**：独立脚本，无需修改现有文件。复用项目约定，如 docs/ 下文档同步。

## 任务边界限制
- **范围内**：RSS 获取、API 调用、基本错误处理、配置加载、有限次循环。
- **范围外**：UI、部署、复杂重试机制、动态 topic_id 获取（手动配置）、无限运行。
- **假设确认**：用户提供初始 token 和 RSS 配置；脚本本地运行。

所有不确定性已解决，需求边界清晰无歧义，技术方案与现有架构对齐。