import pytest
from unittest.mock import patch, mock_open
from dotenv import load_dotenv
import os
import json

from rss_note_writer.config_loader import ConfigLoader

@pytest.fixture
def mock_env_file():
    """模拟 .env 文件"""
    mock_content = "BEARER_TOKEN=test_token\n"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        yield

@pytest.fixture
def mock_json_file():
    """模拟 config/rss_configs.json 文件"""
    mock_data = [
        {"rss_url": "https://example.com/rss", "topic_id": "123", "topic_directory_id": "456"},
        {"rss_url": "https://another.com/rss", "topic_id": "789", "topic_directory_id": "012"}
    ]
    mock_content = json.dumps(mock_data)
    with patch("builtins.open", mock_open(read_data=mock_content)):
        yield

def test_load_token(mock_env_file):
    """测试加载 token"""
    loader = ConfigLoader()
    token = loader.load_token()
    assert token == "test_token"

def test_load_token_missing_file():
    """测试 .env 文件缺失"""
    with patch("os.path.exists", return_value=False):
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError, match="No .env file found"):
            loader.load_token()

def test_load_configs(mock_json_file):
    """测试加载配置"""
    loader = ConfigLoader()
    configs = loader.load_configs()
    assert len(configs) == 2
    assert configs[0]["rss_url"] == "https://example.com/rss"
    assert configs[0]["topic_id"] == "123"
    assert configs[0]["topic_directory_id"] == "456"

def test_load_configs_missing_file():
    """测试配置文件缺失"""
    with patch("os.path.exists", return_value=False):
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            loader.load_configs()

def test_load_configs_invalid_json():
    """测试无效 JSON"""
    invalid_content = "invalid json"
    with patch("builtins.open", mock_open(read_data=invalid_content)):
        loader = ConfigLoader()
        with pytest.raises(json.JSONDecodeError):
            loader.load_configs()

def test_load_configs_empty_file():
    """测试空配置文件"""
    empty_content = "[]"
    with patch("builtins.open", mock_open(read_data=empty_content)):
        loader = ConfigLoader()
        configs = loader.load_configs()
        assert configs == []
