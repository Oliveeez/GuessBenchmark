"""
统一的多模型 API 客户端
自动从配置文件加载并创建对应的 API 客户端
"""

from model_config_manager import ModelConfigManager
from image_llm_api import ImageLLMAPI
from typing import Optional

class UnifiedImageLLMClient:
    """统一的图片 LLM 客户端"""
    
    def __init__(self, config_file: str = "config.env", provider: Optional[str] = None):
        """
        初始化统一客户端
        
        Args:
            config_file: 配置文件路径
            provider: 指定使用的提供商，如果为 None 则使用配置文件中的设置
        """
        self.config_manager = ModelConfigManager(config_file)
        
        if provider:
            # 切换到指定的提供商
            if not self.config_manager.switch_provider(provider):
                raise ValueError(f"无法切换到提供商: {provider}")
        
        # 获取当前配置并创建客户端
        self.config = self.config_manager.get_active_config()
        self.client = self._create_client()
    
    def _create_client(self) -> ImageLLMAPI:
        """根据配置创建对应的 API 客户端"""
        config = self.config
        
        # 创建客户端参数
        client_args = {
            "api_key": config["api_key"],
            "base_url": config["base_url"],
            "model": config["model"],
            "api_type": config["api_type"]
        }
        
        # 添加额外的配置参数
        if "api_version" in config:
            client_args["api_version"] = config["api_version"]
        
        return ImageLLMAPI(**client_args)
    
    def send_image_with_prompt(self, image_path: str, prompt: str, **kwargs):
        """发送图片和提示词到 LLM"""
        return self.client.send_image_with_prompt(image_path, prompt, **kwargs)
    
    def batch_process_images(self, image_folder: str, prompt: str, output_file: Optional[str] = None):
        """批量处理图片"""
        return self.client.batch_process_images(image_folder, prompt, output_file)
    
    def get_current_provider(self) -> str:
        """获取当前使用的提供商"""
        return self.config["provider"]
    
    def get_current_model(self) -> str:
        """获取当前使用的模型"""
        return self.config["model"]
    
    def switch_provider(self, provider: str) -> bool:
        """切换模型提供商"""
        if self.config_manager.switch_provider(provider):
            self.config = self.config_manager.get_active_config()
            self.client = self._create_client()
            return True
        return False
    
    def list_available_providers(self):
        """列出可用的提供商"""
        return self.config_manager.list_available_providers()
    
    def print_current_config(self):
        """打印当前配置"""
        self.config_manager.print_current_config()

def create_client_from_config(config_file: str = "config.env", provider: Optional[str] = None) -> UnifiedImageLLMClient:
    """
    从配置文件创建客户端的便捷函数
    
    Args:
        config_file: 配置文件路径
        provider: 指定提供商（可选）
        
    Returns:
        统一客户端实例
    """
    return UnifiedImageLLMClient(config_file, provider)

if __name__ == "__main__":
    # 测试统一客户端
    try:
        client = create_client_from_config()
        
        print("=== 统一 LLM 客户端测试 ===\n")
        
        # 显示当前配置
        client.print_current_config()
        
        print(f"\n当前提供商: {client.get_current_provider()}")
        print(f"当前模型: {client.get_current_model()}")
        
        print(f"\n=== 可用提供商 ===")
        providers = client.list_available_providers()
        for provider, info in providers.items():
            status = "✅" if provider == client.get_current_provider() else "  "
            print(f"{status} {info['name']}: {info['model']} - {info['status']}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        print("请检查配置文件是否存在且配置正确")
