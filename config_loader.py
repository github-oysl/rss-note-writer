import json
import os
from dotenv import load_dotenv

class ConfigLoader:
    def __init__(self, config_path='config/rss_configs.json', env_path='.env'):
        """
        初始化 ConfigLoader。
        
        :param config_path: 配置文件的路径，默认 'config/rss_configs.json'
        :param env_path: .env 文件的路径，默认 '.env'
        """
        self.config_path = config_path
        self.env_path = env_path

    def load_token(self):
        """
        从 .env 文件加载 BEARER_TOKEN。
        
        :return: token 字符串
        :raises FileNotFoundError: 如果 .env 文件不存在
        :raises KeyError: 如果 BEARER_TOKEN 未定义
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
        
        :return: 配置列表 (List[Dict])
        :raises FileNotFoundError: 如果配置文件不存在
        :raises json.JSONDecodeError: 如果 JSON 无效
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            configs = json.load(f)
        
        # 验证每个配置的有效性
        for config in configs:
            if not all(key in config for key in ['rss_url', 'topic_id', 'topic_directory_id']):
                raise ValueError("Invalid config: missing required keys")
        
        return configs