import os
import re
import time
import random
from llm_link import ChatModel

def load_idioms(file_path):
    """读取成语列表，返回(成语, 拼音)的列表"""
    idioms_with_pinyin = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                # 提取成语和拼音
                parts = line.split('\t')
                if len(parts) >= 2:
                    idiom = parts[0].strip()
                    pinyin = parts[1].strip()
                    if len(idiom) == 4:  # 确保是四字成语
                        idioms_with_pinyin.append((idiom, pinyin))
    return idioms_with_pinyin

def filter_idioms_by_llm(idioms_with_pinyin, target_count=4000, batch_size=20):
    """使用LLM筛选成语"""
    model = ChatModel().init_model()
    
    # 输出文件
    output_file = "selected_idioms.txt"
    rejected_file = "rejected_idioms.txt"
    final_file = "idiom_table_new.txt"
    
    # 创建成语到拼音的映射
    idiom_to_pinyin = {item[0]: item[1] for item in idioms_with_pinyin}
    idioms = [item[0] for item in idioms_with_pinyin]
    
    # 读取已处理的成语（如果存在）
    processed = set()
    selected = []
    rejected = []
    
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                idiom = line.strip()
                if idiom:
                    selected.append(idiom)
                    processed.add(idiom)
    
    if os.path.exists(rejected_file):
        with open(rejected_file, 'r', encoding='utf-8') as f:
            for line in f:
                idiom = line.strip()
                if idiom:
                    rejected.append(idiom)
                    processed.add(idiom)
    
    print(f"已选择: {len(selected)}个，已拒绝: {len(rejected)}个")
    
    # 随机打乱成语顺序，避免按拼音排序的偏差
    random.shuffle(idioms)
    
    # 筛选未处理的成语
    unprocessed = [idiom for idiom in idioms if idiom not in processed]
    print(f"待处理: {len(unprocessed)}个成语")
    
    with open(output_file, 'a', encoding='utf-8') as f_selected, \
         open(rejected_file, 'a', encoding='utf-8') as f_rejected:
        
        for i in range(0, len(unprocessed), batch_size):
            # 如果已选够4000个就停止
            if len(selected) >= target_count:
                break
                
            batch = unprocessed[i:i+batch_size]
            
            # 构造prompt
            idiom_list = "、".join(batch)
            prompt = f"""请从以下成语中筛选出中学生都应该知道的常用成语。

筛选标准：
1. 中学生普遍熟悉和了解的成语
2. 在日常生活、学习、考试中经常出现的成语
3. 意思清晰、用法常见的成语
4. 排除过于生僻、古老或很少使用的成语
5. 排除那些不太像成语的词组

成语列表：{idiom_list}

请直接返回符合条件的成语，每个成语一行，不要添加其他解释或说明。如果某个成语不符合标准，就不要包含在结果中。"""

            try:
                message = [
                    {"role": "system", "content": "你是一位经验丰富的中学语文老师，熟悉中学生的语文水平和常用成语。"},
                    {"role": "user", "content": prompt}
                ]
                
                response = model.multi_chat_completion([message], n=1)[0]
                
                # 解析返回结果
                returned_idioms = []
                for line in response.split('\n'):
                    line = line.strip()
                    # 提取四字成语
                    clean_idiom = ''.join(re.findall(r'[\u4e00-\u9fa5]', line))
                    if len(clean_idiom) == 4 and clean_idiom in batch:
                        returned_idioms.append(clean_idiom)
                
                # 分类处理结果
                for idiom in batch:
                    if idiom in returned_idioms:
                        selected.append(idiom)
                        f_selected.write(f"{idiom}\n")
                        f_selected.flush()
                    else:
                        rejected.append(idiom)
                        f_rejected.write(f"{idiom}\n")
                        f_rejected.flush()
                
                print(f"批次 {i//batch_size + 1}: 处理了{len(batch)}个，选中{len(returned_idioms)}个，总计选中{len(selected)}个")
                
                # 防止请求过快
                time.sleep(1)
                
            except Exception as e:
                print(f"处理批次出错: {e}")
                # 出错时，暂时跳过这批，记录为rejected
                for idiom in batch:
                    rejected.append(idiom)
                    f_rejected.write(f"{idiom}\n")
                    f_rejected.flush()
                time.sleep(5)
    
    print(f"\n筛选完成！")
    print(f"最终选中: {len(selected)}个成语")
    print(f"拒绝: {len(rejected)}个成语")
    
    # 写入最终文件，保持原格式
    if len(selected) >= target_count:
        final_selected = random.sample(selected, target_count)
    else:
        final_selected = selected
    
    with open(final_file, 'w', encoding='utf-8') as f:
        for idiom in final_selected:
            pinyin = idiom_to_pinyin.get(idiom, "")
            f.write(f"{idiom}\t{pinyin}\n")
    
    print(f"已保存{len(final_selected)}个成语到 {final_file}")
    return selected

def main():
    print("开始筛选中学生常用成语...")
    
    # 读取成语和拼音
    idioms_with_pinyin = load_idioms("idiom_table.txt")
    print(f"总共读取到 {len(idioms_with_pinyin)} 个成语")
    
    # 使用LLM筛选
    selected_idioms = filter_idioms_by_llm(idioms_with_pinyin, target_count=4000, batch_size=20)
    
    print("筛选完成！")

if __name__ == "__main__":
    main()