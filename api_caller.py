import requests
import time
import logging
import json
from typing import Optional, Dict, Any

class ApiCaller:
    """
    API 调用器：负责向笔记 API 发送链接数据。
    """
    
    def __init__(self):
        """
        初始化 API 调用器。
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://get-notes.luojilab.com/voicenotes/web/topics/notes/stream"
    
    def call_api(self, link: str, topic_id: str, topic_directory_id: str, token: str) -> requests.Response:
        """
        调用笔记 API 将链接添加到指定主题。

        :param link: 要添加的链接
        :param topic_id: 主题 ID
        :param topic_directory_id: 主题目录 ID
        :param token: Bearer token 认证（可传入带或不带 'Bearer ' 前缀）
        :return: requests.Response 对象
        :raises: requests.exceptions.RequestException 当请求失败时
        """
        self.logger.info(f"调用 API 添加链接到主题 {topic_id}: {link}")

        # 规范化 token，避免重复 'Bearer '
        normalized_token = self._normalize_token(token)

        # 构造请求头
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Authorization': normalized_token,
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://get-notes.luojilab.com',
            'Referer': 'https://get-notes.luojilab.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'X-Request-ID': str(int(time.time() * 1000)),
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        
        # 构造请求体
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
        
        try:
            # 打印详细请求信息（脱敏）
            masked_headers = self._mask_headers(headers)
            self.logger.info(f"API 请求: POST {self.base_url}")
            self.logger.info(f"请求头: {json.dumps(masked_headers, ensure_ascii=False)}")
            self.logger.info(f"请求体: {json.dumps(payload, ensure_ascii=False)[:2000]}")

            # 发送 POST 请求
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            # 打印详细响应信息
            self.logger.info(f"响应状态: {response.status_code}")
            try:
                resp_headers = dict(response.headers)
            except Exception:
                resp_headers = {}
            self.logger.info(f"响应头: {json.dumps(resp_headers, ensure_ascii=False)}")
            self.logger.info(f"响应体: {response.text[:4000]}")

            # 如果响应不是 2xx，记录错误信息
            if not response.ok:
                self.logger.warning(f"API 调用返回非成功状态: {response.status_code}")

            return response
            
        except requests.exceptions.Timeout:
            self.logger.error(f"API 调用超时: {self.base_url}")
            raise
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"API 连接错误: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API 请求异常: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"API 调用未知错误: {str(e)}")
            raise

    def _normalize_token(self, token: str) -> str:
        """
        规范化 Authorization token：
        - 如果已包含前缀 'Bearer '，原样返回；
        - 否则自动加上 'Bearer ' 前缀。

        :param token: 原始 token 字符串
        :return: 带前缀的标准 Authorization 值
        """
        if not token:
            return ''
        t = token.strip()
        return t if t.lower().startswith('bearer ') else f'Bearer {t}'

    def _mask_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """
        对敏感请求头进行脱敏，避免在日志中泄露凭证。

        :param headers: 原始请求头
        :return: 脱敏后的请求头副本
        """
        masked = dict(headers)
        auth = masked.get('Authorization')
        if isinstance(auth, str) and auth:
            # 仅显示 'Bearer ' 前缀和末尾 6 位，其他用 * 替代
            try:
                prefix = 'Bearer '
                raw = auth[len(prefix):] if auth.lower().startswith('bearer ') else auth
                tail = raw[-6:] if len(raw) >= 6 else raw
                masked['Authorization'] = f"Bearer ****{tail}"
            except Exception:
                masked['Authorization'] = '***'
        return masked
