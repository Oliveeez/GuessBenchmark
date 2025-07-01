import json

def calculate_accuracy(json_file):
    total_cnt = 0
    correct_cnt = 0
    wrong_cnt = 0
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for item in data:
        total_cnt += 1
        if item['gt'] == item['pred']:
            correct_cnt += 1
        else:
            print(f"Incorrect prediction for idiom '{item['gt']}': predicted '{item['pred']}'")
            wrong_cnt += 1
    
    accuracy = (correct_cnt / total_cnt) * 100 if total_cnt > 0 else 0
    
    print(f"Total entries: {total_cnt}")
    print(f"Correct count: {correct_cnt}")
    print(f"Wrong count: {wrong_cnt}")
    print(f"Accuracy: {accuracy:.2f}%")

if __name__ == "__main__":
    json_file_path = "/data/tianyu_data/appendix/GuessBenchmark/experiment/output/idiom_emoji_1_500_by_ds_fixed_by_ds.json"
    calculate_accuracy(json_file_path)