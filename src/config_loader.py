"""
配置加载器 - 适配Qwen API
"""
import json
import os
import logging

class ConfigLoader:
    def __init__(self, config_path=None):
        """
        初始化配置加载器
        """
        if config_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "..", "config", "api_config.yaml")
        
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"尝试加载配置文件: {self.config_path}")
        self.config = self.load_config()
    
    def load_config(self):
        """
        加载配置文件
        """
        # 先尝试使用JSON解析（避免yaml依赖问题）
        try:
            # 如果是JSON文件
            if self.config_path.endswith('.json'):
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    config = json.load(file)
            else:
                # 尝试YAML
                try:
                    import yaml
                    with open(self.config_path, 'r', encoding='utf-8') as file:
                        config = yaml.safe_load(file)
                except ImportError:
                    # 如果没有yaml，返回默认配置
                    self.logger.warning("PyYAML未安装，使用默认配置")
                    return self.get_default_config()
                
            self.logger.info(f"配置文件加载成功: {self.config_path}")
            return config or {}
            
        except FileNotFoundError:
            self.logger.warning(f"配置文件不存在: {self.config_path}")
            return self.get_default_config()
        except Exception as e:
            self.logger.error(f"加载配置文件时出错: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """获取默认配置"""
        return {
            "qwen_api": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "",
                "models": {
                    "qwen_max": "qwen-max",
                    "qwen_plus": "qwen-plus",
                    "qwen_turbo": "qwen-turbo"
                },
                "default_params": {
                    "temperature": 0.3,
                    "max_tokens": 2000,
                    "timeout": 60
                }
            }
        }
    
    def get_api_config(self):
        """获取API配置"""
        return self.config.get("qwen_api", {})
    
    def get_prompts(self):
        """获取提示词模板"""
        return self.config.get("prompts", {})
    
    def get_model_id(self, model_name="qwen_turbo"):
        """获取模型ID"""
        models = self.config.get("qwen_api", {}).get("models", {})
        return models.get(model_name, "qwen-turbo")
    
    def get_base_url(self):
        """获取基础URL"""
        return os.getenv("QWEN_BASE_URL") or self.config.get("qwen_api", {}).get("base_url", "")
    
    def get_api_key(self):
        """获取API密钥"""
        return os.getenv("QWEN_API_KEY") or self.config.get("qwen_api", {}).get("api_key", "")
    
    def get_default_params(self):
        """获取默认参数"""
        return self.config.get("qwen_api", {}).get("default_params", {})

# 测试函数
def test_config_loader():
    """测试配置加载器"""
    logger = logging.getLogger(__name__)
    logger.info("开始测试配置加载器")
    loader = ConfigLoader()
    config = loader.config
    logger.info(f"API基础URL: {loader.get_base_url()}")
    logger.info(f"可用模型: {loader.get_api_config().get('models', {})}")
    logger.info(f"提示词模板数量: {len(loader.get_prompts())}")

if __name__ == "__main__":
    test_config_loader()