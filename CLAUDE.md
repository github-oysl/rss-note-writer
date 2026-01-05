# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RSS Note Writer is a Python application that automatically fetches article links from RSS feeds and posts them to a notes API. It supports both file-based and database-backed configurations with multi-user row-level security (RLS) for PostgreSQL deployments.

**Core Flow**: RSS sources → Fetch links → Deduplicate → Post to API → Store results

## Common Commands

### Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application (basic)
python -m rss_note_writer --config-file src/rss_note_writer/config/rss_configs.json

# Run with debug logging
python -m rss_note_writer --log-level DEBUG --config-file src/rss_note_writer/config/rss_configs.json

# Create default config files
python -m rss_note_writer --create-config

# Quick start scripts (auto-setup venv)
./run_mac.sh --log-level DEBUG              # macOS/Linux
run_windows.bat --log-level DEBUG           # Windows
```

### Testing

```bash
# Run all tests with pytest
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_rss_fetcher.py -v

# Run with coverage
python -m pytest tests/ --cov=src/rss_note_writer --cov-report=html

# Quick functional test
python quick_test.py
```

### Database Operations

```bash
# Export file-based data to SQL
python scripts/export_to_sql.py

# Import SQL data to Neon/PostgreSQL
python scripts/import_to_neon.py
```

### Docker

```bash
# Build and start services
docker compose up -d

# View logs
docker compose logs -f rss-note-writer

# Run with custom command
docker compose run --rm rss-note-writer python -m rss_note_writer --log-level DEBUG
```

### Web Management Interface

```bash
# Start the FastAPI web UI (default port 8000)
uvicorn rss_note_writer.webapp.app:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

### Core Components

```
┌─────────────────────────────────────────┐
│ CLI (cli.py)                            │  Entry point, arg parsing
├─────────────────────────────────────────┤
│ Scheduler (scheduler.py)                │  Orchestrates fetch-post flow
├─────────────────────────────────────────┤
│ RssFetcher | ApiCaller                  │  External integrations
├─────────────────────────────────────────┤
│ ConfigLoader | DedupStore               │  Configuration & deduplication
├─────────────────────────────────────────┤
│ Repositories (repositories.py)          │  Data access with RLS support
├─────────────────────────────────────────┤
│ SQLAlchemy Models (models.py)           │  ORM layer
│ Database (PostgreSQL) or JSON files     │  Storage layer
└─────────────────────────────────────────┘
```

### Key Files

- **cli.py** (259 lines): Main entry point with argument parsing and config creation
- **scheduler.py** (~12KB): Core orchestration logic that coordinates RSS fetching, API calls, and result storage
- **rss_fetcher.py** (~3KB): RSS feed parsing with feedparser, extracts HTTP/HTTPS links
- **api_caller.py** (~6KB): Posts links to notes API with Bearer token authentication
- **config_loader.py** (~6KB): Loads configs from JSON files or database, supports environment variables
- **models.py** (~5KB): SQLAlchemy ORM models (RssConfigSource, ProcessedLink, WriteResult, AppUser, UserToken)
- **repositories.py** (~15KB): Data access layer with row-level security support for multi-user PostgreSQL
- **webapp/app.py** (~25KB): FastAPI web management UI with authentication

### Data Models

**RssConfigSource**: RSS feed configurations
- Fields: rss_url, topic_id, topic_directory_id, max_links (1-200), content, cron, active, user_id

**ProcessedLink**: Deduplication tracking
- Fields: rss_url, link, topic_id, processed_at, user_id

**WriteResult**: API call results
- Fields: rss_url, link, status, response_data, note_id, error_message, user_id

**AppUser/UserToken**: Multi-user authentication for web UI

### Storage Modes

1. **File-based** (default):
   - Config: `src/rss_note_writer/config/rss_configs.json`
   - Processed links: `src/rss_note_writer/data/processed_links.json`

2. **Database-backed**: Set `DB_URL` environment variable
   - Tables: `rss_config_sources`, `processed_links`, `write_results`, `app_users`, `user_tokens`
   - Supports row-level security (RLS) for multi-user isolation
   - User context set via `app.current_user_id` PostgreSQL variable

### Authentication

- **CLI Mode**: Uses `BEARER_TOKEN` from `.env` or database `user_tokens` table
- **Web UI**: Session-based authentication with username/password stored in `app_users` table

## Configuration

### Environment Variables (.env)

```env
# Required: Notes API authentication
BEARER_TOKEN=your_bearer_token_here

# Optional: Database connection (omit for file-based mode)
DB_URL=postgresql://user:pass@host:5432/dbname

# Optional: Global cron scheduling (e.g., "0 * * * *" for hourly)
CRON=0 * * * *

# Optional: Logging
LOG_LEVEL=INFO
LOG_FILE=rss_note_writer.log

# Optional: Proxy configuration
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
NO_PROXY=1  # Set to disable proxy
```

