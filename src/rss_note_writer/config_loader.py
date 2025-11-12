import json
import os
from dotenv import load_dotenv


class ConfigLoader:
    """
    配置加载器：负责加载 RSS 配置与环境变量。

    方法：
    - `load_token`：从 `.env` 加载 `BEARER_TOKEN`
    - `load_configs`：从 JSON 文件加载 RSS 配置列表
    """

    def __init__(self, config_path: str = 'config/rss_configs.json', env_path: str = '.env'):
        """
        初始化 ConfigLoader。

        参数：
        - `config_path: str`：配置文件路径，默认 `config/rss_configs.json`
        - `env_path: str`：环境文件路径，默认 `.env`

        返回值：
        - 无
        """
        self.config_path = config_path
        self.env_path = env_path

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
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at {self.config_path}")

        with open(self.config_path, 'r') as f:
            configs = json.load(f)

        for config in configs:
            if not all(key in config for key in ['rss_url', 'topic_id', 'topic_directory_id']):
                raise ValueError("Invalid config: missing required keys")

        return configs

