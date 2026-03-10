#!/usr/bin/env python3
"""
基于LLM的知识图谱构建系统 - 通义千问版本
"""
import os
import sys
import json

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """主函数"""
    print("=" * 60)
    print("基于通义千问的知识图谱构建系统")
    print("=" * 60)
    
    try:
        # 动态导入模块
        print("\n📋 初始化系统...")
        
        # 1. 加载配置
        print("[1/5] 加载配置文件...")
        try:
            from config_loader import ConfigLoader
            config_loader = ConfigLoader()
            api_config = config_loader.get_api_config()
            
            if not api_config:
                print("❌ 配置文件加载失败")
                return
            
            print(f"✅ 使用API: {api_config.get('base_url', '未知')}")
            print(f"✅ 使用模型: {config_loader.get_model_id()}")
        except ImportError as e:
            print(f"❌ 导入config_loader失败: {e}")
            return
        
        # 2. 加载数据
        print("\n[2/5] 加载数据文件...")
        try:
            from data_loader import DataLoader
            loader = DataLoader()
            text = loader.load_text_file("data/sample.txt")
            
            if not text:
                print("❌ 数据文件加载失败")
                return
            
            print(f"✅ 加载文本长度: {len(text)} 字符")
            # 只处理前500个字符进行测试
            if len(text) > 500:
                text = text[:500]
                print(f"📝 使用前500字符进行测试: {text}")
        except ImportError as e:
            print(f"❌ 导入data_loader失败: {e}")
            return
        
        # 3. 测试Qwen API连接
        print("\n[3/5] 测试Qwen API连接...")
        try:
            from qwen_client import QwenAPIClient
            client = QwenAPIClient(
                api_key=api_config.get('api_key'),
                base_url=api_config.get('base_url')
            )
            
            if client.test_connection():
                print("✅ Qwen API连接成功")
            else:
                print("❌ Qwen API连接失败，请检查网络和配置")
                return
        except ImportError as e:
            print(f"❌ 导入qwen_client失败: {e}")
            return
        
        # 4. 抽取信息
        print("\n[4/5] 抽取信息...")
        print("这可能需要一些时间，请耐心等待...")
        
        try:
            from llm_extractor import QwenExtractor
            extractor = QwenExtractor()
            
            result = extractor.extract_from_text(text, max_length=500)
            
            if result:
                print(f"✅ 抽取完成:")
                print(f"  实体数量: {len(result.get('entities', []))}")
                print(f"  关系数量: {len(result.get('relations', []))}")
                
                # 保存结果
                output_dir = "data"
                os.makedirs(output_dir, exist_ok=True)
                
                result_file = os.path.join(output_dir, "qwen_extracted_data.json")
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 结果已保存到: {result_file}")
                
                # 显示部分结果
                if result.get("entities"):
                    print("\n📋 抽取到的实体（前5个）:")
                    for i, entity in enumerate(result["entities"][:5], 1):
                        print(f"  {i}. {entity.get('name', '无名')} ({entity.get('type', '未知')})")
                
                if result.get("relations"):
                    print("\n🔗 抽取到的关系（前5个）:")
                    for i, rel in enumerate(result["relations"][:5], 1):
                        print(f"  {i}. {rel.get('subject', '未知')} -> {rel.get('relation', '相关')} -> {rel.get('object', '未知')}")
            else:
                print("❌ 信息抽取失败")
                return
                
        except ImportError as e:
            print(f"❌ 导入QwenExtractor失败: {e}")
            return
        
        # 5. 构建知识图谱
        print("\n[5/5] 构建知识图谱...")
        try:
            from kg_builder import KnowledgeGraphBuilder
            
            builder = KnowledgeGraphBuilder()
            
            # 添加实体和关系
            if result.get("entities"):
                builder.add_entities(result["entities"])
            
            if result.get("relations"):
                builder.add_relations(result["relations"])
            
            # 可视化
            builder.visualize_simple()
            
            # 保存图谱
            builder.save_to_file("output/qwen_knowledge_graph.txt")
            
            print("✅ 知识图谱构建完成")
            
        except ImportError as e:
            print(f"❌ 导入kg_builder失败: {e}")
            return
        
    except Exception as e:
        print(f"❌ 系统运行出错: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("🎉 程序执行完成！")
    print("=" * 60)

def test_mode():
    """测试模式 - 使用简短文本快速测试"""
    print("\n🔧 测试模式")
    
    test_text = """清华大学位于北京，成立于1911年。
校长是王希勤。清华大学是中国著名的高等学府。"""
    
    print(f"测试文本: {test_text}")
    
    try:
        from qwen_client import QwenAPIClient
        from llm_extractor import QwenExtractor
        
        client = QwenAPIClient()
        
        if client.test_connection():
            extractor = QwenExtractor()
            result = extractor.extract_from_text(test_text, max_length=200)
            
            if result:
                print(f"\n✅ 测试成功！抽取到:")
                print(f"  实体: {len(result.get('entities', []))} 个")
                print(f"  关系: {len(result.get('relations', []))} 个")
                
                if result.get("entities"):
                    print("\n实体列表:")
                    for entity in result["entities"]:
                        print(f"  - {entity.get('name')} ({entity.get('type')})")
                        
                # 保存结果
                with open("data/qwen_test_result.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print("✅ 测试结果保存到: data/qwen_test_result.json")
            else:
                print("❌ 测试失败：抽取结果为空")
        else:
            print("❌ 测试失败：API连接失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    # 创建必要的目录
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    print("请选择运行模式:")
    print("1. 完整模式 (处理完整数据)")
    print("2. 测试模式 (快速测试)")
    
    try:
        choice = input("请输入选择 (1/2): ").strip()
        
        if choice == "2":
            test_mode()
        else:
            main()
            
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")