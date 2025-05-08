import json

def read_jsonl_file(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  
                data.append(json.loads(line))
    return data

# input_files = [
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_by_ds.json',
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_by_ds_2.json',
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_by_ds_3.json'
# ]
# input_files = [
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/unpop_idioms_by_ds.json',
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/unpop_idioms_by_ds_2.json',
#     '/data/tianyu_data/appendix/GuessBenchmark/data_generation/unpop_idioms_by_ds_3.json'
# ]

# merged_data = []
# counts = []

# for file in input_files:
#     file_data = read_jsonl_file(file)
#     counts.append(len(file_data))
#     merged_data.extend(file_data)


# output_file = '/data/tianyu_data/appendix/GuessBenchmark/data_generation/unpop_idioms_merged.json'
# with open(output_file, 'w', encoding='utf-8') as f:
#     json.dump(merged_data, f, ensure_ascii=False, indent=2)


# for i, file in enumerate(input_files):
#     print(f"{file} 对象个数：{counts[i]}")

output_file = '/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_merged.json'
with open(output_file, 'r') as file:
    data = json.load(file)

print(f"\n合并后的JSON文件对象个数：{len(data)}")