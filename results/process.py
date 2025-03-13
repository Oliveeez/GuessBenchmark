import json
from collections import OrderedDict
import os

def update_json_file(input_json_path, output_json_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    new_data = []
    gt_data = []
    for item in data:
        old_name = item["image_name"]
        if old_name.startswith("c_idiom_") and old_name.endswith(".jpg"):
            number = old_name.split("_")[-1].split(".")[0]
            new_name = f"c_idiom_img_{number}.jpeg"
            print(new_name)
            item["image_name"] = new_name
        new_data.append(item)
        
        gt_item = {
            "image_name": item["image_name"],
            "gt": item["gt"]
        }
        gt_data.append(gt_item)
    
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(gt_data, f, ensure_ascii=False, indent=4)
    
    print(f"new json file saved to: {output_json_path}")

    with open("/gemini/code/results/chinese_gpt_4o_res2.json", 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)



if __name__ == "__main__":
    input_json_path = "/gemini/code/GuessBenchmark/results/e_proverb_emoji_gpt_4o_res.json"  
    output_json_path = "/gemini/code/GuessBenchmark/results/e_proverb_emoji_gpt_4o_res.json"  

    with open(input_json_path, 'r', encoding='utf-8') as file:
        data = json.load(file, object_pairs_hook=OrderedDict)
    for item in data:
        if 'proverb' in item:
            item['pred'] = item.pop('proverb')
        
        new_item = OrderedDict()
        new_item['image_name'] = item['image_name']
        new_item['gt'] = item['gt']
        new_item['pred'] = item['pred']
        new_item['inference chain'] = item['inference chain']
        
        item.clear()
        item.update(new_item)
    

    with open(output_json_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

