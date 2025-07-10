import logging
import re

# for counting token numbers
import tiktoken
from typing import List, Dict

def filter_traceback(s):
    lines = s.split('\n')
    filtered_lines = []
    for i, line in enumerate(lines):
        if line.startswith('Traceback'):
            for j in range(i, len(lines)):
                if "Set the environment variable HYDRA_FULL_ERROR=1" in lines[j]:
                    break
                filtered_lines.append(lines[j])
            return '\n'.join(filtered_lines)
    return ''  # Return an empty string if no Traceback is found

def filter_constraints_error(s):
    lines = s.split('\n')
    filtered_lines = []
    for i, line in enumerate(lines):
        if line.startswith('Constraints Error'):
            for j in range(i, len(lines)):
                filtered_lines.append(lines[j])
            return '\n'.join(filtered_lines)
    return ''  # Return an empty string if no Constraints Error is found

def file_to_string(file_path):
    """
    Read .txt into string
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return ""
    return content

def get_hyperpms_lst(hyperpms: dict) -> str:
    result = ""
    for key, value in hyperpms.items():
        result += f"{key} = {value}\n"
    return result

def get_real_id(exterior_iteration, step):      # step=1: Produced by Crossover; step=2: Produced by Mutation
    if exterior_iteration == 0:
        return "0_Init_"
    else:
        return str(exterior_iteration) + "_" + ("crossover_" if step == 1 else "mutation_")

def add_heubase_to_prompt(prompt, root_dir, problem):
    root_dir = str(root_dir)
    problem = str(problem)
    prompt = prompt + file_to_string(root_dir + "/prompts/common/heubase_common.txt") + file_to_string(root_dir + "/prompts/" + problem + "/heubase.txt")
    return prompt
    
def block_until_running(stdout_filepath, iter_num, id):
    # Ensure that the evaluation has started before moving on
    while True:
        log = file_to_string(stdout_filepath)
        if  len(log) > 0:
            if "Traceback" in log:
                logging.info(f"Interior Iteration {iter_num}: Individual {id} execution error!")
            elif "Constraints Error" in log:
                logging.info(f"Interior Iteration {iter_num}: Individual {id} constraints error!")
            else:
                logging.info(f"Interior Iteration {iter_num}: Individual {id} successful!")
            break

def extract_code_from_response(content):
    """Extract code from the response of the code generator."""
    pattern_code = r'```python(.*?)```'
    code_string = re.search(pattern_code, content, re.DOTALL)
    code_string = code_string.group(1).strip() if code_string is not None else None
    return code_string

def extract_description_from_response(content):
    """Extract everything but the code from content."""
    pattern_code = r'```python.*?```'
    description = re.sub(pattern_code, '', content, flags=re.DOTALL)
    # Strip leading/trailing whitespace and return
    return description.strip()

def extract_numbers_after_func_and_get_max(text):
    matches = re.findall(r'func_(\d+)', text)
    numbers = [int(match) for match in matches]
    return max(numbers) if numbers else 0

def extract_hyperparameters(code):
    try:
        # 使用正则表达式分割文本，兼容带空格和不带空格的标记
        parts = re.split(r'#\s*Hyperparameter\s*#', code)
        if len(parts) < 2:
            logging.info("Input string must contain at least two '#Hyperparameter#' markers.")
            return {}, {}
        
        parameters_text = parts[1].strip()  # 获取两个标记之间的部分
        
        # 使用正则表达式提取参数名、值，并检查类型注释
        pattern = r'(\w+)\s*=\s*([\d.]+)(\s*#\s*(int|float))?'
        matches = re.findall(pattern, parameters_text)
        
        # 存储参数的值和类型
        parameters_dict = {}
        parameters_type = {}
        
        for key, value, _, type_hint in matches:
            if type_hint and type_hint.strip().lower() == "int":
                parameters_dict[key] = int(float(value))  # 先转float再转int，避免字符串直接转int的问题
                parameters_type[key] = 1  # 1 表示 int
            else:
                parameters_dict[key] = float(value)
                parameters_type[key] = 0  # 0 表示 float
        
        return parameters_dict, parameters_type
    
    except Exception as e:
        logging.error(f"An error occurred when extracting hyperparameters: {e}", exc_info=True)
        return {}, {}
    
def remove_hyperparameters(code):
    return re.sub(r'#\s*Hyperparameter\s*#.*?#\s*Hyperparameter\s*#', '', code, flags=re.DOTALL)

# The following function is used to count the number of tokens
def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    计算给定文本的 token 数量，模型默认为 gpt-3.5-turbo。
    如果无法根据 model 获取 encoding，则使用默认 encoding。
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    return len(tokens)

def count_message_tokens(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo") -> int:
    """
    计算 OpenAI Chat API 消息列表的 token 数量。
    如果无法根据 model 获取 encoding，则使用默认 encoding。
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    for message in messages:
        total_tokens += 4  # 假设每条消息有 4 个额外 token（role、分隔符等）
        for key, value in message.items():
            total_tokens += len(encoding.encode(value))
            if key == "name":  # 包含 name 字段时，减少1个 token
                total_tokens -= 1
    total_tokens += 2  # 会话结束时额外 token
    return total_tokens

# Calculate the total number of tokens consumed for incoming messages and outgoing replies
def estimate_total_tokens(input_messages: List[Dict[str, str]], 
                          output_text: str,
                          model: str = "gpt-3.5-turbo") -> int:
    """
    How to use:
        input_messages = [{"role": "user", "content": "Hello!"}]
        output_text = "Hi there!"
        total_tokens = estimate_total_tokens(input_messages, output_text)
    """
    input_token_count = count_message_tokens(input_messages, model)
    output_token_count = count_tokens(output_text, model)
    total = input_token_count + output_token_count
    return total