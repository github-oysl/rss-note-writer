import pytest
import requests
import sys
import os
from unittest.mock import Mock, patch
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_caller import ApiCaller

class TestApiCaller:
    """
    API 调用器单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.api_caller = ApiCaller()
        self.test_link = "https://example.com/article"
        self.test_topic_id = "topic123"
        self.test_topic_dir_id = "dir456"
        self.test_token = "test_bearer_token"
    
    @patch('requests.post')
    def test_call_api_success(self, mock_post):
        """测试 API 调用成功。"""
        # Mock 成功的响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response
        
        response = self.api_caller.call_api(
            self.test_link, 
            self.test_topic_id, 
            self.test_topic_dir_id, 
            self.test_token
        )
        
        # 验证响应
        assert response == mock_response
        assert mock_post.called
        
        # 验证请求参数
        call_args = mock_post.call_args
        assert call_args[1]['json']['topic_id'] == self.test_topic_id
        assert call_args[1]['json']['topic_directory_id'] == self.test_topic_dir_id
        assert call_args[1]['json']['attachments'][0]['url'] == self.test_link
        assert 'Bearer test_bearer_token' in call_args[1]['headers']['Authorization']
    
    @patch('requests.post')
    def test_call_api_non_success_status(self, mock_post):
        """测试 API 返回非成功状态码。"""
        # Mock 400 错误响应
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.ok = False
        mock_response.text = '{"error": "Bad Request"}'
        mock_post.return_value = mock_response
        
        response = self.api_caller.call_api(
            self.test_link, 
            self.test_topic_id, 
            self.test_topic_dir_id, 
            self.test_token
        )
        
        # 验证仍然返回响应对象
        assert response == mock_response
        assert response.status_code == 400
    
    @patch('requests.post')
    def test_call_api_timeout(self, mock_post):
        """测试 API 调用超时。"""
        # Mock 超时异常
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        with pytest.raises(requests.exceptions.Timeout):
            self.api_caller.call_api(
                self.test_link, 
                self.test_topic_id, 
                self.test_topic_dir_id, 
                self.test_token
            )
    
    @patch('requests.post')
    def test_call_api_connection_error(self, mock_post):
        """测试 API 连接错误。"""
        # Mock 连接错误
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            self.api_caller.call_api(
                self.test_link, 
                self.test_topic_id, 
                self.test_topic_dir_id, 
                self.test_token
            )
    
    @patch('requests.post')
    def test_call_api_request_exception(self, mock_post):
        """测试通用请求异常。"""
        # Mock 通用请求异常
        mock_post.side_effect = requests.exceptions.RequestException("Unknown error")
        
        with pytest.raises(requests.exceptions.RequestException):
            self.api_caller.call_api(
                self.test_link, 
                self.test_topic_id, 
                self.test_topic_dir_id, 
                self.test_token
            )
    
    @patch('requests.post')
    def test_call_api_headers_format(self, mock_post):
        """测试请求头格式是否正确。"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_post.return_value = mock_response
        
        self.api_caller.call_api(
            self.test_link, 
            self.test_topic_id, 
            self.test_topic_dir_id, 
            self.test_token
        )
        
        # 验证请求头
        headers = mock_post.call_args[1]['headers']
        assert headers['Authorization'] == 'Bearer test_bearer_token'
        assert headers['Content-Type'] == 'application/json'
        assert headers['X-Request-ID'].isdigit()  # 应该是数字字符串
        assert 'User-Agent' in headers
        assert 'Referer' in headers
    
    @patch('requests.post')
    def test_call_api_payload_format(self, mock_post):
        """测试请求体格式是否正确。"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_post.return_value = mock_response
        
        self.api_caller.call_api(
            self.test_link, 
            self.test_topic_id, 
            self.test_topic_dir_id, 
            self.test_token
        )
        
        # 验证请求体
        payload = mock_post.call_args[1]['json']
        assert payload['topic_id'] == self.test_topic_id
        assert payload['topic_directory_id'] == self.test_topic_dir_id
        assert payload['content'] == ""
        assert payload['entry_type'] == "ai"
        assert payload['note_type'] == "link"
        assert payload['source'] == "web"
        assert len(payload['attachments']) == 1
        assert payload['attachments'][0]['url'] == self.test_link
        assert payload['attachments'][0]['type'] == "link"
        assert payload['attachments'][0]['size'] == 100
    
    @patch('requests.post')
    def test_call_api_timeout_parameter(self, mock_post):
        """测试超时参数是否正确传递。"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_post.return_value = mock_response
        
        self.api_caller.call_api(
            self.test_link, 
            self.test_topic_id, 
            self.test_topic_dir_id, 
            self.test_token
        )
        
        # 验证超时参数
        assert mock_post.call_args[1]['timeout'] == 30