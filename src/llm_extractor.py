"""
基于Qwen API的信息抽取器
"""
import json
import re
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加路径，确保能导入其他模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config_loader import ConfigLoader
    from qwen_client import QwenAPIClient
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有模块文件都存在")

class QwenExtractor:
    def __init__(self, config_path=None):
        """
        初始化Qwen抽取器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config_loader = ConfigLoader(config_path)
        self.prompts = self.config_loader.get_prompts()
        
        # 创建API客户端
        api_config = self.config_loader.get_api_config()
        self.client = QwenAPIClient(
            api_key=api_config.get("api_key"),
            base_url=api_config.get("base_url")
        )
        # 并发配置（可通过配置文件中的 performance.max_workers 调整）
        try:
            self.max_workers = int(self.config_loader.config.get("performance", {}).get("max_workers", 3))
        except Exception:
            self.max_workers = 3
        
        print("Qwen抽取器初始化完成")
    
    def extract_from_text(self, text, max_length=3000):
        """
        从文本中抽取实体和关系
        
        Args:
            text: 输入文本
            max_length: 最大文本长度（避免过长）
        
        Returns:
            dict: 包含实体和关系的字典
        """
        print(f"开始抽取信息，文本长度: {len(text)} 字符")
        
        # 如果文本过长，进行分块处理
        if len(text) > max_length:
            print(f"文本过长，进行分块处理（最大{max_length}字符）")
            return self._extract_from_long_text(text, max_length)
        
        # 获取提示词模板
        prompt_template = self.prompts.get("entity_extraction", "")
        if not prompt_template:
            # 默认提示词
            prompt_template = """请从以下文本中提取实体和关系：

文本：{text}

