#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @FileName: huaweicloud_api.py
# @Time: 2025/6/29
# @Author: Assistant
"""
华为云API客户端 - 修复版本
- Qwen2.5-72B-Instruct: http://121.37.103.140:31012/v1 (文本生成)
- Qwen2.5-VL-7B-instruct: http://121.37.103.140:31017/v1 (视觉+文本)
- 已修复代理问题
- 移除model字段（每个端口只有一个模型）
"""

import os
import requests
import time
import base64
import logging
from PIL import Image
import io
from typing import Dict, Any, Optional, List

# 强制清除代理环境变量
proxy_vars = [
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy', 'FTP_PROXY', 'ftp_proxy',
    'SOCKS_PROXY', 'socks_proxy', 'NO_PROXY', 'no_proxy'
]
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]


class APIClient:
    """华为云API客户端 - 支持双模型，已修复代理问题"""
    
    def __init__(self, api_key: str = "EMPTY", 
                 text_api_base: str = "http://121.37.103.140:31012/v1",
                 vision_api_base: str = "http://121.37.103.140:31017/v1",
                 bypass_proxy: bool = True):
        """
        初始化 API 客户端
        
        :param api_key: API 密钥，默认为 "EMPTY"
        :param text_api_base: 文本模型API基础URL
        :param vision_api_base: 视觉模型API基础URL
        :param bypass_proxy: 是否绕过代理，默认True
        """
        self.api_key = api_key
        self.text_api_base = text_api_base
        self.vision_api_base = vision_api_base
        self.bypass_proxy = bypass_proxy
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "HuaweiCloud-API-Client/1.0"
        }
        self.logger = logging.getLogger(__name__)
        
        # 强制清除所有代理环境变量
        if bypass_proxy:
            for var in proxy_vars:
                if var in os.environ:
                    self.logger.debug(f"清除代理变量: {var}={os.environ[var]}")
                    del os.environ[var]
        
        # 配置requests会话以强制绕过代理
        self.session = requests.Session()
        if bypass_proxy:
            # 强制禁用所有代理
            self.session.proxies = {
                'http': None,
                'https': None,
                'ftp': None,
                'socks': None
            }
            # 设置trust_env=False强制忽略环境变量
            self.session.trust_env = False
        
        # 配置连接参数
        self.session.headers.update(self.headers)
        
        # 记录配置信息
        self.logger.info(f"🔧 初始化华为云API客户端")
        self.logger.info(f"📝 文本模型: {text_api_base}")
        self.logger.info(f"👁️ 视觉模型: {vision_api_base}")
        if bypass_proxy:
            self.logger.info(f"🌐 已配置强制绕过代理")

    def _send_request(self, api_base: str, endpoint: str, payload: dict) -> dict:
        """
        发送 HTTP POST 请求到指定的API
        
        :param api_base: API基础URL
        :param endpoint: API的终结点
        :param payload: 请求的负载数据
        :return: API 响应的 JSON 数据
        """
        url = f"{api_base}{endpoint}"
        
        try:
            self.logger.debug(f"🔗 发送请求到: {url}")
            
            # 使用配置好的session发送请求
            response = self.session.post(
                url, 
                json=payload, 
                timeout=60,
                verify=False
            )
            
            if response.status_code != 200:
                error_msg = f"API 请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            return response.json()
            
        except requests.exceptions.Timeout:
            error_msg = f"API 请求超时: {url}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"API 连接失败: {url}, 错误: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.ProxyError as e:
            error_msg = f"代理错误: {url}, 错误: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            self.logger.error(f"API 请求异常: {e}")
            raise

    def api_text(self, prompt: str, max_tokens: int = 100, temperature: float = 0.7) -> Dict[str, Any]:
        """
        执行纯文本生成 API 调用 (使用文本模型)
        
        :param prompt: 输入的文本提示
        :param max_tokens: 最大 token 数量
        :param temperature: 生成的文本的温度值
        :return: 生成的文本内容，使用的 tokens 数量以及请求时间
        """
        start_time = time.time()

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            response = self._send_request(self.text_api_base, "/chat/completions", payload)
            
            end_time = time.time()
            response_time = end_time - start_time

            # 获取生成的文本和使用的 tokens 数量
            output = response['choices'][0]['message']['content']
            used_tokens = response.get('usage', {}).get('total_tokens', 0)

            result = {
                "success": True,
                "text": output.strip(),
                "used_tokens": used_tokens,
                "time_taken": response_time,
                "api_base": self.text_api_base
            }
            
            self.logger.debug(f"📝 文本生成成功: {used_tokens} tokens, {response_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 文本生成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "used_tokens": 0,
                "time_taken": 0,
                "api_base": self.text_api_base
            }

    def api_image(self, prompt: str, image_path: str, max_tokens: int = 100, 
                  temperature: float = 0.7) -> Dict[str, Any]:
        """
        执行图像+文本生成 API 调用 (使用视觉模型)
        
        :param prompt: 输入的文本提示
        :param image_path: 图片文件路径
        :param max_tokens: 最大 token 数量
        :param temperature: 生成的文本的温度值
        :return: 生成的文本内容，使用的 tokens 数量，以及请求的时间
        """
        try:
            # 将图像文件转为 base64
            with open(image_path, "rb") as image_file:
                image = Image.open(image_file)
                image = image.resize((512, 512))  # 可以调整图片大小
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG")
                base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

            start_time = time.time()

            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            response = self._send_request(self.vision_api_base, "/chat/completions", payload)

            end_time = time.time()
            response_time = end_time - start_time

            # 获取生成的文本和使用的 tokens 数量
            output = response['choices'][0]['message']['content']
            used_tokens = response.get('usage', {}).get('total_tokens', 0)

            result = {
                "success": True,
                "text": output.strip(),
                "used_tokens": used_tokens,
                "time_taken": response_time,
                "api_base": self.vision_api_base
            }
            
            self.logger.debug(f"👁️ 视觉分析成功: {used_tokens} tokens, {response_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 视觉分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "used_tokens": 0,
                "time_taken": 0,
                "api_base": self.vision_api_base
            }

    def test_connection(self) -> bool:
        """
        测试API连接状态
        
        :return: 连接是否成功
        """
        try:
            self.logger.info("🔍 测试API连接...")
            
            # 直接测试文本模型API
            self.logger.info("📝 测试文本模型API...")
            text_result = self.api_text("Hello", max_tokens=10, temperature=0.1)
            if not text_result.get("success"):
                self.logger.error(f"❌ 文本模型API测试失败: {text_result.get('error')}")
                return False
            else:
                self.logger.info("✅ 文本模型API测试成功")
            
            # 注意：这里不测试视觉模型，因为需要图片文件
            # 视觉模型将在实际使用时进行测试
            self.logger.info("✅ API连接测试完成")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ API连接测试失败: {e}")
            return False

    def call_text_model(self, messages: List[Dict], temperature: float = 0.7, 
                       max_tokens: int = 1000) -> Dict[str, Any]:
        """
        调用文本模型 (兼容性方法，适配原有的调用方式)
        
        :param messages: 消息列表
        :param temperature: 温度值
        :param max_tokens: 最大tokens
        :return: API响应
        """
        if not messages:
            return {"success": False, "error": "消息列表为空"}
        
        # 提取最后一条用户消息作为prompt
        prompt = ""
        for msg in messages:
            if msg.get("role") == "user":
                prompt = msg.get("content", "")
        
        if not prompt:
            return {"success": False, "error": "未找到用户消息"}
        
        result = self.api_text(prompt, max_tokens, temperature)
        
        # 转换格式以兼容原有调用方式
        if result.get("success"):
            return {
                "success": True,
                "content": result["text"],
                "usage": {"total_tokens": result["used_tokens"]},
                "time_taken": result["time_taken"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "未知错误")
            }

    def call_multimodal_model(self, messages: List[Dict], temperature: float = 0.7, 
                             max_tokens: int = 1000) -> Dict[str, Any]:
        """
        调用多模态模型 (兼容性方法，适配原有的调用方式)
        
        :param messages: 消息列表
        :param temperature: 温度值
        :param max_tokens: 最大tokens
        :return: API响应
        """
        if not messages:
            return {"success": False, "error": "消息列表为空"}
        
        # 提取文本和图像信息
        prompt = ""
        image_data = None
        
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            prompt = item.get("text", "")
                        elif item.get("type") == "image_url":
                            image_url = item.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:image"):
                                # 从base64数据中提取图像并保存为临时文件
                                try:
                                    import tempfile
                                    import os
                                    
                                    # 解码base64图像
                                    header, data = image_url.split(',', 1)
                                    image_bytes = base64.b64decode(data)
                                    
                                    # 保存为临时文件
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                                        tmp_file.write(image_bytes)
                                        image_data = tmp_file.name
                                except Exception as e:
                                    self.logger.error(f"处理base64图像失败: {e}")
                                    return {"success": False, "error": f"图像处理失败: {e}"}
        
        if not prompt:
            return {"success": False, "error": "未找到文本提示"}
        
        if not image_data:
            return {"success": False, "error": "未找到图像数据"}
        
        try:
            result = self.api_image(prompt, image_data, max_tokens, temperature)
            
            # 清理临时文件
            if image_data and image_data.startswith('/tmp'):
                try:
                    os.unlink(image_data)
                except:
                    pass
            
            # 转换格式以兼容原有调用方式
            if result.get("success"):
                return {
                    "success": True,
                    "content": result["text"],
                    "usage": {"total_tokens": result["used_tokens"]},
                    "time_taken": result["time_taken"]
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "未知错误")
                }
                
        except Exception as e:
            self.logger.error(f"多模态模型调用失败: {e}")
            return {"success": False, "error": str(e)}

    def get_model_info(self) -> Dict[str, str]:
        """
        获取模型配置信息
        
        :return: 模型配置信息
        """
        return {
            "text_model": "Qwen2.5-72B-Instruct",
            "vision_model": "Qwen2.5-VL-7B-instruct", 
            "text_api_base": self.text_api_base,
            "vision_api_base": self.vision_api_base,
            "api_key": "***" if self.api_key != "EMPTY" else "EMPTY",
            "bypass_proxy": self.bypass_proxy
        }


