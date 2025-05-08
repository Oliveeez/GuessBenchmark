from transformers import AutoModelForCausalLM, AutoTokenizer

# 指定本地模型路径
model_path = "/data/tianyu_data/appendix/models/llama3.3_70b_instruct"

# 加载模型和分词器
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",  # 自动分配 GPU/CPU 资源
    torch_dtype="auto",  # 自动选择数据类型
    trust_remote_code=True
)

# 定义提示模板
prompt = """[INST] <<SYS>>
你是一个有帮助的AI助手
<</SYS>>

请用中文解释量子计算的基本概念。[/INST]"""

# 编码输入
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

# 生成配置
generate_kwargs = {
    "max_new_tokens": 512,
    "temperature": 0.7,
    "top_p": 0.9,
    "do_sample": True,
    "pad_token_id": tokenizer.eos_token_id
}

# 生成文本
outputs = model.generate(**inputs, **generate_kwargs)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)

print("模型回复：\n", response.split("[/INST]")[-1].strip())
print("模型回复：\n", response)