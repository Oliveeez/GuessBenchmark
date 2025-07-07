#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_idiom_txt_to_json.py

Convert all txt files in idiom_emoji_questions to unified JSON format.
Read    # 检查输入目录
    if not input_dir.exists():
        print(f"❌ 目录不存在: {input_dir.absolute()}")
        returnt files and creates a single JSON file with idiom-emoji pairs.
"""

import json
import os
import re
import random
from pathlib import Path
from typing import List, Dict, Tuple

def parse_txt_file(file_path: Path) -> List[Dict[str, any]]:
    """
    解析单个 txt 文件，提取成语和表情符号对
    
    Args:
        file_path: txt 文件路径，文件名是成语，内容是表情符号
        
    Returns:
        成语-表情符号对的列表，包含谐音数量信息
    """
    idiom_emoji_pairs = []
    
    try:
        # 从文件名提取成语（去掉.txt扩展名）
        idiom = file_path.stem
        
        # 验证成语格式（4个中文字符）
        if not is_valid_idiom(idiom):
            print(f"  ⚠️  文件名不是有效的四字成语: {idiom}")
            return []
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 按行分割内容
        lines = content.strip().split('\n')
        
        current_homophonic_count = 0  # 当前的谐音数量
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是谐音分组标题行
            if '===' in line and '个谐音' in line:
                # 提取谐音数量
                import re
                match = re.search(r'(\d+)\s*个谐音', line)
                if match:
                    current_homophonic_count = int(match.group(1))
                continue
            
            # 跳过其他标题行
            if '===' in line:
                continue
            
            # 提取表情符号：移除所有中文字符、数字、等号等
            emoji_rep = extract_emojis_from_line(line)
            
            if emoji_rep:  # 只添加有效的表情符号
                idiom_emoji_pairs.append({
                    "idiom": idiom,
                    "emoji_rep": emoji_rep,
                    "homophonic_count": current_homophonic_count
                })
    
    except Exception as e:
        print(f"❌ 解析文件 {file_path} 时出错: {e}")
    
    return idiom_emoji_pairs

def extract_emojis_from_line(line: str) -> str:
    """
    从单行内容中提取表情符号，忽略中文字符、数字、等号等
    
    Args:
        line: 单行内容
        
    Returns:
        提取出的表情符号字符串
    """
    # 移除所有中文字符
    content_no_chinese = re.sub(r'[\u4e00-\u9fff]', '', line)
    
    # 移除数字、等号、标点符号和空白字符
    content_cleaned = re.sub(r'[0-9=，。！？：；、\s\n\r\t]', '', content_no_chinese)
    
    # 进一步清理：只保留表情符号范围的Unicode字符
    emoji_chars = []
    for char in content_cleaned:
        code = ord(char)
        # 保留表情符号和相关Unicode范围，但排除数字和等号
        if (0x1F600 <= code <= 0x1F64F or  # 表情
            0x1F300 <= code <= 0x1F5FF or  # 杂项符号
            0x1F680 <= code <= 0x1F6FF or  # 交通符号
            0x1F1E6 <= code <= 0x1F1FF or  # 区域指示符
            0x2600 <= code <= 0x26FF or   # 杂项符号
            0x2700 <= code <= 0x27BF or   # 装饰符号
            0x1F900 <= code <= 0x1F9FF or  # 补充符号
            0x1FA70 <= code <= 0x1FAFF or  # 扩展A
            0xFE00 <= code <= 0xFE0F or   # 变体选择器
            0x20E3 == code):               # 组合键盘符号（但不包含数字本身）
            emoji_chars.append(char)
    
    return ''.join(emoji_chars)

def count_emojis(emoji_text: str) -> int:
    """
    计算字符串中表情符号的数量
    
    Args:
        emoji_text: 包含表情符号的字符串
        
    Returns:
        表情符号的数量
    """
    emoji_count = 0
    i = 0
    while i < len(emoji_text):
        char = emoji_text[i]
        code = ord(char)
        
        # 检查是否是表情符号
        if (0x1F600 <= code <= 0x1F64F or  # 表情
            0x1F300 <= code <= 0x1F5FF or  # 杂项符号
            0x1F680 <= code <= 0x1F6FF or  # 交通符号
            0x1F1E6 <= code <= 0x1F1FF or  # 区域指示符
            0x2600 <= code <= 0x26FF or   # 杂项符号
            0x2700 <= code <= 0x27BF or   # 装饰符号
            0x1F900 <= code <= 0x1F9FF or  # 补充符号
            0x1FA70 <= code <= 0x1FAFF):  # 扩展A
            emoji_count += 1
            
            # 跳过可能的修饰符
            if i + 1 < len(emoji_text):
                next_code = ord(emoji_text[i + 1])
                if 0xFE00 <= next_code <= 0xFE0F:  # 变体选择器
                    i += 1
        i += 1
    
    return emoji_count

def is_valid_idiom(text: str) -> bool:
    """检查是否是有效的四字成语"""
    if not text:
        return False
    
    # 移除所有非中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_text = ''.join(chinese_chars)
    
    # 检查是否恰好是四个中文字符
    return len(chinese_text) == 4 and chinese_text == text

def convert_all_txt_to_json():
    """
    转换所有 txt 文件为统一的 JSON 格式
    """
    print("🚀 开始转换 idiom_emoji_questions 中的所有 txt 文件...")
    
    # 设置路径 - 直接指定项目根目录
    project_root = Path("C:/Users/weiyi/Desktop/GuessBenchmark")
    input_dir = project_root / "data_generation_alt" / "idiom_emoji_questions"
    output_dir = project_root / "data_generation"
    output_file = output_dir / "chinese_idiom_complete.json"
    
    print(f"📁 项目根目录: {project_root.absolute()}")
    print(f"📂 输入目录: {input_dir.absolute()}")
    print(f"📂 输出目录: {output_dir.absolute()}")
    
    # 检查输入目录
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        return
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 收集所有 txt 文件
    txt_files = list(input_dir.glob("*.txt"))
    
    if not txt_files:
        print(f"❌ 在 {input_dir} 中没有找到 txt 文件")
        return
    
    print(f"📁 找到 {len(txt_files)} 个 txt 文件")
    
    # 解析所有文件并按成语分组
    idiom_dict = {}
    idiom_index = 1
    
    for txt_file in txt_files:
        print(f"📖 处理文件: {txt_file.name}")
        
        pairs = parse_txt_file(txt_file)
        
        if pairs:
            # 先过滤出恰好包含4个表情符号的组合
            valid_pairs = [pair for pair in pairs if count_emojis(pair['emoji_rep']) == 4]
            
            if not valid_pairs:
                print(f"  ❌ 没有找到包含4个表情符号的组合: {txt_file.name}")
                continue
            
            # 按谐音数量排序，优先选择谐音数量少的
            valid_pairs.sort(key=lambda x: x['homophonic_count'])
            
            # 按谐音数量分组
            homophonic_groups = {}
            for pair in valid_pairs:
                count = pair['homophonic_count']
                if count not in homophonic_groups:
                    homophonic_groups[count] = []
                homophonic_groups[count].append(pair)
            
            # 按谐音数量从少到多，每种取一个，直到补齐5个
            selected_pairs = []
            sorted_counts = sorted(homophonic_groups.keys())
            
            # 第一轮：每种谐音数量取一个
            for count in sorted_counts:
                if len(selected_pairs) >= 5:
                    break
                group = homophonic_groups[count]
                # 从每组随机选一个
                selected_pairs.append(random.choice(group))
            
            # 如果还没有5个，继续从最少谐音数量的组中补充
            while len(selected_pairs) < 5:
                for count in sorted_counts:
                    if len(selected_pairs) >= 5:
                        break
                    group = homophonic_groups[count]
                    # 排除已选择的项目
                    available = [pair for pair in group if pair not in selected_pairs]
                    if available:
                        selected_pairs.append(random.choice(available))
                    
                # 如果所有组都用完了，退出循环
                if all(len([pair for pair in homophonic_groups[count] if pair not in selected_pairs]) == 0 
                       for count in sorted_counts):
                    break
            
            print(f"  🎯 从 {len(valid_pairs)} 个有效表情组合中按谐音数量梯度选择 {len(selected_pairs)} 个")
            
            # 获取成语名称
            idiom_name = selected_pairs[0]['idiom']
            
            # 创建成语对象结构
            idiom_entry = {
                "idiom_index": idiom_index,
                "idiom": idiom_name,
                "emoji_rep": []
            }
            
            # 添加表情组合
            for idx, pair in enumerate(selected_pairs, 1):
                # 验证表情符号数量
                emoji_count = count_emojis(pair['emoji_rep'])
                # 使用实际的谐音数量
                homophonic_count = pair['homophonic_count']
                
                emoji_entry = {
                    "index": idx,
                    "emoji_set": pair['emoji_rep'],
                    "homophonic_num": homophonic_count
                }
                idiom_entry["emoji_rep"].append(emoji_entry)
                print(f"  ✅ {idiom_name}: {pair['emoji_rep']} (谐音数:{homophonic_count}, 表情数:{emoji_count})")
            
            idiom_dict[idiom_name] = idiom_entry
            idiom_index += 1
        else:
            print(f"  ❌ 解析失败: {txt_file.name}")
    
    # 按成语排序并转换为列表
    sorted_idioms = sorted(idiom_dict.keys())
    final_result = []
    
    # 重新分配索引
    for idx, idiom_name in enumerate(sorted_idioms, 1):
        idiom_entry = idiom_dict[idiom_name]
        idiom_entry["idiom_index"] = idx
        final_result.append(idiom_entry)
    
    # 保存为 JSON
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=4)
        
        print(f"\n✅ 转换完成!")
        print(f"📊 总共转换了 {len(final_result)} 个成语")
        print(f"💾 输出文件: {output_file}")
        
        # 显示前几个示例
        if final_result:
            print(f"\n📋 前3个示例:")
            for i, entry in enumerate(final_result[:3]):
                print(f"  {i+1}. {entry['idiom']} (共{len(entry['emoji_rep'])}个表情组合)")
                for emoji_rep in entry['emoji_rep']:
                    print(f"     - {emoji_rep['emoji_set']}")
        
    except Exception as e:
        print(f"❌ 保存 JSON 文件时出错: {e}")

def preview_txt_files():
    """
    预览 txt 文件内容，帮助理解文件格式
    """
    project_root = Path("C:/Users/weiyi/Desktop/GuessBenchmark")
    input_dir = project_root / "data_generation_alt" / "idiom_emoji_questions"
    
    print(f"📁 项目根目录: {project_root.absolute()}")
    print(f"📂 输入目录: {input_dir.absolute()}")
    
    if not input_dir.exists():
        print(f"❌ 目录不存在: {input_dir.absolute()}")
        return
    
    txt_files = list(input_dir.glob("*.txt"))[:3]  # 预览前3个文件
    
    for txt_file in txt_files:
        print(f"\n📖 预览文件: {txt_file.name}")
        print(f"   成语: {txt_file.stem}")
        print("=" * 50)
        
        try:
            pairs = parse_txt_file(txt_file)
            print(f"找到 {len(pairs)} 个表情符号组合:")
            
            # 按谐音数量分组显示
            homophonic_groups = {}
            for pair in pairs[:10]:  # 只显示前10个
                count = pair['homophonic_count']
                if count not in homophonic_groups:
                    homophonic_groups[count] = []
                homophonic_groups[count].append(pair)
            
            # 按谐音数量排序显示
            for count in sorted(homophonic_groups.keys()):
                group = homophonic_groups[count]
                print(f"  {count}个谐音:")
                for i, pair in enumerate(group[:3]):  # 每组最多显示3个
                    print(f"    - {pair['emoji_rep']}")
            
            if len(pairs) > 10:
                print(f"  ... 还有 {len(pairs) - 10} 个")
                    
        except Exception as e:
            print(f"  ❌ 读取失败: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert idiom txt files to JSON format")
    parser.add_argument("--preview", action="store_true", help="Preview txt files content")
    parser.add_argument("--convert", action="store_true", help="Convert all txt files to JSON")
    
    args = parser.parse_args()
    
    if args.preview:
        preview_txt_files()
    elif args.convert:
        convert_all_txt_to_json()
    else:
        print("🔍 使用 --preview 预览文件内容")
        print("🔄 使用 --convert 开始转换")
        print("\n示例:")
        print("  python convert_idiom_txt_to_json.py --preview")
        print("  python convert_idiom_txt_to_json.py --convert")