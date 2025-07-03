"""
图片 LLM API 调用模块
支持读取图片并通过 API 发送给 LLM 模型进行分析
"""

import base64
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import os
from PIL import Image
import io


class ImageLLMAPI:
    """图片 LLM API 调用类，支持多种模型提供商"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", 
                 model: str = "gpt-4o", api_type: str = "openai", **kwargs):
        """
        初始化 API 客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 使用的模型名称
            api_type: API 类型 (openai, azure, anthropic, openai_compatible)
            **kwargs: 其他配置参数 (如 Azure 的 api_version)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_type = api_type.lower()
        self.extra_config = kwargs
        
        # 根据 API 类型设置不同的 headers
        self.headers = self._get_headers()
    
    def _get_headers(self) -> Dict[str, str]:
        """根据 API 类型获取请求头"""
        if self.api_type == "openai" or self.api_type == "openai_compatible":
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        elif self.api_type == "azure":
            return {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
        elif self.api_type == "anthropic":
            return {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
        else:
            # 默认使用 OpenAI 格式
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
    
    def _get_api_url(self) -> str:
        """根据 API 类型获取请求 URL"""
        if self.api_type == "azure":
            api_version = self.extra_config.get("api_version", "2024-02-15-preview")
            return f"{self.base_url}/openai/deployments/{self.model}/chat/completions?api-version={api_version}"
        elif self.api_type == "anthropic":
            return f"{self.base_url}/v1/messages"
        else:
            # OpenAI 和兼容格式
            return f"{self.base_url}/chat/completions"
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """
        将图片编码为 base64 格式
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            base64 编码的图片字符串
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            raise Exception(f"读取图片失败: {e}")
    
    def resize_image_if_needed(self, image_path: str, max_size: int = 1024) -> str:
        """
        如果图片过大则调整大小
        
        Args:
            image_path: 图片文件路径
            max_size: 最大尺寸
            
        Returns:
            处理后的图片路径
        """
        try:
            with Image.open(image_path) as img:
                # 检查图片尺寸
                if max(img.size) > max_size:
                    # 计算新尺寸
                    ratio = max_size / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    
                    # 调整图片大小
                    img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # 保存临时文件
                    temp_path = image_path.replace('.', '_resized.')
                    img_resized.save(temp_path, optimize=True, quality=85)
                    return temp_path
                else:
                    return image_path
        except Exception as e:
            print(f"调整图片大小时出错: {e}")
            return image_path
    
    def send_image_with_prompt(self, image_path: str, prompt: str, 
                              max_tokens: int = 1000, temperature: float = 0.7) -> Dict[str, Any]:
        """
        发送图片和提示词到 LLM API
        
        Args:
            image_path: 图片文件路径
            prompt: 提示词
            max_tokens: 最大生成 token 数
            temperature: 生成温度
            
        Returns:
            API 响应结果
        """
        # 检查图片文件是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 获取图片类型
        image_ext = Path(image_path).suffix.lower()
        if image_ext == '.jpg':
            image_ext = '.jpeg'
        
        media_type = f"image/{image_ext[1:]}"  # 移除点号
        
        # 调整图片大小（如果需要）
        processed_image_path = self.resize_image_if_needed(image_path)
        
        try:
            # 编码图片
            base64_image = self.encode_image_to_base64(processed_image_path)
            
            # 根据 API 类型构建不同的请求数据
            if self.api_type == "anthropic":
                payload = self._build_anthropic_payload(prompt, base64_image, media_type, max_tokens, temperature)
            else:
                # OpenAI 格式 (包括 Azure 和兼容服务)
                payload = self._build_openai_payload(prompt, base64_image, media_type, max_tokens, temperature)
            
            # 获取 API URL
            api_url = self._get_api_url()
            
            # 发送请求
            response = requests.post(
                api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            # 解析响应
            return self._parse_response(response)
                
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"网络请求错误: {e}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"处理错误: {e}"
            }
        finally:
            # 清理临时文件
            if processed_image_path != image_path and os.path.exists(processed_image_path):
                try:
                    os.remove(processed_image_path)
                except:
                    pass
    
    def _build_openai_payload(self, prompt: str, base64_image: str, media_type: str, 
                             max_tokens: int, temperature: float) -> Dict[str, Any]:
        """构建 OpenAI 格式的请求数据"""
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
    
    def _build_anthropic_payload(self, prompt: str, base64_image: str, media_type: str,
                                max_tokens: int, temperature: float) -> Dict[str, Any]:
        """构建 Anthropic 格式的请求数据"""
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_image
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
    
    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """解析 API 响应"""
        if response.status_code == 200:
            result = response.json()
            
            if self.api_type == "anthropic":
                # Anthropic 响应格式
                return {
                    "success": True,
                    "response": result["content"][0]["text"],
                    "usage": result.get("usage", {}),
                    "model": result.get("model", self.model)
                }
            else:
                # OpenAI 格式响应
                return {
                    "success": True,
                    "response": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {}),
                    "model": result.get("model", self.model)
                }
        else:
            try:
                error_detail = response.json()
            except:
                error_detail = response.text
            
            return {
                "success": False,
                "error": f"API 请求失败: {response.status_code}",
                "details": error_detail
            }
    
    def batch_process_images(self, image_folder: str, prompt: str, 
                           output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        批量处理文件夹中的图片
        
        Args:
            image_folder: 图片文件夹路径
            prompt: 提示词
            output_file: 输出结果文件路径（可选）
            
        Returns:
            批量处理结果
        """
        results = {}
        supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        image_folder_path = Path(image_folder)
        if not image_folder_path.exists():
            return {"success": False, "error": f"文件夹不存在: {image_folder}"}
        
        # 获取所有图片文件
        image_files = [
            f for f in image_folder_path.iterdir() 
            if f.is_file() and f.suffix.lower() in supported_formats
        ]
        
        if not image_files:
            return {"success": False, "error": "文件夹中没有找到支持的图片文件"}
        
        print(f"找到 {len(image_files)} 个图片文件，开始处理...")
        
        for i, image_file in enumerate(image_files, 1):
            print(f"\n处理第 {i}/{len(image_files)} 个图片: {image_file.name}")
            
            result = self.send_image_with_prompt(str(image_file), prompt)
            results[image_file.name] = result
            
            if result["success"]:
                print(f"✓ 成功处理")
                print(f"回答: {result['response'][:100]}...")
            else:
                print(f"✗ 处理失败: {result['error']}")
        
        # 保存结果到文件
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"\n结果已保存到: {output_file}")
            except Exception as e:
                print(f"保存结果文件失败: {e}")
        
        return {
            "success": True,
            "total_images": len(image_files),
            "results": results
        }


def main():
    """主函数示例"""
    # 配置参数
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    if API_KEY == "your-api-key-here":
        print("请设置环境变量 OPENAI_API_KEY 或修改代码中的 API_KEY")
        return
    
    # 创建 API 客户端
    client = ImageLLMAPI(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    
    # 示例 1: 处理单个图片
    image_path = "test_image.jpg"  # 替换为您的图片路径
    prompt = "请描述这张图片的内容"
    
    if os.path.exists(image_path):
        print("=== 单图片处理示例 ===")
        result = client.send_image_with_prompt(image_path, prompt)
        
        if result["success"]:
            print(f"LLM 回答: {result['response']}")
            print(f"使用模型: {result['model']}")
            print(f"Token 使用情况: {result['usage']}")
        else:
            print(f"错误: {result['error']}")
    
    # 示例 2: 批量处理图片
    image_folder = "../data/emoji_source"  # 使用项目中的 emoji 图片
    if os.path.exists(image_folder):
        print(f"\n=== 批量处理示例 ===")
        batch_prompt = "这是什么 emoji 表情？请简洁回答。"
        
        batch_result = client.batch_process_images(
            image_folder=image_folder,
            prompt=batch_prompt,
            output_file="batch_results.json"
        )
        
        if batch_result["success"]:
            print(f"\n批量处理完成，共处理 {batch_result['total_images']} 张图片")
        else:
            print(f"批量处理失败: {batch_result['error']}")


if __name__ == "__main__":
    main()
