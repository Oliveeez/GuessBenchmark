"""
GuessBenchmark 项目专用图片分析脚本
针对成语图片、emoji 图片等进行 LLM 分析
"""

import os
import json
import re
import argparse
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from image_llm_api import ImageLLMAPI


class GuessBenchmarkAnalyzer:
    """GuessBenchmark 项目专用分析器"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        """
        初始化分析器
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 使用的模型名称
        """
        self.client = ImageLLMAPI(api_key=api_key, base_url=base_url, model=model)
        self.project_root = Path(__file__).parent.parent  # 项目根目录

    def prompt_generator(self, image_name: str) -> str:
        """
        根据图片版本生成相应的prompt
        
        Args:
            image_name: 图片文件名
            
        Returns:
            str: 相应版本的prompt
        """
        # 从文件名中提取版本号
        version_match = re.search(r'v(\d+)', image_name)
        if not version_match:
            # 如果没有找到版本号，使用默认v000的prompt
            version_num = 0
        else:
            version_num = int(version_match.group(1))
        
        # 基础prompt部分
        base_prompt = (
            "You are a linguistic expert tasked with identifying Chinese four-character idioms (成语) based on a set of four emojis. "
            "Each emoji corresponds to one character in the idiom, {order_instruction}. The mapping can be either:\n"
            "1) Semantic Match: The emoji's meaning aligns with the character's meaning.\n"
            "2) Phonetic Match: The emoji's Chinese pronunciation (pinyin) matches or closely resembles the character's pronunciation.\n"
            "Additionally, your output must include both the final idiom result and the reasoning process. "
            "The output must be a single JSON object containing only the JSON and no additional text. "
            "The JSON format should be: {{\"idiom\": \"xxxx\", \"inference_chain\": \"...\"}}."
        )
        
        # 根据版本号确定顺序指令
        if version_num == 0:
            order_instruction = "in sequential order"
        elif 2 <= version_num <= 7:
            order_instruction = ("You need to determine the appropriate method and order to read the emojis "
                               "(which may be arranged in circular, diagonal, rectangular borders, or other patterns)")
        elif 8 <= version_num <= 25:
            order_instruction = "You can read the emojis according to the numerical sequence or connecting arrows indicated in the image"
        else:
            # 对于其他版本号，使用默认的sequential order
            order_instruction = "in sequential order"
        
        return base_prompt.format(order_instruction=order_instruction)

    def analyze_single_image(self, image_path: str, output_dir: str) -> bool:
        """
        分析单张图片
        
        Args:
            image_path: 图片文件路径
            output_dir: 输出目录
            
        Returns:
            bool: 是否成功
        """
        image_path = Path(image_path)
        output_dir = Path(output_dir)
        
        if not image_path.exists():
            print(f"❌ 图片文件不存在: {image_path}")
            return False
            
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 正在分析图片: {image_path.name}")
        
        # 根据图片名称生成相应的prompt
        prompt = self.prompt_generator(image_path.name)
        print(f"📝 使用prompt版本: {self._get_version_info(image_path.name)}")
        
        # 发送分析请求
        result = self.client.send_image_with_prompt(str(image_path), prompt)
        
        # 准备输出数据
        output_data = {
            "image_path": str(image_path),
            "image_name": image_path.name,
            "prompt_version": self._get_version_info(image_path.name),
            "analysis_result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存结果
        output_file = output_dir / "test.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            if result.get("success"):
                print(f"✅ 分析完成，结果保存到: {output_file}")
                print(f"📊 分析结果预览:\n{result['response'][:200]}...")
                return True
            else:
                print(f"❌ 分析失败: {result.get('error', '未知错误')}")
                return False
                
        except Exception as e:
            print(f"❌ 保存结果时出错: {e}")
            return False

    def analyze_batch_images(self, input_dir: str, output_dir: str) -> bool:
        """
        批量分析图片
        
        Args:
            input_dir: 输入目录 (level1)
            output_dir: 输出目录
            
        Returns:
            bool: 是否成功
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        
        if not input_dir.exists():
            print(f"❌ 输入目录不存在: {input_dir}")
            return False
            
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🚀 开始批量分析，输入目录: {input_dir}")
        
        # 遍历所有成语文件夹 (level2)
        idiom_folders = [d for d in input_dir.iterdir() if d.is_dir()]
        
        if not idiom_folders:
            print(f"❌ 在 {input_dir} 中未找到成语文件夹")
            return False
            
        total_processed = 0
        total_success = 0
        
        for idiom_folder in sorted(idiom_folders):
            idiom_name = idiom_folder.name  # {index}_{idiom}
            print(f"\n📁 处理成语文件夹: {idiom_name}")
            
            # 分析该成语的所有图片
            idiom_results = self._analyze_idiom_folder(idiom_folder)
            
            if idiom_results:
                # 保存结果
                output_file = output_dir / f"{idiom_name}.json"
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(idiom_results, f, ensure_ascii=False, indent=2)
                    
                    print(f"✅ {idiom_name} 分析完成，结果保存到: {output_file}")
                    total_success += 1
                    
                except Exception as e:
                    print(f"❌ 保存 {idiom_name} 结果时出错: {e}")
            
            total_processed += 1
        
        print(f"\n🎉 批量分析完成!")
        print(f"📊 总计处理: {total_processed} 个成语文件夹")
        print(f"📊 成功处理: {total_success} 个成语文件夹")
        print(f"📊 成功率: {(total_success/total_processed)*100:.1f}%")
        
        return total_success > 0

    def _get_version_info(self, image_name: str) -> str:
        """
        从图片名称中获取版本信息
        
        Args:
            image_name: 图片文件名
            
        Returns:
            str: 版本信息描述
        """
        version_match = re.search(r'v(\d+)', image_name)
        if not version_match:
            return "v000 (default sequential order)"
        
        version_num = int(version_match.group(1))
        
        if version_num == 0:
            return "v000 (sequential order)"
        elif 2 <= version_num <= 7:
            return f"v{version_num:03d} (self-determined reading order)"
        elif 8 <= version_num <= 25:
            return f"v{version_num:03d} (numerical sequence/arrow guidance)"
        else:
            return f"v{version_num:03d} (default sequential order)"

    def _analyze_idiom_folder(self, idiom_folder: Path) -> Optional[Dict[str, Any]]:
        """
        分析单个成语文件夹下的所有图片
        
        Args:
            idiom_folder: 成语文件夹路径 (level2)
            
        Returns:
            Dict: 分析结果字典
        """
        idiom_results = {
            "idiom_folder": str(idiom_folder),
            "idiom_name": idiom_folder.name,
            "images": {},
            "summary": {
                "total_images": 0,
                "successful_analyses": 0,
                "failed_analyses": 0
            }
        }
        
        # 遍历数字文件夹 (level3)
        number_folders = [d for d in idiom_folder.iterdir() if d.is_dir() and d.name.isdigit()]
        
        for number_folder in sorted(number_folders):
            print(f"  📂 处理子文件夹: {number_folder.name}")
            
            # 处理该数字文件夹下的所有图片
            folder_results = self._analyze_number_folder(number_folder)
            
            if folder_results:
                idiom_results["images"][number_folder.name] = folder_results
                
                # 更新统计信息
                for image_data in folder_results.values():
                    idiom_results["summary"]["total_images"] += 1
                    if image_data.get("analysis_result", {}).get("success"):
                        idiom_results["summary"]["successful_analyses"] += 1
                    else:
                        idiom_results["summary"]["failed_analyses"] += 1
        
        return idiom_results if idiom_results["summary"]["total_images"] > 0 else None

    def _analyze_number_folder(self, number_folder: Path) -> Dict[str, Any]:
        """
        分析数字文件夹下的所有图片
        
        Args:
            number_folder: 数字文件夹路径 (level3)
            
        Returns:
            Dict: 该文件夹下所有图片的分析结果
        """
        folder_results = {}
        
        # 1. 处理基准图片 (base图)
        base_images = list(number_folder.glob("*_base_v*.png"))
        for base_image in base_images:
            print(f"    🖼️  分析基准图: {base_image.name}")
            prompt = self.prompt_generator(base_image.name)
            version_info = self._get_version_info(base_image.name)
            print(f"    📝 使用prompt版本: {version_info}")
            
            result = self.client.send_image_with_prompt(str(base_image), prompt)
            folder_results[base_image.name] = {
                "image_path": str(base_image),
                "image_type": "base",
                "prompt_version": version_info,
                "analysis_result": result
            }
        
        # 2. 处理纯变体图片
        pure_variants_dir = number_folder / "seq_varients_pure"
        if pure_variants_dir.exists():
            pure_images = list(pure_variants_dir.glob("*.png"))
            for pure_image in pure_images:
                print(f"    🖼️  分析纯变体图: {pure_image.name}")
                prompt = self.prompt_generator(pure_image.name)
                version_info = self._get_version_info(pure_image.name)
                print(f"    📝 使用prompt版本: {version_info}")
                
                result = self.client.send_image_with_prompt(str(pure_image), prompt)
                folder_results[pure_image.name] = {
                    "image_path": str(pure_image),
                    "image_type": "pure_variant",
                    "prompt_version": version_info,
                    "analysis_result": result
                }
        
        # 3. 处理带指示的变体图片
        guided_variants_dir = number_folder / "seq_varients_with_guideance"
        if guided_variants_dir.exists():
            guided_images = list(guided_variants_dir.glob("*.png"))
            for guided_image in guided_images:
                print(f"    🖼️  分析指示变体图: {guided_image.name}")
                prompt = self.prompt_generator(guided_image.name)
                version_info = self._get_version_info(guided_image.name)
                print(f"    📝 使用prompt版本: {version_info}")
                
                result = self.client.send_image_with_prompt(str(guided_image), prompt)
                folder_results[guided_image.name] = {
                    "image_path": str(guided_image),
                    "image_type": "guided_variant",
                    "prompt_version": version_info,
                    "analysis_result": result
                }
        
        return folder_results

    def generate_summary_report(self, output_dir: str) -> None:
        """
        生成汇总报告
        
        Args:
            output_dir: 输出目录
        """
        output_dir = Path(output_dir)
        
        if not output_dir.exists():
            print(f"❌ 输出目录不存在: {output_dir}")
            return
        
        print("📋 正在生成汇总报告...")
        
        # 收集所有结果文件
        result_files = list(output_dir.glob("*.json"))
        
        if not result_files:
            print(f"❌ 在 {output_dir} 中未找到结果文件")
            return
        
        summary = {
            "total_idioms": len(result_files),
            "total_images": 0,
            "total_successful": 0,
            "total_failed": 0,
            "prompt_version_stats": {},
            "idiom_details": {}
        }
        
        for result_file in result_files:
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                idiom_name = result_file.stem
                
                if "summary" in data:
                    # 批量分析结果
                    summary["total_images"] += data["summary"]["total_images"]
                    summary["total_successful"] += data["summary"]["successful_analyses"]
                    summary["total_failed"] += data["summary"]["failed_analyses"]
                    summary["idiom_details"][idiom_name] = data["summary"]
                    
                    # 统计prompt版本使用情况
                    if "images" in data:
                        for folder_data in data["images"].values():
                            for image_data in folder_data.values():
                                prompt_version = image_data.get("prompt_version", "unknown")
                                if prompt_version not in summary["prompt_version_stats"]:
                                    summary["prompt_version_stats"][prompt_version] = 0
                                summary["prompt_version_stats"][prompt_version] += 1
                else:
                    # 单图分析结果
                    summary["total_images"] += 1
                    if data.get("analysis_result", {}).get("success"):
                        summary["total_successful"] += 1
                    else:
                        summary["total_failed"] += 1
                    
                    summary["idiom_details"][idiom_name] = {
                        "total_images": 1,
                        "successful_analyses": 1 if data.get("analysis_result", {}).get("success") else 0,
                        "failed_analyses": 0 if data.get("analysis_result", {}).get("success") else 1
                    }
                    
                    # 统计prompt版本使用情况
                    prompt_version = data.get("prompt_version", "unknown")
                    if prompt_version not in summary["prompt_version_stats"]:
                        summary["prompt_version_stats"][prompt_version] = 0
                    summary["prompt_version_stats"][prompt_version] += 1
                    
            except Exception as e:
                print(f"⚠️  读取结果文件 {result_file} 时出错: {e}")
        
        # 计算成功率
        if summary["total_images"] > 0:
            summary["success_rate"] = (summary["total_successful"] / summary["total_images"]) * 100
        else:
            summary["success_rate"] = 0
        
        # 保存汇总报告
        summary_file = output_dir / "summary_report.json"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 汇总报告已保存到: {summary_file}")
            print(f"📊 总计分析 {summary['total_images']} 张图片")
            print(f"📊 成功分析 {summary['total_successful']} 张")
            print(f"📊 失败分析 {summary['total_failed']} 张")
            print(f"📊 整体成功率: {summary['success_rate']:.2f}%")
            print(f"📊 Prompt版本分布:")
            for version, count in summary["prompt_version_stats"].items():
                print(f"    {version}: {count} 张图片")
            
        except Exception as e:
            print(f"❌ 保存汇总报告时出错: {e}")


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GuessBenchmark 项目图片分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析单张图片
  python script.py --operate single --input /path/to/image.png --output /path/to/output/

  # 批量分析
  python script.py --operate batch --input /path/to/input_folder/ --output /path/to/output/
        """
    )
    
    parser.add_argument(
        "--operate",
        choices=["single", "batch"],
        default="single",
        help="操作模式: single (分析单张图片) 或 batch (批量分析)"
    )
    
    parser.add_argument(
        "--input",
        required=True,
        help="输入路径: single模式为图片文件路径，batch模式为包含成语文件夹的目录"
    )
    
    parser.add_argument(
        "--output", 
        required=True,
        help="输出目录路径"
    )
    
    parser.add_argument(
        "--generate-summary",
        action="store_true",
        help="是否在批量分析后生成汇总报告"
    )
    
    return parser.parse_args()


def load_config() -> Dict[str, str]:
    """加载配置"""
    load_dotenv()
    
    config = {
        "api_key": os.getenv("GENERAL_API_KEY", ""),
        "base_url": os.getenv("GENERAL_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("GENERAL_MODEL", "gpt-4o")
    }
    
    if not config["api_key"]:
        raise ValueError("未设置 GENERAL_API_KEY 环境变量")
    
    return config


def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 加载配置
        config = load_config()
        
        print("🚀 GuessBenchmark 图片分析工具启动")
        print(f"📋 操作模式: {args.operate}")
        print(f"📂 输入路径: {args.input}")
        print(f"📁 输出目录: {args.output}")
        print(f"🤖 使用模型: {config['model']}")
        print(f"🌐 API地址: {config['base_url']}")
        print("-" * 50)
        
        # 创建分析器
        analyzer = GuessBenchmarkAnalyzer(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=config["model"]
        )
        
        # 执行相应操作
        if args.operate == "single":
            success = analyzer.analyze_single_image(args.input, args.output)
        elif args.operate == "batch":
            success = analyzer.analyze_batch_images(args.input, args.output)
            
            # 如果需要生成汇总报告
            if args.generate_summary and success:
                analyzer.generate_summary_report(args.output)
        
        if success:
            print("\n✅ 所有操作完成!")
        else:
            print("\n❌ 操作失败!")
            return 1
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())