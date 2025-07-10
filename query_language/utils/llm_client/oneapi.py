import openai
from typing import Optional

class OneAPIClient:
    """
    OneAPI API client.
    """
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = "sk-eBdspKZFfH70b8SfBaCcE9Ee7e7a4b3b87A46421B714F09e"
        self.base_url = "http://10.119.11.146:3000/v1"
        openai.api_key = self.api_key
        if self.base_url:
            openai.api_base = self.base_url

    def chat_completion(self, model: str, messages: list[dict], n: int = 1):
        """
        Call OpenAI's chat completion API
        """
        if model == "one_api deepseek-reasoner":
            mymodel = "deepseek-reasoner"
        elif model == "one_api deepseek-chat":
            mymodel = "deepseek-chat"
        elif model == "one_api gpt-3.5-turbo":
            mymodel = "gpt-3.5-turbo"
        elif model == "one_api gpt-4o-mini":
            mymodel = "gpt-4o-mini"
        elif model == "one_api glm-4-flash-250414":
            mymodel = "glm-4-flash-250414"
        elif model == "one-api gemini-2.0-flash":
            mymodel = "gemini-2.0-flash"
        else:
            return NotImplementedError(f"Model {model} not implemented in OneAPIClient.")



        try:
            response = openai.ChatCompletion.create(
                model=mymodel,
                messages=messages,
                n=n
            )
            return response
        except Exception as e:
            raise RuntimeError(f"OpenAI API calling FAILURE: {e}")