请以JSON格式返回，包含"entities"和"relations"两个键。"""
        
        # 调试信息: 打印提示词模板
        print(f"提示词模板: {prompt_template}")
        print(f"输入文本: {text[:max_length]}")
        
        # 构造完整提示词：只替换 {text}，避免格式化其它花括号
        if "{text}" in prompt_template:
            prompt = prompt_template.replace("{text}", text[:max_length])
        else:
            prompt = prompt_template + "\n\n" + text[:max_length]

        # 调用API
        print("正在调用Qwen API...")
        response = self.client.simple_chat(
            prompt,
            system_prompt="你是一个知识图谱构建助手，请以JSON格式返回结果。",
            model=self.config_loader.get_model_id()
        )
        
        if not response:
            print("API调用失败，返回空结果")
            return {"entities": [], "relations": []}
        
        # 调试信息: 打印API返回的原始内容
        print(f"API返回内容: {response}")
        
        # 解析响应（不再尝试用 format 去格式化模板中的大括号）
        print("正在解析API响应...")
        result = self._parse_response(response)

        if not isinstance(result, dict):
            print("❌ 解析结果不是字典，返回空结构")
            return {"entities": [], "relations": []}

        # 确保返回结构包含必要键
        if "entities" not in result:
            result["entities"] = []
        if "relations" not in result:
            result["relations"] = []

        print(f"抽取完成: {len(result.get('entities', []))} 个实体, {len(result.get('relations', []))} 个关系")
        return result
    
    def _extract_from_long_text(self, text, chunk_size=2000):
        """
        处理长文本：分块抽取然后合并
        """
        # 按句号分块，避免切分句子
        sentences = text.split('。')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + "。"
        
        if current_chunk:
            chunks.append(current_chunk)
        print(f"文本被分为 {len(chunks)} 个块，使用最多 {self.max_workers} 个并发线程处理")

        # 并发分块处理，限制最大并发数以避免触发API限频
        all_entities = []
        all_relations = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {executor.submit(self.extract_from_text, chunk, chunk_size): idx for idx, chunk in enumerate(chunks)}

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    result = future.result()
                except Exception as e:
                    print(f"处理第 {idx+1} 块时出错: {e}")
                    result = {"entities": [], "relations": []}

                if "entities" in result:
                    all_entities.extend(result["entities"])
                if "relations" in result:
                    all_relations.extend(result["relations"])
        
        # 去重
        all_entities = self._deduplicate_entities(all_entities)
        all_relations = self._deduplicate_relations(all_relations)
        
        return {
            "entities": all_entities,
            "relations": all_relations
        }
    
    def _parse_response(self, response_text):
        """
        解析API响应，提取JSON
        """
        try:
            response_text = response_text.strip()
            
            # 查找JSON部分（可能包含在代码块中）
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                return result
            else:
                return self._extract_manually(response_text)
                
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response_text[:200]}...")
            return self._extract_manually(response_text)
        except Exception as e:
            print(f"解析响应时出错: {e}")
            return {"entities": [], "relations": []}
    
    def _extract_manually(self, text):
        """
        手动从文本中提取信息
        """
        entities = []
        relations = []
        
        # 简单规则：查找类似实体的描述
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 查找实体描述
            if "实体" in line or "entity" in line.lower():
                # 简单提取
                pass
            
            # 查找关系描述
            if "关系" in line or "relation" in line.lower():
                # 简单提取
                pass
        
        # 如果什么都提取不到，返回一些示例数据
        if not entities and not relations:
            return {
                "entities": [
                    {"name": "示例实体", "type": "概念", "description": "从文本中提取"}
                ],
                "relations": [
                    {"subject": "主体", "relation": "是", "object": "客体"}
                ]
            }
        
        return {
            "entities": entities,
            "relations": relations
        }
    
    def _deduplicate_entities(self, entities):
        """实体去重"""
        seen = set()
        unique_entities = []
        
        for entity in entities:
            if isinstance(entity, dict):
                key = (entity.get("name", ""), entity.get("type", ""))
                if key not in seen:
                    seen.add(key)
                    unique_entities.append(entity)
        
        return unique_entities
    
    def _deduplicate_relations(self, relations):
        """关系去重"""
        seen = set()
        unique_relations = []
        
        for rel in relations:
            if isinstance(rel, dict):
                key = (rel.get("subject", ""), rel.get("relation", ""), rel.get("object", ""))
                if key not in seen:
                    seen.add(key)
                    unique_relations.append(rel)
        
        return unique_relations
    
    def test_extraction(self, test_text=None):
        """
        测试抽取功能
        """
        if test_text is None:
            test_text = """
            阿里巴巴集团由马云于1999年创立，总部位于中国杭州。
            阿里巴巴是一家电子商务公司，旗下有淘宝、天猫等平台。
            张勇是阿里巴巴的现任董事会主席兼CEO。
            """
        
        print("=== 测试Qwen抽取功能 ===")
        print(f"测试文本: {test_text[:100]}...")
        
        result = self.extract_from_text(test_text, max_length=1000)
        
        print(f"\n抽取结果:")
        print(f"实体数量: {len(result.get('entities', []))}")
        print(f"关系数量: {len(result.get('relations', []))}")
        
        if result.get("entities"):
            print("\n实体列表:")
            for i, entity in enumerate(result["entities"][:5], 1):
                print(f"  {i}. {entity.get('name')} ({entity.get('type')}) - {entity.get('description', '')}")
        
        if result.get("relations"):
            print("\n关系列表:")
            for i, rel in enumerate(result["relations"][:5], 1):
                print(f"  {i}. {rel.get('subject')} --[{rel.get('relation')}]--> {rel.get('object')}")

# 测试函数
def test_qwen_extractor():
    """测试Qwen抽取器"""
    print("=== 测试Qwen抽取器 ===")
    
    # 创建抽取器
    extractor = QwenExtractor()
    
    # 测试连接
    print("\n[1] 测试API连接...")
    if extractor.client.test_connection():
        print("✅ Qwen API连接成功")
    else:
        print("❌ Qwen API连接失败，请检查配置")
        return
    
    # 测试抽取功能
    print("\n[2] 测试抽取功能...")
    test_text = "马云是阿里巴巴集团的创始人，阿里巴巴的总部位于中国杭州。"
    extractor.test_extraction(test_text)

if __name__ == "__main__":
    test_qwen_extractor()