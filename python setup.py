#!/usr/bin/env python3
"""
项目环境设置脚本 - 简洁版本
"""
import os
import sys
import subprocess

def main():
    """主函数"""
    print("=" * 60)
    print("知识图谱构建系统 - 环境设置")
    print("=" * 60)
    
    # 1. 检查Python版本
    print("\n检查Python版本...")
    if sys.version_info < (3, 7):
        print(f"错误: 需要Python 3.7或更高版本，当前: {sys.version}")
        return
    print(f"当前Python版本: {sys.version}")
    
    # 2. 创建目录结构
    print("\n创建项目目录...")
    directories = ["data", "output", "config", "logs"]
    
    for dir_name in directories:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✅ 创建: {dir_name}/")
        else:
            print(f"📁 已存在: {dir_name}/")
    
    # 3. 检查并创建配置文件（如果不存在）
    print("\n检查配置文件...")
    config_path = "config/api_config.yaml"
    
    if os.path.exists(config_path):
        print(f"📄 配置文件已存在: {config_path}")
        print("注意：如果API密钥不正确，请手动编辑此文件")
    else:
        print("创建配置文件...")
        config_content = """# DeepSeek API 配置
deepseek_api:
    base_url: "https://masis-api.cn-huabei-1.af-yun.com/v1"
    api_key: "YOUR_API_KEY_HERE"
    appid: "YOUR_APP_ID_HERE"
  
  models:
    deepseek_v3_2: "xopdeepseekv3.2"
    gwash_jtb: "xop3gwenlh7"
    deepseek_70b: "xdeegseekrlliama70b"
  
  default_params:
    temperature: 0.3
    max_tokens: 2000
    timeout: 60
    stream: false

# 项目配置
project:
  name: "基于LLM的知识图谱构建系统"
  version: "2.0"
"""
        
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        print(f"✅ 创建: {config_path}")
    
    # 4. 创建requirements.txt
    print("\n创建依赖文件...")
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write("requests>=2.31.0\n")
        f.write("networkx>=3.1\n")
        f.write("matplotlib>=3.7.2\n")
        f.write("pyyaml>=6.0\n")
    print("✅ 创建: requirements.txt")
    
    # 5. 检查数据文件
    print("\n检查数据文件...")
    data_files = ["data/sample.txt", "data/test.txt"]
    
    for file_path in data_files:
        if not os.path.exists(file_path):
            if "sample.txt" in file_path:
                content = """苹果公司是一家美国科技公司，总部位于加利福尼亚。
史蒂夫·乔布斯是苹果公司的创始人之一。
iPhone是苹果公司的主要产品。"""
            else:
                content = "清华大学是中国著名高等学府，位于北京。"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ 创建: {file_path}")
        else:
            print(f"📄 已存在: {file_path}")
    
    # 6. 询问是否安装依赖
    print("\n" + "=" * 60)
    print("✅ 环境设置完成！")
    
    answer = input("\n是否现在安装依赖包？(y/N): ").strip().lower()
    if answer == 'y':
        print("\n开始安装依赖...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
            print("✅ 依赖安装完成！")
        except subprocess.CalledProcessError:
            print("❌ 依赖安装失败，请手动运行: pip install -r requirements.txt")
    else:
        print("\n可以稍后手动安装依赖: pip install -r requirements.txt")
    
    print("\n下一步:")
    print("1. 运行主程序: python main.py")
    print("2. 测试API连接: 运行 main.py 并选择测试模式")
    print("=" * 60)

if __name__ == "__main__":
    main()