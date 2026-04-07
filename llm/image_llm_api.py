"""
image_llm_api.py
底层图片 LLM API 调用模块

职责：
- 图片编码（base64）与尺寸预处理
- 构造 OpenAI-compatible 多模态请求体
- 发送请求并处理响应
- 自动重试（最多5次，间隔30s，符合博阅API要求）

不关心 provider / config 读取，只需传入 api_key / base_url / model。
"""

import base64
import io
import json
import time
import logging
from pathlib import Path
from typing import Optional, Union

import requests
from PIL import Image

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 支持的视觉模型列表（用于校验和文档提示）
# ─────────────────────────────────────────────
VISION_MODELS = {
    # GPT 系列
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4-vision-preview",
    # Claude 系列
    "claude-opus-4-5-20250929",
    "claude-sonnet-4-5-20250929",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    # Gemini 系列
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    # Qwen 系列
    "qwen-vl-max",
    "qwen-vl-plus",
    "qwen2.5-vl-72b-instruct",
    "qwen2.5-vl-7b-instruct",
    # 其他
    "glm-4v",
    "glm-4v-plus",
}

# 支持的图片 MIME 类型
SUPPORTED_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# 重试配置（符合博阅 API 文档要求）
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_INTERVAL = 30  # 秒


class ImageLLMAPI:
    """
    底层图片 LLM API 客户端（OpenAI-compatible 格式）

    使用方式：
        client = ImageLLMAPI(
            api_key="sk-xxx",
            base_url="https://apicz.boyuerichdata.com/v1",
            model="gpt-4o"
        )
        response = client.send_image("path/to/image.png", "这张图片代表什么成语？")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apicz.boyuerichdata.com/v1",
        model: str = "gpt-4o",
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_interval: int = DEFAULT_RETRY_INTERVAL,
        timeout: int = 60,
        max_image_size: int = 1024,
    ):
        """
        Args:
            api_key:         API 密钥
            base_url:        API base URL（末尾不含 /）
            model:           模型名称
            max_retries:     最大重试次数（默认5，符合博阅文档建议）
            retry_interval:  每次重试间隔秒数（默认30）
            timeout:         单次请求超时秒数
            max_image_size:  图片最长边的最大像素，超出则等比缩放
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.timeout = timeout
        self.max_image_size = max_image_size

        self._endpoint = f"{self.base_url}/chat/completions"
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        if model not in VISION_MODELS:
            logger.warning(
                f"模型 '{model}' 不在已知视觉模型列表中，"
                f"如确认支持视觉输入可忽略此警告。"
            )

    # ── 图片处理 ────────────────────────────────────

    def encode_image(self, image_path: str) -> tuple[str, str]:
        """
        将图片文件编码为 base64，并返回对应的 MIME 类型。

        Returns:
            (base64_str, mime_type)  例如 ("iVBOR...", "image/png")
        """
        path = Path(image_path)
        suffix = path.suffix.lower()
        mime_type = SUPPORTED_MIME.get(suffix, "image/jpeg")

        with open(image_path, "rb") as f:
            raw = f.read()

        return base64.b64encode(raw).decode("utf-8"), mime_type

    def _resize_image(self, image_path: str) -> str:
        """
        若图片最长边超过 max_image_size，等比缩放后保存为临时文件。

        Returns:
            原路径（无需缩放）或临时文件路径
        """
        img = Image.open(image_path)
        w, h = img.size
        max_side = max(w, h)

        if max_side <= self.max_image_size:
            return image_path  # 无需处理

        scale = self.max_image_size / max_side
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # 写入内存缓冲，避免产生临时文件
        buf = io.BytesIO()
        fmt = "PNG" if Path(image_path).suffix.lower() == ".png" else "JPEG"
        img.save(buf, format=fmt)
        buf.seek(0)

        # 保存到同目录的临时文件
        tmp_path = str(image_path) + "_resized_tmp.jpg"
        with open(tmp_path, "wb") as f:
            f.write(buf.read())

        logger.debug(f"图片已缩放: {w}x{h} → {new_w}x{new_h}，临时文件: {tmp_path}")
        return tmp_path

    def prepare_image(self, image_path: str) -> tuple[str, str]:
        """
        预处理图片：缩放（如需）+ 编码 base64。

        Returns:
            (base64_str, mime_type)
        """
        resized_path = self._resize_image(image_path)
        b64, mime = self.encode_image(resized_path)

        # 清理临时文件
        if resized_path != image_path:
            try:
                Path(resized_path).unlink()
            except Exception:
                pass

        return b64, mime

    # ── 请求构造 ─────────────────────────────────────

    def build_messages(
        self,
        image_b64: str,
        mime_type: str,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """
        构造 OpenAI vision 格式的 messages 列表。

        图片以 base64 data URI 形式内嵌，兼容所有 OpenAI-compatible 端点。
        """
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}",
                    "detail": "high",
                },
            },
            {
                "type": "text",
                "text": prompt,
            },
        ]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        return messages

    # ── API 调用（含重试） ───────────────────────────

    def _call_once(self, messages: list[dict], **kwargs) -> str:
        """
        发送单次请求，返回模型输出文本。
        失败时抛出异常，由上层重试逻辑处理。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
        }

        # 允许调用方透传额外参数（如 top_p 等）
        for key in ("top_p", "stream"):
            if key in kwargs:
                payload[key] = kwargs[key]

        resp = requests.post(
            self._endpoint,
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"HTTP {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def call_api(self, messages: list[dict], **kwargs) -> Optional[str]:
        """
        带自动重试的 API 调用。

        Returns:
            模型输出文本，全部重试失败则返回 None。
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._call_once(messages, **kwargs)
                if attempt > 1:
                    logger.info(f"第 {attempt} 次重试成功")
                return result

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        f"请求失败（第{attempt}/{self.max_retries}次）: {e}，"
                        f"{self.retry_interval}s 后重试..."
                    )
                    time.sleep(self.retry_interval)
                else:
                    logger.error(
                        f"请求失败，已达最大重试次数 {self.max_retries}: {e}"
                    )

        return None

    # ── 对外主接口 ───────────────────────────────────

    def send_image(
        self,
        image_path: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        发送单张图片 + prompt，返回模型回复文本。

        Args:
            image_path:    图片文件路径
            prompt:        用户提问文本
            system_prompt: 可选的 system 消息
            **kwargs:      透传给 API 的参数（max_tokens, temperature 等）

        Returns:
            模型输出文本，失败返回 None。
        """
        try:
            b64, mime = self.prepare_image(image_path)
        except Exception as e:
            logger.error(f"图片处理失败 [{image_path}]: {e}")
            return None

        messages = self.build_messages(b64, mime, prompt, system_prompt)
        return self.call_api(messages, **kwargs)

    def batch_send(
        self,
        image_paths: list[str],
        prompt_fn,
        on_result=None,
        **kwargs,
    ) -> list[dict]:
        """
        批量处理图片列表。

        Args:
            image_paths:  图片路径列表
            prompt_fn:    callable(image_path) -> (prompt, system_prompt)
                          或 callable(image_path) -> prompt
            on_result:    可选回调 callable(idx, image_path, response)，
                          每张图处理完后调用（可用于实时保存结果）
            **kwargs:     透传给 API 的参数

        Returns:
            list of {"image_path": str, "response": str | None, "success": bool}
        """
        results = []
        total = len(image_paths)

        for idx, image_path in enumerate(image_paths, start=1):
            logger.info(f"[{idx}/{total}] 处理: {Path(image_path).name}")

            # 解析 prompt_fn 的返回值
            fn_result = prompt_fn(image_path)
            if isinstance(fn_result, tuple) and len(fn_result) == 2:
                prompt, system_prompt = fn_result
            else:
                prompt, system_prompt = fn_result, None

            response = self.send_image(
                image_path, prompt, system_prompt, **kwargs
            )
            success = response is not None

            record = {
                "image_path": image_path,
                "image_name": Path(image_path).name,
                "response": response,
                "success": success,
            }
            results.append(record)

            if on_result:
                on_result(idx, image_path, response)

            if not success:
                logger.warning(f"失败: {image_path}")

        success_count = sum(1 for r in results if r["success"])
        logger.info(f"批量处理完成: {success_count}/{total} 成功")
        return results

    # ── 工具方法 ─────────────────────────────────────

    def switch_model(self, model: str):
        """运行时切换模型（无需重新创建实例）"""
        if model not in VISION_MODELS:
            logger.warning(f"模型 '{model}' 不在已知视觉模型列表中")
        self.model = model
        logger.info(f"模型已切换为: {model}")

    def get_model_info(self) -> dict:
        """返回当前配置信息"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "max_retries": self.max_retries,
            "retry_interval": self.retry_interval,
            "max_image_size": self.max_image_size,
        }

    def __repr__(self):
        return f"ImageLLMAPI(model={self.model!r}, base_url={self.base_url!r})"