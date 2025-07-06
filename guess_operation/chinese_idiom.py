import os
import re
import time
import json
from datetime import datetime
from pathlib import Path
import sys

# 添加 llm 模块到路径
sys.path.append(str(Path(__file__).parent.parent / "llm"))

try:
    from unified_client import create_client_from_config
except ImportError:
    print("❌ 无法导入 unified_client，请确保 llm 文件夹中的文件存在")
    sys.exit(1)

def is_valid_chinese_idiom(text):
    """检查是否是有效的四字成语"""
    # 移除所有非中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_text = ''.join(chinese_chars)
    
    # 检查是否恰好是四个中文字符
    return len(chinese_text) == 4

def extract_idiom_from_response(response):
    """从LLM响应中提取成语"""
    if not response:
        return "xxxx"
    
    # 去除换行符和多余空格
    response = response.strip().replace('\n', ' ').replace('\r', ' ')
    
    # 尝试多种提取方式
    extraction_patterns = [
        # 直接四字成语
        r'[\u4e00-\u9fff]{4}',
        # 成语：xxxx 格式
        r'成语[：:]\s*([\u4e00-\u9fff]{4})',
        # 答案：xxxx 格式  
        r'答案[：:]\s*([\u4e00-\u9fff]{4})',
        # 是：xxxx 格式
        r'是[：:]?\s*([\u4e00-\u9fff]{4})',
        # 引号中的四字成语
        r'["""'']\s*([\u4e00-\u9fff]{4})\s*["""'']',
        # 句子开头的四字成语
        r'^([\u4e00-\u9fff]{4})',
    ]
    
    for pattern in extraction_patterns:
        matches = re.findall(pattern, response)
        for match in matches:
            if is_valid_chinese_idiom(match):
                return match
    
    # 如果所有方法都失败，返回错误标记
    return "错错错错"

def example_chinese_idiom():
    """处理中文成语图片识别"""
    try:
        print("🚀 开始中文成语图片识别...")
        
        # 创建客户端
        print("🔧 创建 LLM 客户端...")
        client = create_client_from_config()
        
        print(f"✅ 当前使用模型: {client.get_current_provider()} - {client.get_current_model()}")
        
        # 查找图片目录
        project_root = Path(__file__).parent.parent
        image_dir = project_root / "data" / "test"
        # image_dir = project_root / "data" / "chinese_idiom_image" / "img"
        
        if not image_dir.exists():
            print(f"❌ 图片目录不存在: {image_dir}")
            return
        
        # 获取所有图片文件
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(image_dir.glob(f"*{ext}"))
            # image_files.extend(image_dir.glob(f"*{ext.upper()}"))
        
        if not image_files:
            print(f"❌ 在 {image_dir} 中未找到图片文件")
            return
        
        print(f"📸 找到 {len(image_files)} 张图片")
        
        # 优化的成语识别提示词
        prompt = """请仔细观察这张图片，分析图中的元素，然后猜测它代表的中文成语。

要求：
1. 只返回四个汉字的成语，不要任何解释
2. 如果不确定，也要给出最可能的四字成语
3. 格式：直接返回成语，如"一败涂地"

成语："""
        
        # 存储结果
        results = []
        processed = 0
        
        print("\n🔍 开始处理图片...")
        
        for image_file in sorted(image_files):
            processed += 1
            print(f"\n[{processed}/{len(image_files)}] 处理: {image_file.name}")
            
            try:
                # 发送请求
                result = client.send_image_with_prompt(
                    str(image_file), 
                    prompt,
                    max_tokens=10,  # 限制输出长度
                    temperature=0.1  # 降低随机性
                )
                
                if result["success"]:
                    response = result['response'].strip()
                    print(f"   原始回答: {response}")
                    
                    # 提取成语
                    idiom = extract_idiom_from_response(response)
                    print(f"   提取成语: {idiom}")
                    
                    results.append(idiom)
                else:
                    print(f"   ❌ API请求失败: {result['error']}")
                    results.append("错错错错")
                
                # 添加延迟避免API限制
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ 处理出错: {e}")
                results.append("错错错错")
        
        # 生成输出文件
        output_dir = Path(__file__).parent
        current_time = datetime.now()
        date_str = current_time.strftime("%Y.%m.%d._%H.%M.%S")
        timestamp = current_time.strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"result\\{date_str}_CHN_result.txt"
        
        print(f"\n💾 保存结果到: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 写入标题（使用生成日期作为标题）
            f.write(f"{date_str}\n")
            f.write("="*30 + "\n")
            f.write(f"生成时间: {current_time.strftime('%H:%M:%S')}\n")
            f.write(f"使用模型: {client.get_current_provider()} - {client.get_current_model()}\n")
            f.write(f"处理图片: {len(image_files)} 张\n")
            f.write("="*30 + "\n\n")
            
            # 写入每个成语（每行一个）
            for idiom in results:
                f.write(f"{idiom}\n")
        
        # 统计结果
        valid_count = sum(1 for r in results if r != "错错错错")
        error_count = len(results) - valid_count
        
        print(f"\n📊 处理完成！")
        print(f"   总计: {len(results)} 张图片")
        print(f"   成功: {valid_count} 个成语")
        print(f"   失败: {error_count} 个")
        print(f"   成功率: {valid_count/len(results)*100:.1f}%")
        print(f"   结果文件: {output_file}")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    example_chinese_idiom()