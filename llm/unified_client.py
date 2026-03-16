"""
unified_client.py
统一 LLM 客户端入口

职责：
- 组合 ModelConfigManager + ImageLLMAPI，对外暴露简洁接口
- 支持运行时切换 provider / model，无需重建实例
- 是 guess_bench_analyzer.py 等业务代码的唯一依赖入口

使用示例：
    from unified_client import create_client

    # 使用 config.env 中的默认配置
    client = create_client()

    # 指定模型
    client = create_client(model="claude-sonnet-4-5-20250929")

    # 发送图片
    response = client.send_image("path/to/image.png", "这四个emoji代表什么成语？")

    # 切换模型（无需重建）
    client.switch_model("gemini-2.5-flash")
    response = client.send_image("path/to/image.png", "...")
"""

import logging
from pathlib import Path
from typing import Optional, Callable

from model_config_manager import ModelConfigManager
from image_llm_api import ImageLLMAPI

logger = logging.getLogger(__name__)


class UnifiedImageLLMClient:
    """
    统一图片 LLM 客户端

    封装配置读取和 API 调用，业务代码只需与本类交互。
    """

    def __init__(
        self,
        config_file: str = "config.env",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Args:
            config_file: 配置文件路径
            provider:    指定 provider（覆盖 config 文件中的 ACTIVE_MODEL_PROVIDER）
            model:       指定模型名（覆盖 config 文件中的默认模型）
        """
        self._mgr = ModelConfigManager(config_file)

        if provider:
            if not self._mgr.switch_provider(provider):
                raise ValueError(f"不支持的 provider: {provider!r}")

        if model:
            self._mgr.switch_model(model)

        self._api: ImageLLMAPI = self._build_api()

    def _build_api(self) -> ImageLLMAPI:
        """根据当前配置构建 ImageLLMAPI 实例"""
        cfg = self._mgr.get_active_config()

        if not cfg.get("api_key"):
            raise ValueError(
                f"Provider '{cfg['provider']}' 的 API Key 未配置，"
                f"请在 config.env 中设置对应的 KEY 字段。"
            )

        return ImageLLMAPI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model=cfg["model"],
        )

    # ── 切换接口 ─────────────────────────────────────

    def switch_provider(self, provider: str) -> "UnifiedImageLLMClient":
        """
        切换 provider 并重建底层 API 实例。

        Returns:
            self（支持链式调用）
        """
        if not self._mgr.switch_provider(provider):
            raise ValueError(f"不支持的 provider: {provider!r}")
        self._api = self._build_api()
        return self

    def switch_model(self, model: str) -> "UnifiedImageLLMClient":
        """
        切换模型（保持当前 provider 不变）。

        Returns:
            self（支持链式调用）
        """
        self._mgr.switch_model(model)
        self._api.switch_model(model)
        return self

    # ── 核心调用接口 ─────────────────────────────────

    def send_image(
        self,
        image_path: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        发送单张图片，返回模型回复文本。

        Args:
            image_path:    图片文件路径
            prompt:        用户 prompt
            system_prompt: 可选 system prompt
            **kwargs:      max_tokens, temperature 等 API 参数

        Returns:
            模型输出文本，失败返回 None。
        """
        return self._api.send_image(image_path, prompt, system_prompt, **kwargs)

    def batch_send(
        self,
        image_paths: list[str],
        prompt_fn: Callable,
        on_result: Optional[Callable] = None,
        **kwargs,
    ) -> list[dict]:
        """
        批量处理图片。

        Args:
            image_paths:  图片路径列表
            prompt_fn:    callable(image_path) -> prompt  或
                          callable(image_path) -> (prompt, system_prompt)
            on_result:    可选回调 callable(idx, image_path, response)
            **kwargs:     透传给 API 的参数

        Returns:
            list of {"image_path", "image_name", "response", "success"}
        """
        return self._api.batch_send(image_paths, prompt_fn, on_result, **kwargs)

    # ── 信息查询接口 ─────────────────────────────────

    @property
    def current_model(self) -> str:
        return self._api.model

    @property
    def current_provider(self) -> str:
        return self._mgr.active_provider

    @property
    def current_base_url(self) -> str:
        return self._api.base_url

    def print_status(self):
        """打印当前配置状态"""
        self._mgr.print_status()

    def list_providers(self) -> dict:
        """列出所有可用 provider"""
        return self._mgr.list_providers()

    def __repr__(self):
        return (
            f"UnifiedImageLLMClient("
            f"provider={self.current_provider!r}, "
            f"model={self.current_model!r})"
        )


# ── 便捷工厂函数 ─────────────────────────────────────

def create_client(
    model: Optional[str] = None,
    provider: Optional[str] = None,
    config_file: str = "config.env",
) -> UnifiedImageLLMClient:
    """
    创建 UnifiedImageLLMClient 的快捷方式。

    Args:
        model:       指定模型名称（不填则使用 config.env 中的默认值）
        provider:    指定 provider（不填则使用 config.env 中的 ACTIVE_MODEL_PROVIDER）
        config_file: 配置文件路径

    Returns:
        配置好的 UnifiedImageLLMClient 实例

    Examples:
        client = create_client()                              # 使用默认配置
        client = create_client(model="gpt-4o")               # 指定模型
        client = create_client(model="gemini-2.5-flash")
        client = create_client(provider="openai", model="gpt-4.1")
    """
    return UnifiedImageLLMClient(
        config_file=config_file,
        provider=provider,
        model=model,
    )