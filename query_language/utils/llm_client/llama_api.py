from typing import Optional
#import llama_api  # import the official SDK of Llama API

class LlamaAPIClient:
    """
    Llama API client.
    Not sure if this is the correct way to use the Llama API SDK.
    """
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        # Llama API global settings 
#        llama_api.api_key = self.api_key
#        if self.base_url:
#            llama_api.api_base = self.base_url

#    def chat_completion(self, model: str, messages: list[dict], temperature: float = 0.7, n: int = 1):
#        """
#        Call Llama's chat completion API
#        """
#        try:
#            response = llama_api.ChatCompletion.create(
#                model=model,
#                messages=messages,
#                temperature=temperature,
#                n=n
#            )
#            return response
#        except Exception as e:
#            raise RuntimeError(f"Llama API calling falled: {e}")
