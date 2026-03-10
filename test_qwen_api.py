#!/usr/bin/env python3
"""
测试通义千问API
"""
import requests
import json
import os
from dotenv import load_dotenv

def test_qwen_api():
    """直接测试API"""
    load_dotenv()
    print("=" * 60)
    print("测试通义千问API")
    print("=" * 60)
    
    # 你的API配置（建议从环境变量读取）
    API_KEY = os.getenv("QWEN_API_KEY", "").strip()
    BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    if not API_KEY:
        print("❌ 未检测到 QWEN_API_KEY，请先在环境变量或 .env 中配置")
        return False
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 测试不同的模型
    models = [
        ("qwen-turbo", "快速版本"),
        ("qwen-plus", "增强版本"),
        ("qwen-max", "最强版本")
    ]
    
    for model_id, model_desc in models:
        print(f"\n测试模型: {model_desc} ({model_id})")
        
        data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "你是一个测试助手"},
                {"role": "user", "content": "请回复'通义千问API测试成功'"}
            ],
            "temperature": 0.3,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result:
                    reply = result["choices"][0]["message"]["content"]
                    print(f"✅ {model_desc} 测试成功！回复: {reply}")
                    
                    # 显示使用情况
                    if "usage" in result:
                        usage = result["usage"]
                        print(f"  Token使用: 输入{usage.get('prompt_tokens')}, 输出{usage.get('completion_tokens')}")
                    
                    return True
                else:
                    print(f"❌ 响应格式错误: {result}")
            else:
                error_msg = response.text
                print(f"❌ 请求失败: {error_msg[:200]}")
                
        except Exception as e:
            print(f"❌ 连接错误: {e}")
    
    return False

if __name__ == "__main__":
    if test_qwen_api():
        print("\n" + "=" * 60)
        print("✅ API测试成功！可以运行主程序了")
        print("运行: python main.py")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ API测试失败，请检查:")
        print("1. API密钥是否正确")
        print("2. 网络连接是否正常")
        print("3. 账户是否有余额")
        print("=" * 60)