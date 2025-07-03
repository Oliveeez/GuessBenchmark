import json
import unicodedata

def remove_tone(pinyin):
    # 去除拼音音调
    return ''.join([c for c in unicodedata.normalize('NFD', pinyin) if not unicodedata.combining(c)])

# 1. 读取idiom.json，筛选四字成语
idioms = []
with open('idiom.json', encoding='utf-8') as f:
    for line in f:
        line = line.strip().rstrip(',')
        if not line:
            continue
        try:
            obj = json.loads(line)
            word = obj.get('word', '')
            if len(word) == 4:
                pinyin = obj.get('pinyin', '')
                # 只保留字母和空格
                pinyin_no_tone = ' '.join([remove_tone(s) for s in pinyin.split()])
                idioms.append({'word': word, 'pinyin': pinyin_no_tone})
        except Exception as e:
            print(f"跳过异常行: {line[:30]}... 错误: {e}")

# 2. 生成成语表
with open('idiom_table.txt', 'w', encoding='utf-8') as f:
    for item in idioms:
        f.write(f"{item['word']}\t{item['pinyin']}\n")