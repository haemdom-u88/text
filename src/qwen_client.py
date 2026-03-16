#!/usr/bin/env python3
"""
阿里云通义千问API客户端
改进：使用环境变量读取API Key和Base URL，使用requests.Session并添加重试机制。
添加Token Bucket流控和指数退避重试。
"""
import os
import json
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TokenBucket:
    """Token Bucket for rate limiting"""
    def __init__(self, rate, capacity):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens=1):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class QwenAPIClient:
	def __init__(self, api_key=None, base_url=None, timeout=60, max_retries=3, rate_limit=10):
		"""
		初始化Qwen API客户端

		优先使用传入参数，其次使用环境变量 `QWEN_API_KEY`、`QWEN_BASE_URL`。
		添加Token Bucket流控，默认10 requests/second。
		"""
		default_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"

		# 优先级：传参 > 环境变量 > 默认
		self.api_key = api_key or os.environ.get('QWEN_API_KEY')
		self.base_url = base_url or os.environ.get('QWEN_BASE_URL', default_base)
		self.timeout = timeout

		# Token Bucket for rate limiting
		self.token_bucket = TokenBucket(rate=rate_limit, capacity=rate_limit * 2)

		# 不在日志中打印完整API Key
		masked_key = (self.api_key[:4] + '...' + self.api_key[-4:]) if self.api_key else 'None'

		# 配置会话与重试策略
		self.session = requests.Session()
		retries = Retry(total=max_retries, backoff_factor=1,
						status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['POST'])
		adapter = HTTPAdapter(max_retries=retries)
		self.session.mount('https://', adapter)
		self.session.mount('http://', adapter)

		self.headers = {
			"Content-Type": "application/json",
		}
		if self.api_key:
			self.headers["Authorization"] = f"Bearer {self.api_key}"

		print(f"Qwen API客户端初始化完成，基础URL: {self.base_url}，api_key={masked_key}，rate_limit={rate_limit}/s")

	def chat_completion(self, messages, model=None, temperature=0.3, max_tokens=2000):
		"""
		调用聊天补全接口
		添加Token Bucket流控和指数退避重试。
		"""
		model = model or "qwen-max"

		payload = {
			"model": model,
			"messages": messages,
			"temperature": temperature,
			"max_tokens": max_tokens,
			"stream": False
		}

		url = f"{self.base_url}/chat/completions"

		max_attempts = 5
		base_delay = 1  # seconds

		for attempt in range(max_attempts):
			# Wait for token bucket
			while not self.token_bucket.consume():
				time.sleep(0.1)  # Wait 100ms before checking again

			try:
				print(f"正在调用模型: {model}，URL: {url}，尝试 {attempt + 1}/{max_attempts}")
				resp = self.session.post(url, headers=self.headers, json=payload, timeout=self.timeout)
				if resp.status_code == 200:
					result = resp.json()
					if "choices" in result and len(result["choices"]) > 0:
						reply = result["choices"][0]["message"]["content"]
						print(f"API调用成功，返回token数: {result.get('usage', {}).get('total_tokens', '未知')}")
						return reply
					else:
						print(f"API响应格式异常: {result}")
						return None
				elif resp.status_code == 429:  # Rate limit exceeded
					delay = base_delay * (2 ** attempt)  # Exponential backoff
					print(f"QPS限流，等待 {delay} 秒后重试...")
					time.sleep(delay)
					continue
				else:
					print(f"API调用失败，状态码: {resp.status_code}")
					print(f"响应内容: {resp.text}")
					return None

			except Exception as e:
				delay = base_delay * (2 ** attempt)
				print(f"API调用异常: {e}，等待 {delay} 秒后重试...")
				time.sleep(delay)
				continue

		print("达到最大重试次数，API调用失败")
		return None

	def simple_chat(self, prompt, system_prompt=None, model=None):
		messages = []
		if system_prompt:
			messages.append({"role": "system", "content": system_prompt})
		messages.append({"role": "user", "content": prompt})
		return self.chat_completion(messages, model=model)

	def generate(self, prompt: str, system_prompt: str = None, model: str = None, temperature: float = 0.3, max_tokens: int = 2000):
		"""
		统一的文本生成接口，兼容其它客户端的 `generate()` 调用。

		Args:
			prompt: 主提示词
			system_prompt: 系统角色设定
			model: 模型ID
			temperature: 采样温度
			max_tokens: 最大生成长度

		Returns:
			str | None: 模型返回文本
		"""
		messages = []
		if system_prompt:
			messages.append({"role": "system", "content": system_prompt})
		messages.append({"role": "user", "content": prompt})
		return self.chat_completion(messages, model=model, temperature=temperature, max_tokens=max_tokens)

	def structured_extract(self, schema_hint: str, input_text: str, model: str = None):
		"""
		结构化生成抽取：强制JSON输出，便于入库或前端使用。

		Args:
			schema_hint: 对输出JSON结构的明确说明（字段、枚举、约束）
			input_text: 待抽取文本
			model: 模型ID

		Returns:
			str | None: 原始文本回复（期望为JSON字符串）
		"""
		prompt = (
			"你是一位资深的课程设计专家。请严格按如下JSON Schema输出，不要包含解释：\n"
			f"Schema: {schema_hint}\n"
			f"输入文本：\n{input_text}"
		)
		return self.simple_chat(prompt, system_prompt="结构化抽取助手", model=model)

	def test_connection(self):
		print("正在测试Qwen API连接...")
		test_prompt = "请回复'Qwen API连接成功'"
		response = self.simple_chat(test_prompt, model="qwen-turbo")
		if response and "API连接成功" in response:
			print("✅ Qwen API连接测试成功！")
			return True
		else:
			print(f"❌ Qwen API连接测试失败，响应: {response}")
			return False


def test_qwen_client():
	print("=== 测试Qwen API客户端 ===")
	client = QwenAPIClient()
	if client.test_connection():
		print("\n测试简单对话...")
		response = client.simple_chat("你好，请简单介绍一下你自己", system_prompt="你是一个知识图谱构建助手")
		print(f"\nAI回复: {response}")


if __name__ == "__main__":
	test_qwen_client()

