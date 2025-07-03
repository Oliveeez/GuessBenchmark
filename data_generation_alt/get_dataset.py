import json
from pypinyin import lazy_pinyin
import os

data = []
with open("emoji_hanzi.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        emoji = parts[0]
        hanzi = parts[1:]
        pinyin = [lazy_pinyin(h)[0] if h else "" for h in hanzi]
        index = list(range(1, len(hanzi) + 1))
        data.append({
            "emoji": emoji,
            "hanzi": hanzi,
            "pinyin": pinyin,
            "index": index
        })

with open("emoji_hanzi.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 生成100个insert_data_id_x.in文件，每行格式为：insert 拼音 emoji 汉字 index
with open("emoji_hanzi.json", encoding="utf-8") as f:
    data = json.load(f)

lines = []
for entry in data:
    emoji = entry["emoji"]
    hanzi_list = entry["hanzi"]
    pinyin_list = entry["pinyin"]
    index_list = entry["index"]
    for h, p, idx in zip(hanzi_list, pinyin_list, index_list):
        lines.append(f"insert {p} {emoji} {h} {idx}")

total_files = 1
per_file = (len(lines) + total_files - 1) // total_files

os.makedirs("insert_data_id", exist_ok=True)
for i in range(total_files):
    chunk = lines[i*per_file : (i+1)*per_file]
    with open(f"insert_data_id/insert_data_id.in", "w", encoding="utf-8") as f:
        f.write("\n".join(chunk) + ("\n" if chunk else ""))