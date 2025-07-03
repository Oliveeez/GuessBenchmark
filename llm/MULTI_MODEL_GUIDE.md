# 多模型图片 LLM API 使用指南

## 🎯 系统特性

现在您的系统支持多种 LLM 模型提供商：

- 🟢 **OpenAI 官方**: GPT-4o, GPT-4 Vision
- 🔵 **阿里云 DashScope**: Qwen-VL-Plus, Qwen-VL-Max
- 🟦 **Azure OpenAI**: GPT-4o, GPT-4 Vision
- 🟣 **Anthropic Claude**: Claude-3.5-Sonnet
- ⚙️ **自定义服务**: 任何兼容 OpenAI API 的服务

## 🚀 快速开始

### 1. 配置模型

编辑 `config.env` 文件：

```env
# 选择要使用的模型提供商
ACTIVE_MODEL_PROVIDER=dashscope  # 可选: openai, dashscope, azure, anthropic, custom

# 配置您要使用的服务
DASHSCOPE_API_KEY=sk-eb2948add8454227a2f7e1be36eb860b
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-vl-plus

# 如果要使用 OpenAI
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### 2. 运行示例

```bash
# 运行多模型示例
python multi_model_example.py

# 或运行项目专用分析器
python guess_benchmark_analyzer.py
```

## 📋 配置说明

### 阿里云 DashScope (推荐)

```env
ACTIVE_MODEL_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-your-dashscope-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-vl-plus  # 或 qwen-vl-max, qwen-vl
```

**模型选择:**
- `qwen-vl`: 基础版，便宜
- `qwen-vl-plus`: 平衡版，推荐 ✅
- `qwen-vl-max`: 高性能版，较贵

### OpenAI 官方

```env
ACTIVE_MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o  # 或 gpt-4-vision-preview
```

### Azure OpenAI

```env
ACTIVE_MODEL_PROVIDER=azure
AZURE_API_KEY=your-azure-key
AZURE_BASE_URL=https://your-resource.openai.azure.com
AZURE_MODEL=gpt-4o
AZURE_API_VERSION=2024-02-15-preview
```

### Anthropic Claude

```env
ACTIVE_MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

## 🔧 使用方法

### 方法一：统一客户端（推荐）

```python
from unified_client import create_client_from_config

# 自动加载配置文件中的设置
client = create_client_from_config()

# 处理单张图片
result = client.send_image_with_prompt("image.jpg", "描述这张图片")

# 批量处理
result = client.batch_process_images("images/", "这是什么？", "results.json")
```

### 方法二：直接使用 API 类

```python
from image_llm_api import ImageLLMAPI

# 创建特定类型的客户端
client = ImageLLMAPI(
    api_key="your-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen-vl-plus",
    api_type="openai_compatible"  # 或 "openai", "azure", "anthropic"
)

result = client.send_image_with_prompt("image.jpg", "描述这张图片")
```

### 方法三：运行时切换模型

```python
from unified_client import create_client_from_config

# 创建客户端
client = create_client_from_config()

# 查看可用提供商
providers = client.list_available_providers()
print(providers)

# 切换到不同的提供商
client.switch_provider("openai")  # 切换到 OpenAI
client.switch_provider("dashscope")  # 切换到阿里云
```

## 🎮 针对您项目的使用

### 1. 分析成语图片

```python
from unified_client import create_client_from_config

client = create_client_from_config()

# 针对成语的优化提示词
prompt = """请仔细观察这张图片，运用中文文化知识分析图片中的元素，猜测它代表的成语。

分析步骤：
1. 图片描述：详细描述图中的物体、人物、动作、场景
2. 文化解读：分析这些元素在中国文化中的象征意义
3. 成语推测：基于文化含义推测最可能的成语

答案格式：
成语：[四字成语]
理由：[简要解释]
信心：[1-5分]"""

result = client.send_image_with_prompt("成语图片.jpg", prompt)
```

### 2. 批量分析项目图片

```python
# 分析所有成语图片
result = client.batch_process_images(
    "../data/chinese_idiom_image/img",
    prompt,
    "idiom_analysis_results.json"
)

# 分析所有 emoji
result = client.batch_process_images(
    "../data/emoji_source",
    "这是什么 emoji？请简洁回答。",
    "emoji_analysis_results.json"
)
```

## 💡 最佳实践

### 1. 模型选择建议

- **开发测试**: 使用阿里云 `qwen-vl-plus`（性价比高）
- **生产环境**: 根据精度要求选择 `qwen-vl-max` 或 OpenAI `gpt-4o`
- **大批量处理**: 使用 `qwen-vl`（便宜）

### 2. 提示词优化

```python
# 针对不同模型优化提示词
if client.get_current_provider() == "dashscope":
    prompt = "请用中文详细分析这张图片..." # 阿里云模型对中文理解更好
elif client.get_current_provider() == "openai":
    prompt = "Analyze this image in detail..." # OpenAI 对英文提示更敏感
```

### 3. 错误处理

```python
result = client.send_image_with_prompt(image_path, prompt)

if result["success"]:
    print(f"✅ 分析成功: {result['response']}")
else:
    print(f"❌ 分析失败: {result['error']}")
    
    # 自动切换到备用模型
    if "rate limit" in result['error'].lower():
        print("尝试切换到备用模型...")
        if client.switch_provider("dashscope"):
            result = client.send_image_with_prompt(image_path, prompt)
```

### 4. 批量处理优化

```python
import time

# 为不同服务设置不同的延迟
delays = {
    "openai": 1.0,      # OpenAI 较严格的速率限制
    "dashscope": 0.5,   # 阿里云相对宽松
    "azure": 0.3,       # Azure 通常配额较高
}

provider = client.get_current_provider()
delay = delays.get(provider, 1.0)

# 在批量处理中添加延迟
for image in images:
    result = client.send_image_with_prompt(image, prompt)
    time.sleep(delay)  # 避免速率限制
```

## 🔍 故障排除

### 常见错误及解决方案

1. **模型不支持错误**
   ```
   错误: Unsupported model `multimodal-embedding-v1`
   解决: 检查 DASHSCOPE_MODEL 设置，应使用 qwen-vl-plus
   ```

2. **认证失败**
   ```
   错误: 401 Unauthorized
   解决: 检查 API Key 是否正确，账户是否有余额
   ```

3. **配置文件问题**
   ```
   错误: 配置文件不存在
   解决: 确保 config.env 文件存在且格式正确
   ```

### 调试命令

```bash
# 测试配置
python model_config_manager.py

# 测试统一客户端
python unified_client.py

# 运行完整示例
python multi_model_example.py
```

## 📞 获取帮助

如果遇到问题，请：

1. 检查配置文件格式是否正确
2. 确认 API Key 和余额状态
3. 查看错误详细信息
4. 尝试切换到其他模型提供商

现在您可以灵活地在不同模型间切换，享受多模型带来的便利！
