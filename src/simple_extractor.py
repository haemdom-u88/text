"""
基础信息抽取器 - 不使用LLM，先用规则实现
"""
import re

class SimpleExtractor:
    def __init__(self):
        """初始化抽取器"""
        self.entity_types = {
            "公司": ["公司", "集团", "企业"],
            "人物": ["创始人", "CEO", "总裁", "主席"],
            "产品": ["手机", "电脑", "平板", "手表", "耳机"],
            "地点": ["总部", "位于", "在"]
        }
        print("基础抽取器已初始化")
    
    def extract_entities_by_rules(self, text):
        """
        使用简单规则抽取实体
        Args:
            text: 输入文本
        Returns:
            实体列表，每个实体是 (类型, 名称) 的元组
        """
        entities = []
        
        # 规则1：提取括号中的内容（通常是英文名或简称）
        quoted = re.findall(r'（(.*?)）|\((.*?)\)', text)
        for q in quoted:
            for item in q:
                if item:
                    entities.append(("英文名", item))
        
        # 规则2：提取"XX公司"模式
        company_pattern = r'([\u4e00-\u9fa5a-zA-Z0-9]+公司)'
        companies = re.findall(company_pattern, text)
        entities.extend([("公司", company) for company in companies])
        
        # 规则3：提取"XX产品"模式
        product_pattern = r'([\u4e00-\u9fa5a-zA-Z0-9]+手机|[\u4e00-\u9fa5a-zA-Z0-9]+电脑|[\u4e00-\u9fa5a-zA-Z0-9]+平板|[\u4e00-\u9fa5a-zA-Z0-9]+手表)'
        products = re.findall(product_pattern, text)
        entities.extend([("产品", product) for product in products])
        
        # 规则4：提取人名（连续的中文字符，长度2-4）
        name_pattern = r'([\u4e00-\u9fa5]{2,4})'
        possible_names = re.findall(name_pattern, text)
        
        # 过滤掉常见非人名词汇
        non_names = {"美国", "公司", "位于", "包括", "现任", "全球", "称为", "拥有"}
        for name in possible_names:
            if name not in non_names:
                entities.append(("人物", name))
        
        # 去重
        entities = list(set(entities))
        return entities
    
    def extract_relations_by_rules(self, text):
        """
        使用简单规则抽取关系
        Args:
            text: 输入文本
        Returns:
            关系列表，每个关系是 (主体, 关系词, 客体) 的元组
        """
        relations = []
        
        # 分割成句子
        sentences = re.split('[。，；]', text)
        
        for sentence in sentences:
            # 规则1：寻找"是"关系
            if '是' in sentence and '公司' in sentence:
                parts = sentence.split('是')
                if len(parts) >= 2:
                    subject = parts[0].strip()
                    object_text = '是'.join(parts[1:]).strip()
                    if subject and object_text:
                        relations.append((subject, '是', object_text))
            
            # 规则2：寻找"位于"关系
            if '位于' in sentence:
                parts = sentence.split('位于')
                if len(parts) == 2:
                    subject = parts[0].strip()
                    location = parts[1].strip()
                    if subject and location:
                        relations.append((subject, '位于', location))
            
            # 规则3：寻找"由...创立"关系
            if '由' in sentence and '创立' in sentence:
                # 简化处理
                founder_match = re.search(r'由([\u4e00-\u9fa5、]+)创立', sentence)
                if founder_match:
                    founders = founder_match.group(1)
                    company_match = re.search(r'([\u4e00-\u9fa5a-zA-Z0-9]+公司)', sentence)
                    if company_match:
                        company = company_match.group(1)
                        for founder in founders.split('、'):
                            relations.append((founder.strip(), '创立了', company))
        
        return relations
    
    def extract_all(self, text):
        """
        提取所有信息
        Args:
            text: 输入文本
        Returns:
            包含实体和关系的字典
        """
        entities = self.extract_entities_by_rules(text)
        relations = self.extract_relations_by_rules(text)
        
        result = {
            "entities": [],
            "relations": []
        }
        
        # 格式化实体
        for entity_type, entity_name in entities:
            result["entities"].append({
                "name": entity_name,
                "type": entity_type
            })
        
        # 格式化关系
        for subject, relation, obj in relations:
            result["relations"].append({
                "subject": subject,
                "relation": relation,
                "object": obj
            })
        
        return result

# 测试函数
def test_extractor():
    """测试抽取器"""
    print("=== 测试基础抽取器 ===")
    
    # 测试文本
    test_text = "苹果公司是一家美国科技公司，由史蒂夫·乔布斯创立。"
    
    # 创建抽取器实例
    extractor = SimpleExtractor()
    
    # 抽取信息
    result = extractor.extract_all(test_text)
    
    # 显示结果
    print(f"测试文本: {test_text}")
    print(f"\n抽取到的实体:")
    for entity in result["entities"]:
        print(f"  - {entity['name']} ({entity['type']})")
    
    print(f"\n抽取到的关系:")
    for relation in result["relations"]:
        print(f"  - {relation['subject']} {relation['relation']} {relation['object']}")

if __name__ == "__main__":
    test_extractor()