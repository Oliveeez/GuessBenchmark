import zhipuai
from typing import Optional

class ZhipuAIClient:
    """
    ZhipuAI API client.
    Not sure if works well.
    """
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        # ZhipuAI's SDK initialisation method
        zhipuai.api_key = self.api_key
        if self.base_url:
            zhipuai.api_base = self.base_url

    def chat_completion(self, model: str, messages: list[dict], temperature: float = 0.7, n: int = 1):
        """
        Call ZhipuAI's chat completion API
        """
        try:
            # Using ZhipuAI's API Interface Format
            response = zhipuai.model_api.invoke(
                model=model,
                prompt=messages,
                temperature=temperature,
                top_n=n
            )
            return response
        except Exception as e:
            raise RuntimeError(f"ZhipuAI API calling FAILURE: {e}")