# 示例使用
if __name__ == "__main__":
    import os
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 初始化客户端（自动绕过代理）
    client = APIClient(bypass_proxy=True)
    
    # 获取模型信息
    model_info = client.get_model_info()
    print("\n🔧 模型配置:")
    for key, value in model_info.items():
        print(f"   {key}: {value}")
    
    # 测试连接
    if client.test_connection():
        print("\n✅ API连接测试成功")
        
        # 测试文本生成
        print("\n📝 测试文本生成:")
        result_text = client.api_text("请说一个笑话", max_tokens=50, temperature=0.7)
        if result_text["success"]:
            print(f"Generated Text: {result_text['text']}")
            print(f"Tokens Used: {result_text['used_tokens']}, Time Taken: {result_text['time_taken']:.2f}s")
        else:
            print(f"文本生成失败: {result_text['error']}")
        
        # 测试图像分析（需要提供实际的图片路径）
        image_path = "test_image.jpg"  # 如果有测试图片的话
        if os.path.exists(image_path):
            print(f"\n👁️ 测试图像分析: {image_path}")
            image_result = client.api_image("请描述这张图片", image_path, max_tokens=50, temperature=0.7)
            if image_result["success"]:
                print(f"Generated Text: {image_result['text']}")
                print(f"Tokens Used: {image_result['used_tokens']}, Time Taken: {image_result['time_taken']:.2f}s")
            else:
                print(f"图像分析失败: {image_result['error']}")
        else:
            print(f"\n⚠️ 图片文件不存在: {image_path}")
    else:
        print("\n❌ API连接测试失败")
        print("💡 请检查:")
        print("   1. API服务是否正常运行")
        print("   2. IP地址和端口是否正确")
        print("   3. 网络连接是否正常")