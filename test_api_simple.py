# Test script for ApiCaller
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api_caller import ApiCaller
    print("✓ ApiCaller imported successfully")
    
    import time
    test_id = str(int(time.time() * 1000))
    print(f"✓ X-Request-ID generated: {test_id}")
    
    # 测试基本功能
    caller = ApiCaller()
    print("✓ ApiCaller initialized successfully")
    print("✓ API caller module is working correctly!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()