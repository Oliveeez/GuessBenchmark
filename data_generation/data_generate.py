import re
import json
from openai import OpenAI

from dotenv import load_dotenv
import os

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("DS_API_KEY"), base_url=os.getenv("DS_URL"))

# File paths
# input_file = "./pop_parted_idioms_origin/idioms_1_500.json"  
# compliant_output_file = "./pop_idioms_emoji_pair/idiom_emoji_1_500_by_ds.json"  
# error_output_file = "./pop_idioms_emoji_pair/idiom_emoji_1_500_by_ds_error.json" 
 
# input_file = "/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_merged.json"  
# compliant_output_file = "./pop_idioms_emoji_pair/idiom_emoji_merged_by_ds.json"  
# error_output_file = "./pop_idioms_emoji_pair/idiom_emoji_merged_by_ds_error.json" 

input_file = "/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_parted_idioms_origin/pop_idioms_merged.json"  
compliant_output_file = "./idiom_emoji_merged_by_ds.json"  
error_output_file = "./idiom_emoji_merged_by_ds_error.json" 


# Regular expression pattern to extract JSON from response
json_pattern = re.compile(r'```json\s*({.*?})\s*```', re.DOTALL)

def process_response(idiom, response_content):
    """Process the API response and save to appropriate file based on content."""
    # Try to extract JSON from the response
    json_match = json_pattern.search(response_content)

    if json_match:
        try:
            # Parse the JSON to validate it
            response_json = json.loads(json_match.group(1))
            if "emoji_rep" in response_json and "inference_chain" in response_json:
                # Create new JSON with idiom as first element
                compliant_data = {
                    "idiom": idiom,
                    "emoji_rep": response_json["emoji_rep"],
                    "inference_chain": response_json["inference_chain"]
                }
                # Valid format found
                # with open(compliant_output_file, 'a', encoding='utf-8') as f:
                #     json.dump(compliant_data, f, ensure_ascii=False)
                #     f.write('\n') 
                return True, compliant_data
        except json.JSONDecodeError:
            pass
    
    # If we get here, either no JSON found or invalid format
    fail_data = {
        "idiom": idiom,
        "response": response_content
    }

    return False, fail_data

def main():
    # Read idioms from file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)  
            data = data[:5]
            print(f"===Total idioms to process: {len(data)}===")
            idioms = [item['word'] for item in data if 'word' in item]  
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: File '{input_file}' is not a valid JSON file.")
        return
    except KeyError:
        print(f"Error: Some entries in '{input_file}' are missing the 'word' field.")
        return
    
    success_data_list = []
    fail_data_list = []
    
    
    # Process each idiom with progress tracking
    for index, idiom in enumerate(idioms, start=1):
        try:
            # Print progress
            print(f"Processing idiom {index}/{len(idioms)}: {idiom}", end=" - ")
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "你是一个擅长将中文成语转化为emoji表情符号的智能助手。请根据以下要求生成结果："
                            "【核心规则】1. 每个成语必须生成由4个表情符号组成的序列 2. 每个表情必须严格对应成语中的汉字顺序 3. 表情选择需满足以下任一条件："
                            "▶ 含义匹配：表情象征意义与对应汉字含义相符 ▶ 发音匹配：表情中文读音（拼音）与汉字发音相同/高度相似"
                            "【关键要求】1. 每个字符单独选择其中一种匹配规则 2. 必须同时输出最终结果和推理过程 3. 输出严格遵循JSON格式且不带任何额外文本"
                            "示例格式：{\"emoji_rep\": \"1️⃣❤️1️⃣👔\", \"inference_chain\": \"成语'一心一意'生成逻辑：1.1️⃣(一)...\"}"
                            "【输出规范】请确保：✓ 表情数量严格对应四字成语 ✓ 优先选择直观易懂的表情符号 ✓ 发音匹配需标注对应拼音 ✓ 推理过程需分步骤说明每个字符的选择依据"
                        )
                    },
                    {
                        "role": "user", 
                        "content": f"请生成成语 ['{idiom}'] 的emoji表情符号组"
                    },
                ],
                stream=False
            )           
            # Process the response
            
            response_content = response.choices[0].message.content
            print(f"Response content: {response_content}")
            success, generate_data = process_response(idiom, response_content)
            print(f"Success: {success}")
            
            # Flush writes to ensure data is saved
            if success:
                success_data_list.append(generate_data)
            else:
                fail_data_list.append(generate_data)

        except Exception as e:
            print(f"Error: {str(e)}")
            # Save the error case
            fail_data = {
                "idiom": idiom,
                "response": f"Error: {str(e)}"
            }
            fail_data_list.append(generate_data)

    with open(compliant_output_file, 'w', encoding='utf-8') as f:    
        json.dump(success_data_list, f, ensure_ascii=False, indent=4,  ) 

    with open(error_output_file, 'w', encoding='utf-8') as f:    
        json.dump(fail_data_list, f, ensure_ascii=False, indent=4,  ) 

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. All completed items have been saved.")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        print("All completed items have been saved.")