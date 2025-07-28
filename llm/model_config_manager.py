"""
多模型配置管理器
支持 OpenAI、阿里云 DashScope、Azure、Anthropic 等多种 API
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

class ModelConfigManager:
    """多模型配置管理器"""
    
    def __init__(self, config_file: str = "config.env"):
        self.config_file = config_file
        self.config = self._load_config()
        self.active_provider = self.config.get("ACTIVE_MODEL_PROVIDER", "openai").lower()
    
    def _load_config(self) -> Dict[str, str]:
        """从配置文件加载配置"""
        config = {}
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
                print(f"✅ 成功加载配置文件: {self.config_file}")
            except Exception as e:
                print(f"⚠️ 读取配置文件出错: {e}")
        else:
            print(f"⚠️ 配置文件不存在: {self.config_file}")
        
        return config
    
    def get_active_config(self) -> Dict[str, Any]:
        """获取当前激活的模型配置"""
        provider = self.active_provider
        
        if provider == "openai":
            return self._get_openai_config()
        elif provider == "dashscope":
            return self._get_dashscope_config()
        elif provider == "azure":
            return self._get_azure_config()
        elif provider == "anthropic":
            return self._get_anthropic_config()
        elif provider == "general":
            return self._get_general_config()
        else:
            raise ValueError(f"不支持的模型提供商: {provider}")
    
    def _get_openai_config(self) -> Dict[str, Any]:
        """获取 OpenAI 配置"""
        return {
            "provider": "openai",
            "api_key": self.config.get("OPENAI_API_KEY", ""),
            "base_url": self.config.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "model": self.config.get("OPENAI_MODEL", "gpt-4o"),
            "api_type": "openai"
        }
    
    def _get_dashscope_config(self) -> Dict[str, Any]:
        """获取阿里云 DashScope 配置"""
        return {
            "provider": "dashscope",
            "api_key": self.config.get("DASHSCOPE_API_KEY", ""),
            "base_url": self.config.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "model": self.config.get("DASHSCOPE_MODEL", "qwen-vl-plus"),
            "api_type": "openai_compatible"
        }
    
    def _get_azure_config(self) -> Dict[str, Any]:
        """获取 Azure OpenAI 配置"""
        return {
            "provider": "azure",
            "api_key": self.config.get("AZURE_API_KEY", ""),
            "base_url": self.config.get("AZURE_BASE_URL", ""),
            "model": self.config.get("AZURE_MODEL", "gpt-4o"),
            "api_version": self.config.get("AZURE_API_VERSION", "2024-02-15-preview"),
            "api_type": "azure"
        }
    
    def _get_anthropic_config(self) -> Dict[str, Any]:
        """获取 Anthropic 配置"""
        return {
            "provider": "anthropic",
            "api_key": self.config.get("ANTHROPIC_API_KEY", ""),
            "base_url": self.config.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "model": self.config.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "api_type": "anthropic"
        }
    
    def _get_general_config(self) -> Dict[str, Any]:
        """获取通用配置"""
        return {
            "provider": "general",
            "api_key": self.config.get("GENERAL_API_KEY", ""),
            "base_url": self.config.get("GENERALBASE_URL", ""),
            "model": self.config.get("GENERAL_MODEL", ""),
            "api_type": "openai_compatible"
        }
    
    def list_available_providers(self) -> Dict[str, Dict[str, str]]:
        """列出所有可用的模型提供商"""
        providers = {}
        
        # 检查每个提供商的配置
        for provider in ["openai", "dashscope", "azure", "anthropic", "general"]:
            temp_provider = self.active_provider
            self.active_provider = provider
            try:
                config = self.get_active_config()
                if config["api_key"] and config["api_key"] != "":
                    providers[provider] = {
                        "name": self._get_provider_name(provider),
                        "model": config["model"],
                        "status": "✅ 已配置"
                    }
                else:
                    providers[provider] = {
                        "name": self._get_provider_name(provider),
                        "model": config["model"],
                        "status": "⚠️ 未配置 API Key"
                    }
            except Exception as e:
                providers[provider] = {
                    "name": self._get_provider_name(provider),
                    "model": "未知",
                    "status": f"❌ 配置错误: {e}"
                }
            finally:
                self.active_provider = temp_provider
        
        return providers
    
    def _get_provider_name(self, provider: str) -> str:
        """获取提供商的友好名称"""
        names = {
            "openai": "OpenAI 官方",
            "dashscope": "阿里云 DashScope",
            "azure": "Azure OpenAI",
            "anthropic": "Anthropic Claude",
            "custom": "自定义服务"
        }
        return names.get(provider, provider)
    
    def validate_config(self, provider: Optional[str] = None) -> bool:
        """验证配置是否正确"""
        if provider:
            temp_provider = self.active_provider
            self.active_provider = provider
        
        try:
            config = self.get_active_config()
            
            # 检查必要字段
            if not config.get("api_key"):
                print(f"❌ {self._get_provider_name(self.active_provider)} 缺少 API Key")
                return False
            
            if not config.get("base_url"):
                print(f"❌ {self._get_provider_name(self.active_provider)} 缺少 Base URL")
                return False
            
            if not config.get("model"):
                print(f"❌ {self._get_provider_name(self.active_provider)} 缺少模型名称")
                return False
            
            print(f"✅ {self._get_provider_name(self.active_provider)} 配置验证通过")
            return True
            
        except Exception as e:
            print(f"❌ {self._get_provider_name(self.active_provider)} 配置验证失败: {e}")
            return False
        finally:
            if provider:
                self.active_provider = temp_provider
    
    def switch_provider(self, provider: str) -> bool:
        """切换模型提供商"""
        if provider.lower() not in ["openai", "dashscope", "azure", "anthropic", "custom"]:
            print(f"❌ 不支持的提供商: {provider}")
            return False
        
        old_provider = self.active_provider
        self.active_provider = provider.lower()
        
        if self.validate_config():
            print(f"✅ 成功切换到: {self._get_provider_name(provider)}")
            return True
        else:
            self.active_provider = old_provider
            print(f"❌ 切换失败，回退到: {self._get_provider_name(old_provider)}")
            return False
    
    def print_current_config(self):
        """打印当前配置信息"""
        try:
            config = self.get_active_config()
            provider_name = self._get_provider_name(self.active_provider)
            
            print(f"🎯 当前使用: {provider_name}")
            print(f"   API Key: {config['api_key'][:10]}...{config['api_key'][-4:]}")
            print(f"   Base URL: {config['base_url']}")
            print(f"   Model: {config['model']}")
            
            if "api_version" in config:
                print(f"   API Version: {config['api_version']}")
            
        except Exception as e:
            print(f"❌ 获取配置信息失败: {e}")

def create_sample_config():
    """创建示例配置文件"""
    sample_config = """# LLM API 多模型配置文件

