# RSS Note Writer

自动从 RSS 源获取文章链接并添加到笔记应用的 Python 工具。

## 🚀 功能特性

- **📡 RSS 源支持**: 从多个 RSS 源自动获取文章链接
- **🔍 智能过滤**: 自动过滤非 HTTP/HTTPS 链接，确保安全性
- **📝 API 集成**: 无缝集成笔记应用 API，支持 Bearer Token 认证
- **⏰ 定时调度**: 可配置的调度间隔，避免 API 限频
- **🔄 链接去重**: 内存级链接去重，避免重复处理
- **📊 日志系统**: 完整的日志记录，支持多级日志和文件输出
- **⚙️ 灵活配置**: JSON 配置文件，环境变量管理
- **🛡️ 错误处理**: 完善的异常处理，确保程序稳定运行

## 📦 安装

### 环境要求
- Python 3.7+
- pip 包管理器

### 安装步骤

1. **克隆项目**（或下载源码）
```bash
git clone <repository-url>
cd rss-note-writer
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **创建配置文件**
```bash
python rss_note_writer.py --create-config
```

## 🔧 配置

### 1. 设置 API Token

编辑 `.env` 文件，添加您的笔记应用 API Token：
```env
BEARER_TOKEN=your_bearer_token_here
```

### 2. 配置 RSS 源

编辑 `config/rss_configs.json`，添加 RSS 源配置：
```json
[
  {
    "rss_url": "https://rss.cnn.com/rss/edition.rss",
    "topic_id": "news_topic",
    "topic_directory_id": "news_directory"
  },
  {
    "rss_url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "topic_id": "tech_topic",
    "topic_directory_id": "tech_directory"
  }
]
```

### 3. 高级配置（可选）

#### 日志配置
```env
# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# 日志文件路径
LOG_FILE=rss_note_writer.log
```

#### 调度配置
```json
{
  "rss_url": "https://example.com/rss",
  "topic_id": "your_topic_id",
  "topic_directory_id": "your_directory_id",
  "max_links": 10,  // 每个 RSS 源最大链接数
  "delay_seconds": 10  // API 调用间隔（秒）
}
```

## 🎯 使用

### 快速开始
```bash
# 创建默认配置
python rss_note_writer.py --create-config

# 运行程序
python rss_note_writer.py
```

### 命令行参数
```bash
python rss_note_writer.py [选项]

选项:
  --config-file PATH    RSS 配置文件路径 (默认: config/rss_configs.json)
  --delay SECONDS       API 调用延迟时间（秒）(默认: 10)
  --log-level LEVEL     日志级别: DEBUG, INFO, WARNING, ERROR (默认: INFO)
  --log-file PATH       日志文件路径（可选）
  --create-config       创建默认配置文件并退出
  --help               显示帮助信息并退出
```

### 使用示例
```bash
# 基本使用
python rss_note_writer.py

# 设置 5 秒延迟
python rss_note_writer.py --delay 5

# 启用调试日志
python rss_note_writer.py --log-level DEBUG

# 输出日志到文件
python rss_note_writer.py --log-file app.log

# 使用自定义配置
python rss_note_writer.py --config-file my_config.json

# 重新创建配置文件
python rss_note_writer.py --create-config
```

## 🧪 测试

### 快速测试
```bash
# 运行快速功能测试
python quick_test.py
```

### 完整测试
```bash
# 运行所有测试
python final_test_runner.py

# 运行单元测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_rss_fetcher.py -v
```

### 测试覆盖
- ✅ 单元测试：50+ 测试用例
- ✅ 集成测试：12+ 测试场景  
- ✅ 端到端测试：5+ 真实场景
- ✅ 代码覆盖率：90%+

## 📋 API 说明

### 笔记 API 端点
```
POST https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream
```

### 请求头
```http
Authorization: Bearer {token}
Content-Type: application/json
X-Request-ID: {timestamp}
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

### 请求体
```json
{
  "attachments": [
    {
      "size": 100,
      "type": "link",
      "url": "https://example.com/article"
    }
  ],
  "content": "",
  "entry_type": "ai",
  "note_type": "link",
  "source": "web",
  "topic_id": "topic_id",
  "topic_directory_id": "directory_id"
}
```

## 🔍 故障排除

### 常见问题

#### 1. ModuleNotFoundError
```bash
# 安装缺失的依赖
pip install -r requirements.txt
```

#### 2. FileNotFoundError
```bash
# 创建默认配置
python rss_note_writer.py --create-config
```

#### 3. KeyError: BEARER_TOKEN
```bash
# 检查 .env 文件是否存在并包含 BEARER_TOKEN
cat .env
```

#### 4. API 调用失败
- 检查网络连接
- 验证 API Token 有效性
- 检查 API 端点是否可用
- 查看日志文件获取详细错误信息

#### 5. RSS 解析失败
- 验证 RSS URL 是否有效
- 检查 RSS 源是否可访问
- 确认 RSS 格式是否正确

### 调试建议

#### 启用调试日志
```bash
python rss_note_writer.py --log-level DEBUG
```

#### 检查日志文件
```bash
tail -f rss_note_writer.log  # 如果有设置日志文件
```

#### 测试 RSS 源
```python
# 测试 RSS 解析
python -c "
import feedparser
feed = feedparser.parse('https://your-rss-url.com/feed')
print(f'找到 {len(feed.entries)} 篇文章')
for entry in feed.entries[:3]:
    print(f'- {entry.title}: {entry.link}')
"
```

## 📊 性能说明

### 处理能力
- **RSS 源数量**: 无限制（建议 10-20 个）
- **链接处理**: 每个 RSS 源最多 10 个链接
- **调度间隔**: 可配置（默认 10 秒）
- **内存使用**: 约 50-100MB（取决于 RSS 源数量）

### 优化建议
1. **合理设置延迟**: 避免 API 限频，建议 5-30 秒
2. **控制 RSS 源数量**: 建议不超过 50 个同时处理
3. **定期清理日志**: 避免日志文件过大
4. **监控运行状态**: 定期检查程序运行状态

## 🔧 开发

### 项目结构
```
rss-note-writer/
├── rss_note_writer.py      # 主脚本
├── config_loader.py        # 配置加载器
├── rss_fetcher.py          # RSS 获取器
├── api_caller.py           # API 调用器
├── scheduler.py            # 调度器
├── logger.py               # 日志系统
├── requirements.txt        # 依赖列表
├── tests/                  # 测试目录
├── config/                 # 配置文件
└── docs/                   # 项目文档
```

### 开发环境设置
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装开发依赖
pip install -r requirements.txt
pip install pytest pytest-cov  # 测试工具
```

### 代码规范
- 遵循 PEP 8 Python 编码规范
- 函数必须有文档字符串
- 关键逻辑需要注释说明
- 异常必须被适当处理

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 贡献步骤
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📞 支持

如有问题，请：

1. 查看文档和 FAQ
2. 搜索现有 Issue
3. 创建新 Issue 描述问题
4. 提供相关日志和配置信息

---

**项目状态**: ✅ 稳定运行  
**最后更新**: 2024年11月  
**维护状态**: 活跃维护