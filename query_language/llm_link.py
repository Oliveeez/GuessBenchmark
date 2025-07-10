import openai
import time
import logging
import random
from typing import Optional
import concurrent.futures
import re
import emoji

logger = logging.getLogger(__name__)

class ChatModel:
    """
    How to use it:

    model = ChatModel(model="gpt-4", api_key=
        "your_api_key").init_model()
    response = model.multi_chat_completion(
        messages_list=[...], n=1)
    """
    def __init__(
        self,
        model: str = "deepseek-v3",
        temperature: float = 0.5,   # medium-high diversity and medium-high quality
        base_url: Optional[str] = "http://123.129.219.111:3000/v1",
        api_key: Optional[str] = "sk-LwyvquF9WxkHAtHXF0UpEYPD7t3CQq1ApWOoK8ETTxBr84gj",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key          # TODO: here add an 'or' to employ our API.
        self.base_url = base_url
        self.client = None

    def init_model(self):
        if self.model.startswith("gpt"):
            from utils.llm_client.openai import OpenAIClient
            self.client = OpenAIClient(api_key=self.api_key, base_url=self.base_url)
        elif self.model.startswith("deepseek"):
            from utils.llm_client.deepseek import DeepSeekClient
            self.client = DeepSeekClient(api_key=self.api_key, base_url=self.base_url)
        elif self.model.startswith("GLM"):
            from utils.llm_client.zhipuai import ZhipuAIClient
            self.client = ZhipuAIClient(api_key=self.api_key, base_url=self.base_url)
        elif self.model.startswith("one_api"):
            from utils.llm_client.oneapi import OneAPIClient
            self.client = OneAPIClient(api_key=self.api_key, base_url=self.base_url)
        else:
            from utils.llm_client.llama_api import LlamaAPIClient
            self.client = LlamaAPIClient(api_key=self.api_key, base_url=self.base_url)
        
        if not self.client:
            logger.fatal(f"Cannot Initialize LLM: {self.model}")
            exit(-1)
        
        return self

    def _chat_completion_api(self, messages: list[dict], n: int = 1, temperature: float = 0.4):
        """
        Actually calling the appropriate API based on the model
        """
        try:
            if self.model.startswith("one_api"):
                # OneAPI's API Interface Format
                response = self.client.chat_completion(
                    model=self.model,
                    messages=messages,
                    n=n
                )
            else:
                response = self.client.chat_completion(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    n=n
                )
            return response["choices"]  # 返回生成的结果
        except Exception as e:
            logging.error(f"API calling FAILED: {e}")
            return None

    def chat_completion(self, n: int, messages: list[dict]) -> list[dict]:
        """
        Utilizing '_chat_completion_api'
        """
        temperature = self.temperature
        time.sleep(random.random())  # avoid speed limit
        for attempt in range(5):  # retry 5 times at most
            try:
                response_cur = self._chat_completion_api(messages, n, temperature)
                if response_cur:
                    return response_cur
            except Exception as e:
                logging.exception(e)
                logging.info(f"{attempt+1} times calling failed: {e}")
                time.sleep(1)
        
        logging.error("Failed 5 times, exiting...")
        exit()
        
    def multi_chat_completion(self, messages_list: list[list[dict]], n: int = 1, temperature: float = None):
        """
        Generate multiple dialogue responses to support parallel calls
        """
        temperature = temperature or self.temperature
        assert isinstance(messages_list, list), "messages_list should be a list."
        if not isinstance(messages_list[0], list):
            messages_list = [messages_list]

        if len(messages_list) > 1:
            assert n == 1, "Currently multi_chat_completion only supports n=1 for multi-group conversations."

        if self.model.startswith("gpt") == False:
            # Transform messages if n > 1
            messages_list *= n
            n = 1

        with concurrent.futures.ThreadPoolExecutor() as executor:
            args = [dict(model=self, messages=messages, n=n) for messages in messages_list]
            choices = executor.map(lambda p: p["model"].chat_completion(n=p["n"], messages=p["messages"]), args)

        contents: list[str] = []
        for choice in choices:
            for c in choice:
                # 更健壮地获取 content 字段
                try:
                    content = c.get("message", {}).get("content")
                    if content is not None:
                        contents.append(content)
                    else:
                        # 记录异常内容，避免崩溃
                        contents.append(str(c))
                except Exception as e:
                    # 捕获异常并记录
                    contents.append(f"ERROR: {e}, raw: {str(c)}")
        return contents

