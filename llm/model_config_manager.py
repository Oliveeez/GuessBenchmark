"""
model_config_manager.py
多 Provider 配置管理器

职责：
- 读取 config.env，管理多个 API provider 的配置
- 支持运行时切换 provider 和模型
- 当前主力 provider 为 boyue（博阅 API）
- 保留 openai/azure/anthropic/dashscope/general 入口，将来切回时直接改 config.env 即可

config.env 示例（在项目根目录）：
    ACTIVE_MODEL_PROVIDER=boyue

    BOYUE_API_KEY=sk-xxx
    BOYUE_BASE_URL=https://apicz.boyuerichdata.com/v1
    BOYUE_MODEL=gpt-4o

    OPENAI_API_KEY=sk-xxx
    OPENAI_BASE_URL=https://api.openai.com/v1
    OPENAI_MODEL=gpt-4o
    ...
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 所有视觉模型（按 provider 分组，方便查阅）
PROVIDER_DEFAULT_MODELS = {
    "boyue": "gpt-4o",
    "openai": "gpt-4o",
    "azure": "gpt-4o",
    "anthropic": "claude-sonnet-4-5-20250929",
    "dashscope": "qwen-vl-max",
    "general": "gpt-4o",
}

# 各 provider 对应的 API 类型（用于鉴权头选择）
PROVIDER_API_TYPES = {
    "boyue": "openai_compatible",
    "openai": "openai",
    "azure": "azure",
    "anthropic": "anthropic",
    "dashscope": "openai_compatible",
    "general": "openai_compatible",
}


class ModelConfigManager:
    """
    多 Provider 配置管理器

    使用示例：
        mgr = ModelConfigManager("config.env")
        config = mgr.get_active_config()
        # config = {"api_key": ..., "base_url": ..., "model": ..., "provider": ..., ...}

        mgr.switch_provider("openai")
        mgr.switch_model("gpt-4.1")
    """

    def __init__(self, config_file: str = "config.env"):
        """
        Args:
            config_file: 配置文件路径，相对路径时从脚本所在目录向上查找
        """
        self.config_file = self._resolve_config_path(config_file)
        self._raw = self._load_file()
        self.active_provider = self._raw.get(
            "ACTIVE_MODEL_PROVIDER", "boyue"
        ).lower().strip()
        # 运行时 model 覆盖（switch_model 时使用，优先于 config 文件）
        self._model_override: Optional[str] = None

    # ── 文件加载 ─────────────────────────────────────

    def _resolve_config_path(self, config_file: str) -> Path:
        """在当前目录和父目录中查找 config.env"""
        p = Path(config_file)
        if p.is_absolute() or p.exists():
            return p
        # 向上最多查找 3 层
        search_dir = Path(__file__).parent
        for _ in range(4):
            candidate = search_dir / config_file
            if candidate.exists():
                return candidate
            search_dir = search_dir.parent
        logger.warning(f"配置文件未找到: {config_file}，将使用环境变量或默认值")
        return Path(config_file)

    def _load_file(self) -> dict:
        """解析 config.env，返回 key-value 字典"""
        config = {}
        if not self.config_file.exists():
            logger.warning(f"配置文件不存在: {self.config_file}")
            return config

        with open(self.config_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip().strip('"').strip("'")

        logger.debug(f"已加载配置文件: {self.config_file}，共 {len(config)} 项")
        return config

    def _get(self, key: str, default: str = "") -> str:
        """先查 config 文件，再查环境变量"""
        return self._raw.get(key) or os.environ.get(key) or default

    # ── 各 Provider 配置获取 ──────────────────────────

    def _get_boyue_config(self) -> dict:
        return {
            "provider": "boyue",
            "api_type": "openai_compatible",
            "api_key": self._get("BOYUE_API_KEY"),
            "base_url": self._get("BOYUE_BASE_URL", "https://apicz.boyuerichdata.com/v1"),
            "model": self._get("BOYUE_MODEL", PROVIDER_DEFAULT_MODELS["boyue"]),
        }

    def _get_openai_config(self) -> dict:
        return {
            "provider": "openai",
            "api_type": "openai",
            "api_key": self._get("OPENAI_API_KEY"),
            "base_url": self._get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "model": self._get("OPENAI_MODEL", PROVIDER_DEFAULT_MODELS["openai"]),
        }

    def _get_azure_config(self) -> dict:
        return {
            "provider": "azure",
            "api_type": "azure",
            "api_key": self._get("AZURE_API_KEY"),
            "base_url": self._get("AZURE_BASE_URL"),
            "model": self._get("AZURE_MODEL", PROVIDER_DEFAULT_MODELS["azure"]),
            "api_version": self._get("AZURE_API_VERSION", "2024-02-15-preview"),
        }

    def _get_anthropic_config(self) -> dict:
        return {
            "provider": "anthropic",
            "api_type": "openai_compatible",   # 走代理时统一用 OpenAI 兼容格式
            "api_key": self._get("ANTHROPIC_API_KEY"),
            "base_url": self._get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "model": self._get("ANTHROPIC_MODEL", PROVIDER_DEFAULT_MODELS["anthropic"]),
        }

    def _get_dashscope_config(self) -> dict:
        return {
            "provider": "dashscope",
            "api_type": "openai_compatible",
            "api_key": self._get("DASHSCOPE_API_KEY"),
            "base_url": self._get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "model": self._get("DASHSCOPE_MODEL", PROVIDER_DEFAULT_MODELS["dashscope"]),
        }

    def _get_general_config(self) -> dict:
        return {
            "provider": "general",
            "api_type": "openai_compatible",
            "api_key": self._get("GENERAL_API_KEY"),
            "base_url": self._get("GENERAL_BASE_URL"),
            "model": self._get("GENERAL_MODEL", PROVIDER_DEFAULT_MODELS["general"]),
        }

    # ── 对外接口 ─────────────────────────────────────

    _GETTERS = {
        "boyue":     "_get_boyue_config",
        "openai":    "_get_openai_config",
        "azure":     "_get_azure_config",
        "anthropic": "_get_anthropic_config",
        "dashscope": "_get_dashscope_config",
        "general":   "_get_general_config",
    }

    def get_active_config(self) -> dict:
        """
        获取当前激活 provider 的完整配置字典。

        Returns:
            {
                "provider": str,
                "api_type": str,
                "api_key": str,
                "base_url": str,
                "model": str,
                ...  # azure 会额外有 api_version
            }
        """
        getter_name = self._GETTERS.get(self.active_provider)
        if not getter_name:
            raise ValueError(
                f"不支持的 provider: {self.active_provider!r}，"
                f"可选: {list(self._GETTERS.keys())}"
            )
        config = getattr(self, getter_name)()

        # 应用运行时 model 覆盖
        if self._model_override:
            config["model"] = self._model_override

        return config

    def switch_provider(self, provider: str) -> bool:
        """
        切换 provider，清除运行时 model 覆盖。

        Returns:
            True 表示切换成功，False 表示 provider 不存在。
        """
        provider = provider.lower().strip()
        if provider not in self._GETTERS:
            logger.error(f"不支持的 provider: {provider!r}")
            return False
        self.active_provider = provider
        self._model_override = None
        logger.info(f"Provider 已切换为: {provider}")
        return True

    def switch_model(self, model: str):
        """
        在当前 provider 下覆盖模型名称（不修改 config 文件）。
        """
        self._model_override = model
        logger.info(f"模型已切换为: {model}（provider={self.active_provider}）")

    def list_providers(self) -> dict:
        """
        列出所有 provider 及其状态。

        Returns:
            {provider_name: {"active": bool, "has_key": bool, "default_model": str}}
        """
        result = {}
        for p in self._GETTERS:
            key_env = f"{p.upper()}_API_KEY"
            has_key = bool(self._get(key_env))
            result[p] = {
                "active": p == self.active_provider,
                "has_key": has_key,
                "default_model": PROVIDER_DEFAULT_MODELS.get(p, "—"),
            }
        return result

    def print_status(self):
        """打印当前配置状态（调试用）"""
        config = self.get_active_config()
        print("=" * 50)
        print(f"  Active Provider : {config['provider']}")
        print(f"  Model           : {config['model']}")
        print(f"  Base URL        : {config['base_url']}")
        print(f"  API Key         : {'*' * 8}{config['api_key'][-6:] if config['api_key'] else '(未设置)'}")
        print("=" * 50)
        print("  所有 Provider 状态:")
        for name, info in self.list_providers().items():
            mark = "▶" if info["active"] else " "
            key_status = "✓" if info["has_key"] else "✗"
            print(f"  {mark} {name:<12} key={key_status}  默认模型={info['default_model']}")
        print("=" * 50)