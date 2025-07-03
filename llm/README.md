# 图片 LLM API 使用指南

这个模块提供了一个简单易用的接口，用于将图片和文本提示发送给大语言模型进行分析。

## 功能特性

- 🖼️ 支持多种图片格式（JPG, PNG, GIF, BMP, WebP）
- 🔄 自动图片大小调整，优化 API 传输
- 🔧 支持多种 LLM API（OpenAI, Anthropic 等）
- 📦 批量处理图片文件夹
- 💾 结果自动保存为 JSON 格式
- ⚙️ 灵活的配置选项

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

复制 `config.env.example` 为 `config.env` 并填入您的 API 密钥：

```bash
copy config.env.example config.env
```

编辑 `config.env` 文件：
```
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### 3. 运行示例

```bash
python example_usage.py
```

## 使用方法

### 基本用法

```python
from image_llm_api import ImageLLMAPI
import os

# 创建 API 客户端
client = ImageLLMAPI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1",
    model="gpt-4o"
)

# 处理单张图片
result = client.send_image_with_prompt(
    image_path="path/to/image.jpg",
    prompt="请描述这张图片的内容"
)

if result["success"]:
    print(f"LLM 回答: {result['response']}")
else:
    print(f"错误: {result['error']}")
```

### 批量处理

```python
# 批量处理文件夹中的所有图片
result = client.batch_process_images(
    image_folder="path/to/images",
    prompt="这是什么？",
    output_file="results.json"
)
```

### 高级配置

```python
# 自定义参数
result = client.send_image_with_prompt(
    image_path="image.jpg",
    prompt="详细分析这张图片",
    max_tokens=2000,        # 最大生成长度
    temperature=0.3         # 生成随机性
)
```

## API 参数说明

### ImageLLMAPI 类

- `api_key`: API 密钥
- `base_url`: API 基础 URL
- `model`: 使用的模型名称

### send_image_with_prompt 方法

- `image_path`: 图片文件路径
- `prompt`: 文本提示
- `max_tokens`: 最大生成 token 数（默认 1000）
- `temperature`: 生成温度（默认 0.7）

### batch_process_images 方法

- `image_folder`: 图片文件夹路径
- `prompt`: 文本提示
- `output_file`: 结果输出文件（可选）

## 支持的 LLM 服务

### OpenAI
```python
client = ImageLLMAPI(
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    model="gpt-4o"
)
```

### Azure OpenAI
```python
client = ImageLLMAPI(
    api_key="your-azure-key",
    base_url="https://your-resource.openai.azure.com/openai/deployments/your-deployment",
    model="gpt-4"
)
```

### 其他兼容 OpenAI API 的服务
```python
client = ImageLLMAPI(
    api_key="your-key",
    base_url="https://your-custom-api.com/v1",
    model="your-model"
)
```

## 错误处理

API 调用返回的结果包含 `success` 字段：

```python
result = client.send_image_with_prompt(image_path, prompt)

if result["success"]:
    # 成功
    response = result["response"]
    usage = result["usage"]
    model = result["model"]
else:
    # 失败
    error = result["error"]
    details = result.get("details", "")
```

## 注意事项

1. **图片大小**: 系统会自动调整过大的图片以优化传输
2. **API 限制**: 注意您的 API 服务的速率限制和使用配额
3. **网络超时**: 默认请求超时为 60 秒
4. **图片格式**: 支持 JPG, PNG, GIF, BMP, WebP 格式
5. **临时文件**: 调整大小后的临时文件会自动清理

## 项目集成示例

针对您的 GuessBenchmark 项目，可以这样使用：

```python
# 分析成语图片
result = client.send_image_with_prompt(
    image_path="../data/chinese_idiom_image/img/一败涂地.jpg",
    prompt="请猜测这张图片代表的中文成语，并解释原因。"
)

# 分析 emoji 图片
result = client.batch_process_images(
    image_folder="../data/emoji_source",
    prompt="这是什么 emoji 表情？请简洁回答。",
    output_file="emoji_analysis.json"
)
```

## 故障排除

### 常见问题

1. **导入错误**: 确保已安装所有依赖包
2. **API 密钥错误**: 检查 `.env` 文件中的密钥是否正确
3. **网络连接问题**: 检查网络连接和 API 服务可用性
4. **图片格式不支持**: 确保图片格式在支持列表中

### 调试模式

如需调试，可以在代码中添加详细的错误信息输出：

```python
result = client.send_image_with_prompt(image_path, prompt)
if not result["success"]:
    print(f"错误类型: {result['error']}")
    if 'details' in result:
        print(f"详细信息: {result['details']}")
```
