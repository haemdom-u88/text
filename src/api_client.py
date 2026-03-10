"""
DeepSeek API客户端封装
"""
import requests
import json
import time
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class DeepSeekAPIClient:
    def __init__(self, api_key=None, base_url=None, appid=None):
        """
        初始化API客户端
        
        Args:
            api_key: API密钥
            base_url: API基础地址
            appid: 应用ID
        """
        # 优先使用参数，其次使用环境变量
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://maas-api.cn-huabei-1.xf-yun.com/v1")
        self.appid = appid or os.getenv("DEEPSEEK_APPID", "")
        
        # 请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "App-Id": self.appid
        }

        # 使用 Session 复用连接，添加重试策略和连接池以提高并发稳定性
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5,
                        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"]) 
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        print(f"API客户端初始化完成，基础URL: {self.base_url}")
    
    def chat_completion(self, messages, model=None, temperature=0.3, max_tokens=2000):
        """
        调用聊天补全接口
        
        Args:
            messages: 消息列表，格式如 [{"role": "user", "content": "..."}]
            model: 模型ID，默认使用DeepSeek V3.2
            temperature: 温度参数（0-1）
            max_tokens: 最大生成token数
        
        Returns:
            API响应内容
        """
        # 默认使用DeepSeek V3.2
        model = model or "xopdeepseekv3.2"
        
        # 构造请求数据
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False  # 非流式响应
        }
        
        # 构造完整URL
        url = f"{self.base_url}/chat/completions"
        
        try:
            print(f"正在调用模型: {model}")
            print(f"请求URL: {url}")
            
            # 发送请求（使用 session 以复用连接）
            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60  # 60秒超时
            )
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                
                # 提取回复内容
                if "choices" in result and len(result["choices"]) > 0:
                    reply = result["choices"][0]["message"]["content"]
                    print(f"API调用成功，返回token数: {result.get('usage', {}).get('total_tokens', '未知')}")
                    return reply
                else:
                    print(f"API响应格式异常: {result}")
                    return None
                    
            else:
                print(f"API调用失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            print(f"API调用异常: {e}")
            return None
    
    def simple_chat(self, prompt, system_prompt=None, model=None):
        """
        简单聊天接口
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            model: 模型ID
        
        Returns:
            AI回复内容
        """
        # 构造消息列表
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        # 调用API
        return self.chat_completion(messages, model=model)
    
    def test_connection(self):
        """
        测试API连接
        
        Returns:
            bool: 连接是否成功
        """
        print("正在测试API连接...")
        
        test_prompt = "请回复'API连接成功'"
        response = self.simple_chat(test_prompt, model="xopdeepseekv3.2")
        
        if response and "API连接成功" in response:
            print("✅ API连接测试成功！")
            return True
        else:
            print(f"❌ API连接测试失败，响应: {response}")
            return False

# 测试函数
def test_api_client():
    """测试API客户端"""
    print("=== 测试DeepSeek API客户端 ===")
    
    # 创建客户端实例
    client = DeepSeekAPIClient()
    
    # 测试连接
    if client.test_connection():
        # 测试简单对话
        print("\n测试简单对话...")
        response = client.simple_chat(
            "你好，请简单介绍一下你自己",
            system_prompt="你是一个知识图谱构建助手"
        )
        
        print(f"\nAI回复: {response}")
        
        # 测试不同模型
        print("\n测试不同模型...")
        models = ["xopdeepseekv3.2", "xop3gwenlh7"]
        
        for model in models:
            print(f"\n使用模型: {model}")
            response = client.simple_chat(
                "知识图谱是什么？用一句话回答",
                model=model
            )
            print(f"回复: {response[:50]}...")  # 只显示前50个字符

if __name__ == "__main__":
    test_api_client()