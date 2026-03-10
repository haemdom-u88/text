"""
知识图谱构建器 - 使用NetworkX创建和可视化图谱
"""
import matplotlib.pyplot as plt

class KnowledgeGraphBuilder:
    def __init__(self):
        """初始化知识图谱构建器"""
        print("知识图谱构建器已初始化")
        self.nodes = []  # 存储节点
        self.edges = []  # 存储边
        self.node_count = 0
    
    def add_entities(self, entities):
        """
        添加实体到图谱
        Args:
            entities: 实体列表，每个实体是字典格式
        """
        for entity in entities:
            node_id = f"entity_{self.node_count}"
            self.nodes.append({
                "id": node_id,
                "name": entity["name"],
                "type": entity["type"]
            })
            self.node_count += 1
        print(f"已添加 {len(entities)} 个实体")
    
    def add_relations(self, relations):
        """
        添加关系到图谱
        Args:
            relations: 关系列表，每个关系是字典格式
        """
        for relation in relations:
            self.edges.append({
                "subject": relation["subject"],
                "relation": relation["relation"],
                "object": relation["object"]
            })
        print(f"已添加 {len(relations)} 个关系")

    def build(self, extracted_data):
        """
        根据抽取结果构建图谱并返回用于前端可视化的结构
        Args:
            extracted_data: 包含 'entities' 和 'relations' 的字典
        Returns:
            dict: { 'nodes': [...], 'edges': [...] }
        """
        # 重置内部存储，避免重复累积
        self.nodes = []
        self.edges = []
        self.node_count = 0

        entities = extracted_data.get('entities', []) if isinstance(extracted_data, dict) else []
        relations = extracted_data.get('relations', []) if isinstance(extracted_data, dict) else []

        # 添加并构建可视化友好的节点/边
        self.add_entities(entities)
        self.add_relations(relations)

        # 转换边为前端常用的 source/target 结构
        edges_out = []
        for e in self.edges:
            edges_out.append({
                'source': e.get('subject'),
                'target': e.get('object'),
                'relation': e.get('relation')
            })

        return {
            'nodes': self.nodes,
            'edges': edges_out
        }
    
    def visualize_simple(self):
        """
        简单可视化（文本形式）
        """
        print("\n=== 知识图谱（文本视图）===")
        
        print("\n实体节点:")
        for i, node in enumerate(self.nodes, 1):
            print(f"{i}. {node['name']} [{node['type']}]")
        
        print("\n关系边:")
        for i, edge in enumerate(self.edges, 1):
            print(f"{i}. {edge['subject']} --[{edge['relation']}]--> {edge['object']}")
    
    def save_to_file(self, filename="knowledge_graph.txt"):
        """
        将图谱保存到文件
        Args:
            filename: 文件名
        """
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=== 知识图谱 ===\n\n")
            
            f.write("实体列表:\n")
            for node in self.nodes:
                f.write(f"- {node['name']} ({node['type']})\n")
            
            f.write("\n关系列表:\n")
            for edge in self.edges:
                f.write(f"- {edge['subject']} {edge['relation']} {edge['object']}\n")
        
        print(f"知识图谱已保存到: {filename}")
        return filename

# 测试函数
def test_kg_builder():
    """测试知识图谱构建器"""
    print("=== 测试知识图谱构建器 ===")
    
    # 创建测试数据
    test_entities = [
        {"name": "苹果公司", "type": "公司"},
        {"name": "史蒂夫·乔布斯", "type": "人物"},
        {"name": "iPhone", "type": "产品"}
    ]
    
    test_relations = [
        {"subject": "史蒂夫·乔布斯", "relation": "创立了", "object": "苹果公司"},
        {"subject": "苹果公司", "relation": "生产", "object": "iPhone"}
    ]
    
    # 创建构建器实例
    builder = KnowledgeGraphBuilder()
    
    # 添加实体和关系
    builder.add_entities(test_entities)
    builder.add_relations(test_relations)
    
    # 可视化
    builder.visualize_simple()
    
    # 保存到文件
    builder.save_to_file("test_kg.txt")

if __name__ == "__main__":
    test_kg_builder()

# Debug: 输出模块加载信息，便于诊断运行时是否使用了正确的文件
try:
    print(f"kg_builder module loaded from: {__file__}")
    print(f"KnowledgeGraphBuilder has build: {hasattr(KnowledgeGraphBuilder, 'build')}")
except Exception:
    pass