### RSS Config Structure (rss_configs.json)

```json
[
  {
    "rss_url": "https://rss.cnn.com/rss/edition.rss",
    "topic_id": "news_topic",
    "topic_directory_id": "news_directory",
    "max_links": 10,
    "content": "整理这条笔记的核心内容，注意标题 按发布日期-主题-领域-内容进行拼接",
    "cron": "*/30 * * * *"
  }
]
```

- `max_links`: 1-200, defaults to 10 if omitted
- `content`: Custom note content template, has default if omitted
- `cron`: Optional per-source scheduling (overrides global CRON)

## Notes API Integration

**Endpoint**: `POST https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream`

**Required Headers**:
- `Authorization: Bearer {token}`
- `Content-Type: application/json`
- `X-Request-ID: {timestamp}`

**Request Body**:
```json
{
  "attachments": [{"size": 100, "type": "link", "url": "https://..."}],
  "content": "Custom content from config",
  "entry_type": "ai",
  "note_type": "link",
  "source": "web",
  "topic_id": "topic_id",
  "topic_directory_id": "directory_id"
}
```

**Response Parsing**: The `api_response_parser.py` extracts note IDs using flexible patterns to handle various response formats.

## Important Implementation Details

### Deduplication Strategy

- **Per-topic**: Links are tracked by (rss_url, topic_id, link) combination
- **File mode**: In-memory JSON with `processed_links.json` persistence
- **DB mode**: Database queries with user-scoped isolation via RLS

### Row-Level Security (RLS)

When using PostgreSQL with multiple users:
1. Set `app.current_user_id` session variable before queries
2. RLS policies filter data by `user_id` column automatically
3. Implemented in `repositories.py` with `set_current_user()` method
4. Ensures complete data isolation between users

### Error Handling

- **Single source failure**: Does not halt entire process
- **API failures**: Logged with full error details in `write_results` table
- **RSS parsing failures**: Skipped with warning, continues to next source
- **Delay between API calls**: Configurable via `--delay` (default 10s) to avoid rate limiting

### Cron Scheduling

- **Global**: Set `CRON` environment variable for all sources
- **Per-source**: Override with `cron` field in RSS config
- **APScheduler**: Used for background job scheduling
- **Daemon mode**: Runs continuously when cron is configured

## Code Standards

- **Python 3.8+** required
- **PEP 8**: Follow Python style guidelines
- **Docstrings**: All functions must have docstrings explaining parameters, returns, and exceptions
- **Type hints**: Use where beneficial for clarity
- **Error handling**: Always handle exceptions appropriately with logging
- **Testing**: Write tests for new functionality (aim for 90%+ coverage)

## Platform-Specific Notes

### macOS/Linux vs Windows

- Virtual env activation: `source .venv/bin/activate` vs `.venv\Scripts\activate`
- Python command: `python3` vs `python`
- Path separators: `/` vs `\`
- Shell scripts: `run_mac.sh` for Unix, `run_windows.bat` for Windows

### Proxy Configuration

- Default proxy: `http://127.0.0.1:7897` (set in run scripts)
- Disable proxy: Set `NO_PROXY=1` before running
- Custom proxy: Export/set `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` variables

### macOS LibreSSL Warning

- System Python may use LibreSSL instead of OpenSSL
- Warning: `urllib3 NotOpenSSLWarning` (harmless, doesn't affect functionality)
- Fix: Use Homebrew Python (`brew install python@3.12`) and recreate venv

## Testing Strategy

The project has comprehensive test coverage:
- **50+ unit tests**: Individual component testing
- **12+ integration tests**: Multi-component interaction testing
- **5+ end-to-end tests**: Full workflow testing
- **~90% code coverage**: Verified with pytest-cov

Tests use mocking extensively (unittest.mock) to isolate components and avoid external dependencies during testing.

## Web Management Interface

The FastAPI web UI (`webapp/app.py`) provides:
- User authentication (login/logout)
- RSS source management (CRUD operations)
- Processed links viewer
- Write results monitoring
- User token management

Access at `http://localhost:8000` after starting with uvicorn.

## Migration from File to Database

1. Create PostgreSQL database and set `DB_URL` in `.env`
2. Run migrations: `python scripts/export_to_sql.py` to generate SQL from JSON files
3. Import: `python scripts/import_to_neon.py` to populate database
4. Update configuration to use database mode

## Common Troubleshooting

- **ModuleNotFoundError**: Run `pip install -r requirements.txt`
- **KeyError: BEARER_TOKEN**: Check `.env` file exists and contains `BEARER_TOKEN`
- **FileNotFoundError**: Run `python -m rss_note_writer --create-config`
- **API 401 Unauthorized**: Verify Bearer token is valid
- **RSS parsing errors**: Check RSS URL is accessible and returns valid XML
- **Database connection errors**: Verify `DB_URL` format and database is running
