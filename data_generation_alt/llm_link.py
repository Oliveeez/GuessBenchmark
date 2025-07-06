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
        model: str = "deepseek-chat",
        temperature: float = 0.5,   # medium-high diversity and medium-high quality
        base_url: Optional[str] = "https://api.deepseek.com/beta/v1",
        api_key: Optional[str] = "sk-dd46dd1afb364d83a1b463cd69efd690",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key          # TODO: here add an 'or' to employ our API.
        self.base_url = base_url
        self.client = None

    def init_model(self):
        if self.model.startswith("o1"):
            from utils.llm_client.openai import OpenAIClient
            self.client = OpenAIClient(api_key="sk-FD1ABCC4BFBB4BEC9164BEB171C5BE82", base_url="http://10.119.11.146:3000/v1")
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
                contents.append(c["message"]["content"])
        return contents
    
def get_dataset(emoji: str, response: str, file_path: str = "emoji_hanzi.txt"):
    text = ''.join(response)
    chars = re.findall(r'\d+\.\s*([\u4e00-\u9fa5])', text)
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(emoji + ' ' + ' '.join(chars) + '\n')
    
if __name__ == "__main__":
    model = ChatModel().init_model()
    all_emojis = list(emoji.EMOJI_DATA.keys())
    message_lst = []
    cnt = 0
    for _, e in enumerate(all_emojis):
        message = [
            {"role": "system", "content": "你是一个中国人，懂汉字。"},
            {"role": "user", "content": f"{e}请根据这个emoji联想**一个汉字**，可以通过1.本身意思2.联想意思，给5个可能性，请保证更直观的在前面，太牵强的不输出。**重要**：你只能按照以下格式输出：1.（一个汉字）\n2.（一个汉字）\n...，且除此之外**不能输出任何其它内容**。"}
        ]
        message_lst.append(message)
        if _ % 20 == 19:
            response = model.multi_chat_completion(messages_list=message_lst, n=1)
            for i, r in enumerate(response):
                get_dataset(all_emojis[i + _ - 19], r)
            message_lst = []
        