"""
简单的使用示例
演示如何使用 ImageLLMAPI 类
"""

import os
from image_llm_api import ImageLLMAPI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('config.env')

def example_single_image():
    """单图片处理示例"""
    # 从环境变量获取配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    if not api_key or api_key == "your-openai-api-key-here":
        print("请先在 config.env 文件中设置正确的 API 密钥")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=api_key, base_url=base_url, model=model)
    
    # 指定图片路径和提示词
    image_path = "../data/emoji_source/apple.png"  # 使用项目中的 emoji 图片
    prompt = "请描述这张图片显示的是什么物品或符号？"
    
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
    # 从环境变量获取配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    if not api_key or api_key == "your-openai-api-key-here":
        print("请先在 config.env 文件中设置正确的 API 密钥")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=api_key, base_url=base_url, model=model)
    
    # 批量处理文件夹中的图片
    image_folder = "../data/emoji_source"
    prompt = "这是什么 emoji 表情或符号？请用中文简洁回答。"
    output_file = "emoji_analysis_results.json"
    
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
    # 从环境变量获取配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    if not api_key or api_key == "your-openai-api-key-here":
        print("请先在 config.env 文件中设置正确的 API 密钥")
        return
    
    # 创建客户端
    client = ImageLLMAPI(api_key=api_key, base_url=base_url, model=model)
    
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

if __name__ == "__main__":
    print("=== 图片 LLM API 使用示例 ===\n")
    
    # 选择要运行的示例
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
        
        print("\n=== 示例 2: 批量处理 ===")
        example_batch_processing()
        
        print("\n=== 示例 3: 成语图片分析 ===")
        example_custom_prompt()
    else:
        print("无效的选择")
