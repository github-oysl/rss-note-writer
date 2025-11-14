import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .repositories import ConfigRepository, init_db_schema


class ConfigLoader:
    """
    配置加载器：负责加载 RSS 配置与环境变量。

    方法：
    - `load_token`：从 `.env` 加载 `BEARER_TOKEN`
    - `load_configs`：从 JSON 文件加载 RSS 配置列表
    """

    def __init__(self, config_path: str = None, env_path: str = None):
        """
        初始化 ConfigLoader。

        参数：
        - `config_path: str`：配置文件路径，默认使用包目录 `src/rss_note_writer/config/rss_configs.json`
        - `env_path: str`：环境文件路径，默认使用顶层 `.env`

        返回值：
        - 无
        """
        pkg_dir = Path(__file__).resolve().parent
        default_config = pkg_dir / 'config' / 'rss_configs.json'
        default_env = Path.cwd() / '.env'
        self.config_path = str(config_path) if config_path else str(default_config)
        self.env_path = str(env_path) if env_path else str(default_env)

    def load_token(self) -> str:
        """
        从 `.env` 文件加载 `BEARER_TOKEN`。

        参数：
        - 无

        返回值：
        - `str`：token 字符串

        异常：
        - `FileNotFoundError`：`.env` 文件不存在
        - `KeyError`：缺少 `BEARER_TOKEN`
        """
        if not os.path.exists(self.env_path):
            raise FileNotFoundError(f"No .env file found at {self.env_path}")

        load_dotenv(self.env_path)
        token = os.getenv('BEARER_TOKEN')
        if not token:
            raise KeyError("BEARER_TOKEN not found in .env file")
        return token

    def load_configs(self):
        """
        从 JSON 文件加载 RSS 配置列表。

        参数：
        - 无

        返回值：
        - `List[Dict]`：配置列表

        异常：
        - `FileNotFoundError`：配置文件不存在
        - `json.JSONDecodeError`：JSON 无效
        - `ValueError`：配置缺少必要键
        """
        # 优先从数据库读取（检测到 DB_URL 且存在配置数据时）
        if os.getenv('DB_URL'):
            try:
                init_db_schema()
                repo = ConfigRepository()
                items = repo.list()
                if items:
                    configs = []
                    for it in items:
                        cfg = {
                            'rss_url': it.get('rss_url'),
                            'topic_id': it.get('topic_id'),
                            'topic_directory_id': it.get('topic_directory_id'),
                        }
                        # 可选字段
                        if it.get('max_links') is not None:
                            cfg['max_links'] = it.get('max_links')
                        if it.get('content'):
                            cfg['content'] = it.get('content')
                        if it.get('cron'):
                            cfg['cron'] = it.get('cron')
                        configs.append(cfg)
                    for config in configs:
                        if not all(key in config for key in ['rss_url', 'topic_id', 'topic_directory_id']):
                            raise ValueError("Invalid config from DB: missing required keys")
                    return configs
            except Exception:
                # 数据库不可用或无数据，回退到文件
                pass

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(self.config_path, 'r', encoding='utf-8-sig') as f:
                text = f.read()
        configs = json.loads(text)

        for config in configs:
            if not all(key in config for key in ['rss_url', 'topic_id', 'topic_directory_id']):
                raise ValueError("Invalid config: missing required keys")

        return configs

