"""
数据加载模块 - 最简单的文件读取功能
"""
import os

class DataLoader:
    def __init__(self):
        """初始化数据加载器"""
        print("数据加载器已初始化")
    
    def load_text_file(self, file_path):
        """
        读取文本文件
        Args:
            file_path: 文件路径
        Returns:
            文件内容字符串
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"错误：文件 {file_path} 不存在")
                return ""
            
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            print(f"成功读取文件: {file_path}")
            print(f"文件长度: {len(content)} 字符")
            return content
            
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return ""
    
    def save_json(self, data, file_path):
        """
        保存数据为JSON文件
        Args:
            data: 要保存的数据（字典或列表）
            file_path: 保存路径
        """
        import json
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            print(f"数据已保存到: {file_path}")
            return True
        except Exception as e:
            print(f"保存文件时出错: {e}")
            return False

# 测试函数
def test_data_loader():
    """测试数据加载器"""
    print("=== 测试数据加载器 ===")
    
    # 创建数据加载器实例
    loader = DataLoader()
    
    # 测试读取文件
    content = loader.load_text_file("../data/sample.txt")
    
    # 显示前100个字符
    if content:
        print("\n文件内容预览:")
        print(content[:100] + "...")
    
    # 测试保存数据
    test_data = {
        "test": "这是一个测试",
        "count": 10,
        "items": ["苹果", "香蕉", "橙子"]
    }
    loader.save_json(test_data, "../data/test_output.json")

if __name__ == "__main__":
    test_data_loader()