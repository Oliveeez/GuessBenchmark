# from openai import OpenAI

# client = OpenAI(
#     api_key="sk-LwyvquF9WxkHAtHXF0UpEYPD7t3CQq1ApWOoK8ETTxBr84gj",
#     base_url="http://123.129.219.111:3000/v1"
# )

# response = client.chat.completions.create(
#     model="claude-4-sonnet",  # 在这里切换模型
#     messages=[
#         {"role": "user", "content": "你好"}
#     ]
# )

# print(response.choices[0].message.content)

import requests

url = "http://123.129.219.111:3000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-LwyvquF9WxkHAtHXF0UpEYPD7t3CQq1ApWOoK8ETTxBr84gj"
}

data = {
    "model": "gpt-4o",  
    "messages": [
        {
            "role": "user",
            "content": "你好"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())