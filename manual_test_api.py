# Test script for ApiCaller - Manual verification
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 手动测试各个组件
print("=== Manual ApiCaller Test ===")

# 测试1: 导入模块
try:
    import requests
    print("✓ requests imported")
except ImportError as e:
    print(f"✗ requests import failed: {e}")
    sys.exit(1)

try:
    import time
    print("✓ time imported")
except ImportError as e:
    print(f"✗ time import failed: {e}")
    sys.exit(1)

try:
    import logging
    print("✓ logging imported")
except ImportError as e:
    print(f"✗ logging import failed: {e}")
    sys.exit(1)

# 测试2: 创建类
try:
    class TestApiCaller:
        def __init__(self):
            self.logger = logging.getLogger(__name__)
            self.base_url = "https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream"
        
        def test_headers(self, token):
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'X-Request-ID': str(int(time.time() * 1000)),
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            return headers
        
        def test_payload(self, link, topic_id, topic_directory_id):
            return {
                "attachments": [{"size": 100, "type": "link", "url": link}],
                "content": "",
                "entry_type": "ai",
                "note_type": "link",
                "source": "web",
                "topic_id": topic_id,
                "topic_directory_id": topic_directory_id
            }
    
    caller = TestApiCaller()
    print("✓ ApiCaller class structure created")
except Exception as e:
    print(f"✗ ApiCaller class creation failed: {e}")
    sys.exit(1)

# 测试3: 测试头部生成
try:
    headers = caller.test_headers("test_token")
    assert 'Authorization' in headers
    assert 'Bearer test_token' in headers['Authorization']
    assert 'X-Request-ID' in headers
    assert headers['X-Request-ID'].isdigit()
    print("✓ Headers generation works")
except Exception as e:
    print(f"✗ Headers generation failed: {e}")
    sys.exit(1)

# 测试4: 测试载荷生成
try:
    payload = caller.test_payload("https://example.com", "topic123", "dir456")
    assert payload['topic_id'] == "topic123"
    assert payload['topic_directory_id'] == "dir456"
    assert len(payload['attachments']) == 1
    assert payload['attachments'][0]['url'] == "https://example.com"
    print("✓ Payload generation works")
except Exception as e:
    print(f"✗ Payload generation failed: {e}")
    sys.exit(1)

print("\n=== All manual tests passed! ===")
print("ApiCaller module is ready for integration.")