# =========================
# 模型选择配置 (选择一个)
# =========================
# 可选值: openai, dashscope, azure, anthropic, custom
ACTIVE_MODEL_PROVIDER=openai

# =========================
# OpenAI 官方 API 配置
# =========================
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# =========================
# 阿里云 DashScope 配置
# =========================
DASHSCOPE_API_KEY=your-dashscope-api-key-here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-vl-plus

# =========================
# Azure OpenAI 配置
# =========================
AZURE_API_KEY=your-azure-api-key-here
AZURE_BASE_URL=https://your-resource.openai.azure.com
AZURE_MODEL=gpt-4o
AZURE_API_VERSION=2024-02-15-preview

# =========================
# Anthropic Claude 配置
# =========================
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# =========================
# 自定义 API 配置
# =========================
CUSTOM_API_KEY=your-custom-api-key
CUSTOM_BASE_URL=https://your-custom-api.com/v1
CUSTOM_MODEL=your-model-name

# =========================
# 请求配置
# =========================
REQUEST_TIMEOUT=60
MAX_IMAGE_SIZE=1024
MAX_TOKENS=1000
TEMPERATURE=0.7
"""
    
    with open("config.env", 'w', encoding='utf-8') as f:
        f.write(sample_config)
    
    print("✅ 已创建示例配置文件: config.env")
    print("请编辑此文件，填入您的实际 API 配置")

if __name__ == "__main__":
    # 测试配置管理器
    if not os.path.exists("config.env"):
        print("配置文件不存在，创建示例配置...")
        create_sample_config()
    
    manager = ModelConfigManager()
    
    print("=== 多模型配置管理器测试 ===\n")
    
    # 显示当前配置
    manager.print_current_config()
    
    print("\n=== 可用的模型提供商 ===")
    providers = manager.list_available_providers()
    for provider, info in providers.items():
        print(f"{info['name']}: {info['model']} - {info['status']}")
    
    # 验证当前配置
    print(f"\n=== 配置验证 ===")
    manager.validate_config()
