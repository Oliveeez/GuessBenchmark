"""
简单的使用示例（不依赖外部库）
演示如何使用 ImageLLMAPI 类
"""

import os
from image_llm_api import ImageLLMAPI

def example_single_image():
    """单图片处理示例"""
    # 直接设置 API 配置（请替换为您的实际配置）
    API_KEY = "your-api-key-here"  # 请替换为您的实际 API 密钥
    BASE_URL = "https://api.openai.com/v1"
    MODEL = "gpt-4o"
    
    # 也可以从环境变量获取
    API_KEY = os.getenv("OPENAI_API_KEY", API_KEY)
    BASE_URL = os.getenv("OPENAI_BASE_URL", BASE_URL)
    MODEL = os.getenv("OPENAI_MODEL", MODEL)
    
    if API_KEY == "your-api-key-here":
        print("请设置环境变量 OPENAI_API_KEY 或修改代码中的 API_KEY")
        print("Windows 设置环境变量示例:")
        print('set OPENAI_API_KEY=sk-your-actual-key')
        print("然后重新运行脚本")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    
    # 指定图片路径和提示词
    image_path = "../data/emoji_source/apple.png"  # 使用项目中的 emoji 图片
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

def example_batch_processing():
    """批量处理示例"""
    # 直接设置 API 配置（请替换为您的实际配置）
    API_KEY = "your-api-key-here"  # 请替换为您的实际 API 密钥
    BASE_URL = "https://api.openai.com/v1"
    MODEL = "gpt-4o"
    
    # 也可以从环境变量获取
    API_KEY = os.getenv("OPENAI_API_KEY", API_KEY)
    BASE_URL = os.getenv("OPENAI_BASE_URL", BASE_URL)
    MODEL = os.getenv("OPENAI_MODEL", MODEL)
    
    if API_KEY == "your-api-key-here":
        print("请设置环境变量 OPENAI_API_KEY 或修改代码中的 API_KEY")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    
    # 批量处理文件夹中的图片
    image_folder = "../data/emoji_source"
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

def example_custom_prompt():
    """自定义提示词示例"""
    # 直接设置 API 配置（请替换为您的实际配置）
    API_KEY = "your-api-key-here"  # 请替换为您的实际 API 密钥
    BASE_URL = "https://api.openai.com/v1"
    MODEL = "gpt-4o"
    
    # 也可以从环境变量获取
    API_KEY = os.getenv("OPENAI_API_KEY", API_KEY)
    BASE_URL = os.getenv("OPENAI_BASE_URL", BASE_URL)
    MODEL = os.getenv("OPENAI_MODEL", MODEL)
    
    if API_KEY == "your-api-key-here":
        print("请设置环境变量 OPENAI_API_KEY 或修改代码中的 API_KEY")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    
    # 处理成语图片（如果存在）
    idiom_image_folder = "../data/chinese_idiom_image/img"
    if os.path.exists(idiom_image_folder):
        # 获取第一张图片作为示例
        image_files = [f for f in os.listdir(idiom_image_folder) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if image_files:
            image_path = os.path.join(idiom_image_folder, image_files[0])
            
            # 针对成语图片的特定提示词
            prompt = """请分析这张图片，尝试猜测它可能代表哪个中文成语。
请考虑：
1. 图片中的物体、人物、动作
2. 它们之间的关系和含义
3. 可能的象征意义

请直接说出你认为最可能的成语，并简要解释原因。"""
            
            print(f"正在分析成语图片: {image_files[0]}")
            result = client.send_image_with_prompt(image_path, prompt)
            
            if result["success"]:
                print("\n=== 成语猜测结果 ===")
                print(result['response'])
            else:
                print(f"\n错误: {result['error']}")
        else:
            print("未找到成语图片文件")
    else:
        print("成语图片文件夹不存在")

def test_api_connection():
    """测试 API 连接"""
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    
    if API_KEY == "your-api-key-here":
        print("⚠️  请先设置 API 密钥")
        print("方法 1: 设置环境变量")
        print("  Windows: set OPENAI_API_KEY=sk-your-key")
        print("  Linux/Mac: export OPENAI_API_KEY=sk-your-key")
        print("\n方法 2: 修改代码中的 API_KEY 变量")
        return False
    
    # 创建客户端
    client = ImageLLMAPI(api_key=API_KEY)
    
    # 使用一个简单的测试图片
    test_image = "../data/emoji_source/apple.png"
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

if __name__ == "__main__":
    print("=== 图片 LLM API 使用示例 ===\n")
    
    # 首先测试 API 连接
    if not test_api_connection():
        print("\n请先解决 API 配置问题后再继续")
        exit(1)
    
    print("\n" + "="*50)
    print("请选择要运行的示例:")
    print("1. 单图片处理")
    print("2. 批量处理")
    print("3. 成语图片分析")
    print("4. 运行所有示例")
    
    choice = input("\n请输入选择 (1-4): ").strip()
    
    if choice == "1":
        example_single_image()
    elif choice == "2":
        example_batch_processing()
    elif choice == "3":
        example_custom_prompt()
    elif choice == "4":
        print("\n=== 示例 1: 单图片处理 ===")
        example_single_image()
        
        input("\n按回车键继续...")
        print("\n=== 示例 2: 批量处理 ===")
        example_batch_processing()
        
        input("\n按回车键继续...")
        print("\n=== 示例 3: 成语图片分析 ===")
        example_custom_prompt()
    else:
        print("无效的选择")
        
    print("\n程序执行完成！")
