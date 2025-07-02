import openai
from typing import Optional

class OpenAIClient:
    """
    OpenAI API client.
    Probably works.
    """
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        openai.api_key = self.api_key
        if self.base_url:
            openai.api_base = self.base_url

    def chat_completion(self, model: str, messages: list[dict], temperature: float = 0.7, n: int = 1):
        """
        Call OpenAI's chat completion API
        """
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                # temperature=temperature,
                n=n
            )
            return response
        except Exception as e:
            raise RuntimeError(f"OpenAI API calling FAILURE: {e}")