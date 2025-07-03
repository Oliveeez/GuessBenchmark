"""
GuessBenchmark 项目专用图片分析脚本
针对成语图片、emoji 图片等进行 LLM 分析
"""

import os
import json
from image_llm_api import ImageLLMAPI
from pathlib import Path

class GuessBenchmarkAnalyzer:
    """GuessBenchmark 项目专用分析器"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        self.client = ImageLLMAPI(api_key=api_key, base_url=base_url, model=model)
        self.project_root = Path(__file__).parent.parent  # 项目根目录
    
    def analyze_chinese_idiom_images(self, output_file: str = "chinese_idiom_analysis.json"):
        """分析中文成语图片"""
        idiom_folder = self.project_root / "data" / "chinese_idiom_image" / "img"
        
        if not idiom_folder.exists():
            print(f"成语图片文件夹不存在: {idiom_folder}")
            return None
        
        prompt = """请仔细观察这张图片，分析图片中的元素和场景，然后猜测它代表的中文成语。

请按以下格式回答：
成语: [你的答案]
解释: [简要说明为什么是这个成语，图片中哪些元素支持你的判断]
置信度: [1-5分，5分表示非常确定]

注意：
- 考虑图片中所有可见的物体、人物、动作、表情等
- 思考这些元素的象征意义和相互关系
- 成语通常有特定的文化背景和比喻含义"""
        
        print("开始分析中文成语图片...")
        result = self.client.batch_process_images(
            image_folder=str(idiom_folder),
            prompt=prompt,
            output_file=output_file
        )
        
        if result["success"]:
            print(f"✓ 成语图片分析完成，结果保存到: {output_file}")
            return result
        else:
            print(f"✗ 成语图片分析失败: {result['error']}")
            return None
    
    def analyze_emoji_images(self, output_file: str = "emoji_analysis.json"):
        """分析 emoji 图片"""
        emoji_folder = self.project_root / "data" / "emoji_source"
        
        if not emoji_folder.exists():
            print(f"Emoji 图片文件夹不存在: {emoji_folder}")
            return None
        
        prompt = """请识别这个 emoji 表情或符号，并提供以下信息：

名称: [emoji 的标准名称]
含义: [这个 emoji 表达的意思或情感]
使用场景: [通常在什么情况下使用]

请用中文回答，保持简洁准确。"""
        
        print("开始分析 emoji 图片...")
        result = self.client.batch_process_images(
            image_folder=str(emoji_folder),
            prompt=prompt,
            output_file=output_file
        )
        
        if result["success"]:
            print(f"✓ Emoji 图片分析完成，结果保存到: {output_file}")
            return result
        else:
            print(f"✗ Emoji 图片分析失败: {result['error']}")
            return None
    
    def analyze_single_idiom_image(self, image_name: str):
        """分析单个成语图片"""
        idiom_folder = self.project_root / "data" / "chinese_idiom_image" / "img"
        image_path = idiom_folder / image_name
        
        if not image_path.exists():
            print(f"图片文件不存在: {image_path}")
            return None
        
        prompt = """请详细分析这张成语图片：

1. 图片描述: 详细描述图片中的所有元素
2. 可能的成语: 列出 2-3 个可能的成语
3. 最佳答案: 选择最可能的成语并详细解释原因
4. 文化背景: 简述这个成语的典故或文化含义

请用中文回答，分析要深入细致。"""
        
        print(f"正在分析成语图片: {image_name}")
        result = self.client.send_image_with_prompt(str(image_path), prompt)
        
        if result["success"]:
            print("\n=== 详细分析结果 ===")
            print(result['response'])
            return result
        else:
            print(f"✗ 分析失败: {result['error']}")
            return None
    
    def compare_with_ground_truth(self, analysis_file: str, gt_file: str):
        """将分析结果与标准答案进行比较"""
        try:
            # 读取分析结果
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_results = json.load(f)
            
            # 读取标准答案
            gt_path = self.project_root / "data" / "chinese_idiom_image" / gt_file
            if gt_path.exists():
                with open(gt_path, 'r', encoding='utf-8') as f:
                    ground_truth = json.load(f)
                
                print("\n=== 准确性评估 ===")
                total = 0
                correct = 0
                
                for image_name, analysis in analysis_results.items():
                    if analysis.get("success"):
                        total += 1
                        response = analysis["response"]
                        
                        # 简单的准确性检查（需要根据实际格式调整）
                        print(f"\n图片: {image_name}")
                        print(f"LLM分析: {response[:100]}...")
                        
                        # 这里可以添加更复杂的比较逻辑
                        # 比如提取成语名称并与标准答案比较
                
                print(f"\n总计分析图片: {total}")
                print(f"分析成功率: {(total / len(analysis_results)) * 100:.1f}%")
                
            else:
                print(f"标准答案文件不存在: {gt_path}")
                
        except Exception as e:
            print(f"比较分析时出错: {e}")
    
    def generate_benchmark_report(self):
        """生成基准测试报告"""
        print("=== GuessBenchmark 项目分析报告 ===\n")
        
        # 分析成语图片
        idiom_result = self.analyze_chinese_idiom_images()
        
        # 分析 emoji 图片
        emoji_result = self.analyze_emoji_images()
        
        # 生成汇总报告
        report = {
            "timestamp": str(Path(__file__).stat().st_mtime),
            "results": {
                "chinese_idioms": idiom_result,
                "emojis": emoji_result
            }
        }
        
        with open("benchmark_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("\n=== 分析完成 ===")
        print("完整报告已保存到: benchmark_report.json")

def main():
    """主函数"""
    # API 配置
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    if API_KEY == "your-api-key-here":
        print("请设置环境变量 OPENAI_API_KEY 或修改代码中的 API_KEY")
        print("Windows 示例: set OPENAI_API_KEY=sk-your-actual-key")
        return
    
    # 创建分析器
    analyzer = GuessBenchmarkAnalyzer(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    
    print("=== GuessBenchmark 项目图片分析工具 ===\n")
    print("请选择操作:")
    print("1. 分析所有成语图片")
    print("2. 分析所有 emoji 图片")
    print("3. 分析单个成语图片")
    print("4. 生成完整基准测试报告")
    print("5. 与标准答案比较")
    
    choice = input("\n请输入选择 (1-5): ").strip()
    
    if choice == "1":
        analyzer.analyze_chinese_idiom_images()
    elif choice == "2":
        analyzer.analyze_emoji_images()
    elif choice == "3":
        image_name = input("请输入图片文件名 (如: 一败涂地.jpg): ").strip()
        analyzer.analyze_single_idiom_image(image_name)
    elif choice == "4":
        analyzer.generate_benchmark_report()
    elif choice == "5":
        analysis_file = input("请输入分析结果文件名 (默认: chinese_idiom_analysis.json): ").strip()
        if not analysis_file:
            analysis_file = "chinese_idiom_analysis.json"
        gt_file = input("请输入标准答案文件名 (默认: c_idiom_image_gt.json): ").strip()
        if not gt_file:
            gt_file = "c_idiom_image_gt.json"
        analyzer.compare_with_ground_truth(analysis_file, gt_file)
    else:
        print("无效的选择")

if __name__ == "__main__":
    main()
