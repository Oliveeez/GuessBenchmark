import subprocess
import tempfile
import re

def extract_emoji(s):
    # 匹配第一个 emoji（宽松匹配，支持多 codepoint，遇到汉字/字母/空格就停）
    m = re.match(r'^([\W_]+?)([一-龥]|[a-zA-Z0-9]|\s|$)', s)
    return m.group(1) if m else s

def query_emojis_by_pinyin(pinyin):
    # 1. 写 query_data.in
    with open('query_data.in', 'w', encoding='utf-8') as f:
        f.write('1\n')
        f.write(f'find {pinyin}\n')

    # 2. 调用 ./bpt（不传stdin参数）
    result = subprocess.run(['./bpt'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore')
    output = result.stdout.strip().splitlines()

    # 3. 解析输出
    res = []
    for line in output:
        parts = line.strip().split()
        if len(parts) >= 3:
            emoji = parts[0]
            hanzi = parts[-2]
            try:
                idx = int(parts[-1])
                res.append((emoji, hanzi, idx))
            except Exception:
                continue
    return res

import os
os.makedirs('idiom_emoji_questions', exist_ok=True)

# 读取idiom_table.txt里的成语和拼音
idioms = []
with open('idiom_table.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) == 2 and len(parts[0]) == 4:
            idioms.append({'word': parts[0], 'pinyin': parts[1]})

idioms = idioms[:1000]
from itertools import islice, product

MAX_PER_GROUP = 1000

def get_same_emoji(emoji_list, char):
    # 返回本字本emoji列表
    return [e for e in emoji_list if e[1] == char]

def get_diff_emoji(emoji_list, char):
    # 返回谐音emoji列表
    return [e for e in emoji_list if e[1] != char]

for idiom in idioms:
    word = idiom['word']
    pinyins = idiom['pinyin'].split()
    emoji_lists = []
    for i, (char, py) in enumerate(zip(word, pinyins)):
        emoji_hanzi_list = query_emojis_by_pinyin(py)
        emoji_lists.append(emoji_hanzi_list)

    groups = [[] for _ in range(5)]

    # 0个谐音（全本字本emoji）
    base = []
    for i in range(4):
        same = get_same_emoji(emoji_lists[i], word[i])
        if not same:
            break
        base.append(same)
    if len(base) == 4:
        for combo in islice(product(*base), MAX_PER_GROUP):
            groups[0].append(combo)

    # 1~4个谐音
    from itertools import combinations
    for n in range(1, 5):
        idx_combs = list(combinations(range(4), n))
        for idxs in idx_combs:
            # idxs为要用谐音的位置，其余用本字本emoji
            lists = []
            valid = True
            for i in range(4):
                if i in idxs:
                    diff = get_diff_emoji(emoji_lists[i], word[i])
                    if not diff:
                        valid = False
                        break
                    lists.append(diff)
                else:
                    same = get_same_emoji(emoji_lists[i], word[i])
                    if not same:
                        valid = False
                        break
                    lists.append(same)
            if not valid:
                continue
            for combo in islice(product(*lists), MAX_PER_GROUP // len(idx_combs)):
                groups[n].append(combo)
                if len(groups[n]) >= MAX_PER_GROUP:
                    break
            if len(groups[n]) >= MAX_PER_GROUP:
                break

    # 写文件
    with open(f'idiom_emoji_questions/{word}.txt', 'w', encoding='utf-8') as f:
        for i, group in enumerate(groups):
            f.write(f'=== {i} 个谐音 ===\n')
            for combo in group:
                f.write(''.join(extract_emoji(eh[0]) for eh in combo) + '\n')
            f.write('\n')

