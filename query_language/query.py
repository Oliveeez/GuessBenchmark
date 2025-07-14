import os
import re
import time
import random
from llm_link import ChatModel

model = ChatModel().init_model()
question_dir = "../data_generation_alt/idiom_emoji_questions"
output_file = "llm_idiom_guess_results.txt"
files = [f for f in os.listdir(question_dir) if f.endswith(".txt")]

BATCH_SIZE = 20
MAX_TEST = 50000
test_count = 0

# 读取已问过的成语集合
asked = set()
if os.path.exists(output_file):
    with open(output_file, encoding="utf-8") as f:
        next(f)  # 跳过表头
        for line in f:
            parts = line.strip().split('\t')
            if parts:
                asked.add(parts[0])  # 只存成语

with open(output_file, "a", encoding="utf-8") as fout:
    if os.stat(output_file).st_size == 0:
        fout.write("标准答案\t谜题（emoji）\tLLM输出成语\tLLM是否正确\t成语中有几个谐音\n")
    for fname in files:
        answer = fname.replace(".txt", "")
        if answer in asked:
            continue
        fpath = os.path.join(question_dir, fname)
        with open(fpath, encoding="utf-8") as fin:
            lines = fin.readlines()
        groups = {}
        current_group = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"===\s*(\d+)\s*个谐音", line)
            if m:
                current_group = int(m.group(1))
                groups[current_group] = []
                continue
            if current_group is not None:
                groups[current_group].append(line)
        batch = []
        meta = []
        for group_num, quiz_list in groups.items():
            if group_num not in (0, 1, 2):
                continue  # 跳过3、4个谐音
            selected = random.sample(quiz_list, min(3, len(quiz_list)))
            for quiz in selected:
                if test_count >= MAX_TEST:
                    break
                message = [
                    {"role": "system", "content": "你是一个中国人，擅长猜成语。"},
                    {"role": "user", "content": f"这四个emoji代表了一个四字成语，每个emoji非常严格地对应一个字（可能有谐音），请猜出这个成语：\n{quiz}\n你只能输出一个成语，不能输出其他内容。"}
                ]
                batch.append(message)
                meta.append((quiz, group_num, answer))
                test_count += 1
                if len(batch) == BATCH_SIZE:
                    responses = model.multi_chat_completion(batch, n=1)
                    for (quiz, group, ans), response in zip(meta, responses):
                        idiom = "".join(re.findall(r"[\u4e00-\u9fa5]", response))[:4]
                        correct = "1" if idiom == ans else "0"
                        fout.write(f"{ans}\t{quiz}\t{idiom}\t{correct}\t{group}\n")
                        fout.flush()
                    batch = []
                    meta = []
                    time.sleep(0.5)
            if test_count >= MAX_TEST:
                break
        if batch and test_count <= MAX_TEST:
            responses = model.multi_chat_completion(batch, n=1)
            for (quiz, group, ans), response in zip(meta, responses):
                idiom = "".join(re.findall(r"[\u4e00-\u9fa5]", response))[:4]
                correct = "1" if idiom == ans else "0"
                fout.write(f"{ans}\t{quiz}\t{idiom}\t{correct}\t{group}\n")
                fout.flush()
            time.sleep(0.5)
        asked.add(answer)
        if test_count >= MAX_TEST:
            break