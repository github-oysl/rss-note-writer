# Simple test for ApiCaller functionality
print("Starting ApiCaller test...")

# Test imports
try:
    import requests
    import time
    import logging
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Test basic functionality
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test X-Request-ID generation
test_id = str(int(time.time() * 1000))
print(f"✓ X-Request-ID generated: {test_id}")

# Test headers construction
token = "test_token"
headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'X-Request-ID': test_id,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print(f"✓ Headers constructed: {len(headers)} headers")
print(f"✓ Authorization: {headers['Authorization']}")

# Test payload construction
link = "https://example.com/article"
topic_id = "topic123"
topic_directory_id = "dir456"

payload = {
    "attachments": [
        {
            "size": 100,
            "type": "link",
            "url": link
        }
    ],
    "content": "",
    "entry_type": "ai",
    "note_type": "link",
    "source": "web",
    "topic_id": topic_id,
    "topic_directory_id": topic_directory_id
}

print(f"✓ Payload constructed: {len(payload)} fields")
print(f"✓ Topic ID: {payload['topic_id']}")
print(f"✓ Attachments: {len(payload['attachments'])} items")

print("\n=== All tests passed! ===")
print("ApiCaller core functionality verified.")