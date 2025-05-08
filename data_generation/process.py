import re
import random
import json

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("DS_API_KEY"), base_url=os.getenv("DS_URL"))

def count_json_objects(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        return len(data)
    elif isinstance(data, dict):
        return 1  
    else:
        return 0  
    
def filter_idioms_randomly(input_file, output_file, sample_size=3000):
    with open(input_file, 'r', encoding='utf-8') as f:
        idioms = json.load(f)
    
    four_char_idioms = [
        item for item in idioms 
        if isinstance(item.get('word'), str) 
        and len(item['word']) == 4 
        and re.fullmatch(r'[\u4e00-\u9fa5]{4}', item['word'])
    ]
    
    print(f"Number of four_char_idioms: {len(four_char_idioms)}")
    
    sample_size = min(sample_size, len(four_char_idioms))
    
    random.seed(42) 
    sampled_idioms = random.sample(four_char_idioms, sample_size)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sampled_idioms, f, ensure_ascii=False, indent=2)
    
    print(f"Randomly chose {sample_size} idioms in {output_file}")
    
def process_response(idiom, response_content):
    """Process the API response"""
    response = response_content.strip().lower()
    if response == "yes":
        return True
    elif response == "no":
        return False
    else:
        invalid_data = {
            "idiom": idiom,
            "response": response_content 
        }
        with open("./invalid_responses_pop_by_ds.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(invalid_data, ensure_ascii=False) + "\n")
            
        return None

def filter_idioms_by_popularity(input_file):
    error_output_file = "./error_responses_pop_by_ds_3.json"
    pop_idiom_file = "./pop_idioms_by_ds_3.json"
    unpop_idiom_file = "./unpop_idioms_by_ds_3.json"

    popular_count = 0
    unpopular_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        idioms = json.load(f)
    kk = 8641+4802+19929
    idioms = idioms[kk:]
    four_char_idioms = [
        item for item in idioms 
        if isinstance(item.get('word'), str) 
        and len(item['word']) == 4 
        and re.fullmatch(r'[\u4e00-\u9fa5]{4}', item['word'])
    ]
    
    print(f"Number of four_char_idioms: {len(four_char_idioms)}")
    
    # ds selecting the idioms based on popularity
    for index, item in enumerate(four_char_idioms, start=1):
        try:
            # Print progress
            idiom = item['word']
            print(f"Processing idiom {index}/{len(four_char_idioms)}: {idiom}", end=" - ")
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "你是一个中文成语常用性分类器，严格根据以下标准判断用户提供的成语是否为现代汉语中的常用成语："
                            "1. 被权威词典收录；2. 高频出现在教材/媒体；3. 日常交流广泛使用。 "
                            "仅回答小写英文单词'yes'或'no'，禁止任何额外解释、标点或格式。"
                        )
                    },
                    {
                        "role": "user", 
                        "content": f"'{idiom}'"
                    },
                ],
                stream=False
            )
            
            # Process the response
            response_content = response.choices[0].message.content
            pop_flag = process_response(idiom, response_content)
            print(f"pop_flag: {pop_flag}")
            
            if pop_flag is not None:
                if pop_flag:
                    with open(pop_idiom_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    popular_count += 1 
                else:
                    with open(unpop_idiom_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    unpopular_count += 1
            
        except Exception as e:
            print(f"Error: {str(e)}")
            # Save the error case
            fail_data = {
                "idiom": idiom,
                "response": f"Error: {str(e)}"
            }
            with open(error_output_file, 'a', encoding='utf-8') as f:
                json.dump(fail_data, f, ensure_ascii=False)
                f.write('\n')
                f.flush()

    print(f"Popular idioms: {popular_count} | Unpopular idioms: {unpopular_count}")


import json

def fix_json_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_json = '[' + ','.join(line.strip() for line in lines) + ']'
    
    try:
        data = json.loads(fixed_json)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        return
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"JSON saved at: {output_file}")



if __name__ == '__main__':
    # input_file = '/data/tianyu_data/appendix/GuessBenchmark/experiment/output/idiom_emoji_1_500_by_ds_fixed_by_ds.json' 
    # output_file = '/data/tianyu_data/appendix/GuessBenchmark/experiment/output/idiom_emoji_1_500_by_ds_fixed_by_ds_2.json'  
    # fix_json_file(input_file, output_file)

    file_path = './idiom.json'  
    object_count = count_json_objects(file_path)
    print(f"[{object_count}] objects in {file_path}")

    filter_idioms_by_popularity(file_path)

    # input_json = './idiom.json'  
    # output_json = './sampled_3000_idioms.json'  
    # filter_idioms(input_json, output_json, 3000)

    