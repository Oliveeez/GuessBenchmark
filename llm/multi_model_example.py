"""
多模型支持的图片 LLM API 使用示例
支持 OpenAI、阿里云 DashScope、Azure、Anthropic 等多种模型
"""

import os
from unified_client import create_client_from_config

def example_single_image():
    """单图片处理示例"""
    try:
        # 创建统一客户端（自动从配置文件加载）
        client = create_client_from_config()
        
        print("🔧 当前配置:")
        client.print_current_config()
        print()
        
        # 指定图片路径和提示词
        image_path = "./data/emoji_source/apple.png"  # 使用项目中的 emoji 图片
        prompt = "请描述这张图片显示的是什么物品或符号？"
        
        if not os.path.exists(image_path):
            print(f"图片文件不存在: {image_path}")
            print("请确保项目结构正确，或修改 image_path 为实际存在的图片路径")
            return
        
        print("正在处理图片...")
        result = client.send_image_with_prompt(image_path, prompt)
        
        if result["success"]:
            print("\n=== LLM 分析结果 ===")
            print(f"回答: {result['response']}")
            print(f"\n使用模型: {result['model']}")
            if 'usage' in result:
                print(f"Token 使用: {result['usage']}")
        else:
            print(f"\n错误: {result['error']}")
            if 'details' in result:
                print(f"详细信息: {result['details']}")
                
    except Exception as e:
        print(f"❌ 创建客户端失败: {e}")
        print("请检查配置文件是否存在且配置正确")

def example_batch_processing():
    """批量处理示例"""
    try:
        client = create_client_from_config()
        
        # 批量处理文件夹中的图片
        image_folder = "./data/test"
        prompt = "这是什么 emoji 表情或符号？请用中文简洁回答。"
        output_file = "emoji_analysis_results.json"
        
        if not os.path.exists(image_folder):
            print(f"图片文件夹不存在: {image_folder}")
            print("请确保项目结构正确，或修改 image_folder 为实际存在的文件夹路径")
            return
        
        print("开始批量处理 emoji 图片...")
        result = client.batch_process_images(
            image_folder=image_folder,
            prompt=prompt,
            output_file=output_file
        )
        
        if result["success"]:
            print(f"\n✓ 批量处理完成！")
            print(f"总共处理了 {result['total_images']} 张图片")
            print(f"结果已保存到: {output_file}")
        else:
            print(f"\n✗ 批量处理失败: {result['error']}")
            
    except Exception as e:
        print(f"❌ 批量处理失败: {e}")

def show_provider_menu():
    """显示提供商选择菜单"""
    try:
        client = create_client_from_config()
        
        print("\n=== 可用的模型提供商 ===")
        providers = client.list_available_providers()
        
        available_providers = []
        for i, (provider, info) in enumerate(providers.items(), 1):
            status = "🎯" if provider == client.get_current_provider() else "  "
            print(f"{status} {i}. {info['name']}: {info['model']} - {info['status']}")
            if "✅" in info['status']:
                available_providers.append(provider)
        
        if len(available_providers) > 1:
            print(f"\n当前使用: {client.get_current_provider()}")
            choice = input("是否要切换提供商？(y/N): ").strip().lower()
            
            if choice == 'y':
                print("\n请选择提供商:")
                for i, provider in enumerate(available_providers, 1):
                    info = providers[provider]
                    print(f"{i}. {info['name']}")
                
                try:
                    idx = int(input("请输入编号: ")) - 1
                    if 0 <= idx < len(available_providers):
                        selected_provider = available_providers[idx]
                        if client.switch_provider(selected_provider):
                            print(f"✅ 已切换到: {providers[selected_provider]['name']}")
                            return client
                        else:
                            print("❌ 切换失败")
                    else:
                        print("❌ 无效的选择")
                except ValueError:
                    print("❌ 请输入有效的数字")
        
        return client
        
    except Exception as e:
        print(f"❌ 获取提供商信息失败: {e}")
        return None

def test_api_connection():
    """测试 API 连接"""
    try:
        client = create_client_from_config()
        
        # 使用一个简单的测试图片
        test_image = "./data/emoji_source/apple.png"
        if os.path.exists(test_image):
            print("正在测试 API 连接...")
            result = client.send_image_with_prompt(test_image, "这是什么？")
            
            if result["success"]:
                print("✓ API 连接测试成功！")
                return True
            else:
                print(f"✗ API 连接测试失败: {result['error']}")
                return False
        else:
            print(f"测试图片不存在: {test_image}")
            return False
            
    except Exception as e:
        print(f"⚠️ 无法创建客户端: {e}")
        print("请检查配置文件并确保至少配置了一个模型提供商")
        return False

if __name__ == "__main__":
    print("=== 多模型图片 LLM API 使用示例 ===\n")
    
    # 显示和选择提供商
    client = show_provider_menu()
    if not client:
        print("\n❌ 无法创建客户端，请检查配置")
        exit(1)
    
    # 测试连接
    if not test_api_connection():
        print("\n请先解决 API 配置问题后再继续")
        exit(1)
    
    print("\n" + "="*50)
    print("请选择要运行的示例:")
    print("1. 单图片处理")
    print("2. 批量处理")
    print("3. 运行所有示例")
    
    choice = input("\n请输入选择 (1-3): ").strip()
    
    if choice == "1":
        example_single_image()
    elif choice == "2":
        example_batch_processing()
    elif choice == "3":
        print("\n=== 示例 1: 单图片处理 ===")
        example_single_image()
        
        input("\n按回车键继续...")
        print("\n=== 示例 2: 批量处理 ===")
        example_batch_processing()
    else:
        print("无效的选择")
        
    print("\n程序执行完成！")
