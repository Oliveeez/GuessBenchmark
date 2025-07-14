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
    基于emoji_hanzi.txt文件中实际emoji的范围检测
    """
    result = ""
    i = 0
    
    while i < len(line):
        char = line[i]
        code_point = ord(char)
        
        # 基于实际emoji文件的完整范围
        is_emoji = (
            # 主要emoji范围
            0x1F600 <= code_point <= 0x1F64F or  # 表情符号 😀-🙏
            0x1F300 <= code_point <= 0x1F5FF or  # 杂项符号和象形文字 🌀-🗿
            0x1F680 <= code_point <= 0x1F6FF or  # 交通和地图符号 🚀-🛿
            0x1F700 <= code_point <= 0x1F77F or  # 炼金术符号
            0x1F780 <= code_point <= 0x1F7FF or  # 几何形状扩展
            0x1F800 <= code_point <= 0x1F8FF or  # 补充箭头-C
            0x1F900 <= code_point <= 0x1F9FF or  # 补充符号和象形文字 🤀-🧿
            0x1FA00 <= code_point <= 0x1FA6F or  # 棋类符号
            0x1FA70 <= code_point <= 0x1FAFF or  # 符号和象形文字扩展-A 🩰-🫿
            0x1FB00 <= code_point <= 0x1FBFF or  # 符号和象形文字扩展-B
            
            # 传统符号范围 (包含很多重要emoji)
            0x2600 <= code_point <= 0x26FF or    # 杂项符号 ☀-⛿ (包含⌨️, ♈-♓, ⚛, ⚗, ⛑等)
            0x2700 <= code_point <= 0x27BF or    # 装饰符号 ✀-➿
            
            # 特定重要符号
            0x2B50 <= code_point <= 0x2B55 or    # ⭐⭕
            0x3030 == code_point or              # 〰️
            0x303D == code_point or              # 〽️  
            0x3297 == code_point or              # ㊗️
            0x3299 == code_point or              # ㊙️
            
            # 箭头和几何图形
            0x2190 <= code_point <= 0x21FF or    # 箭头 ←→↑↓等
            0x25A0 <= code_point <= 0x25FF or    # 几何图形 ■□▲▼等
            0x2B00 <= code_point <= 0x2BFF or    # 杂项符号和箭头
            
            # 播放控制和技术符号
            0x23E9 <= code_point <= 0x23F3 or    # ⏩⏪⏫⏬⏭⏮⏯⏰⏱⏲⏳
            0x23CF == code_point or              # ⏏️
            0x2328 == code_point or              # ⌨️
            
            # 星号和数学符号
            0x2733 == code_point or              # ✳️
            0x2734 == code_point or              # ✴️
            0x274C == code_point or              # ❌
            0x274E == code_point or              # ❎
            0x2753 <= code_point <= 0x2755 or    # ❓❔❕
            0x2757 == code_point or              # ❗
            0x2795 <= code_point <= 0x2797 or    # ➕➖➗
            
            # 心形和感叹号
            0x2763 == code_point or              # ❣️
            0x2764 == code_point or              # ❤️
            0x27A1 == code_point or              # ➡️
            0x27B0 == code_point or              # ➰
            0x27BF == code_point or              # ➿
            
            # 版权等符号
            0x00A9 == code_point or              # ©️
            0x00AE == code_point or              # ®️
            0x203C == code_point or              # ‼️
            0x2049 == code_point or              # ⁉️
            0x2122 == code_point or              # ™️
            0x2139 == code_point or              # ℹ️
            
            # 宗教和文化符号
            0x262E == code_point or              # ☮️
            0x262F == code_point or              # ☯️ 
            0x2638 == code_point or              # ☸️
            0x2694 == code_point or              # ⚔️
            0x269B == code_point or              # ⚛️
            0x26D4 == code_point or              # ⛔
            0x271D == code_point or              # ✝️
            0x2721 == code_point or              # ✡️
            0x262A == code_point or              # ☪️
            
            # 区域指示符号 (国旗)
            0x1F1E6 <= code_point <= 0x1F1FF or  # 🇦-🇿
            
            # 数字和字母 (用于组合emoji)
            0x30 <= code_point <= 0x39 or        # 数字 0-9
            0x41 <= code_point <= 0x5A or        # 大写字母 A-Z
            0x61 <= code_point <= 0x7A or        # 小写字母 a-z
            0x23 == code_point or                 # # (用于 #️⃣)
            0x2A == code_point or                 # * (用于 *️⃣)
            
            # emoji修饰符和组合字符
            0xFE00 <= code_point <= 0xFE0F or    # 变体选择器
            code_point == 0x20E3 or              # 组合键盘符号 ⃣
            0x1F3FB <= code_point <= 0x1F3FF or  # 肤色修饰符 🏻🏼🏽🏾🏿
            code_point == 0x200D or              # 零宽连接符 (用于组合emoji)
            
            # 其他重要符号
            0x231A <= code_point <= 0x231B or    # ⌚⌛
            0x24C2 == code_point or              # Ⓜ️
            0x1F004 == code_point or             # 🀄 (麻将)
            0x1F0CF == code_point                # 🃏 (小丑牌)
        )
        
        if is_emoji:
            result += char
        
        i += 1
    
    return result

def count_emojis(emoji_text: str) -> int:
    """
    更准确的emoji计数，基于实际emoji特征
    """
    if not emoji_text:
        return 0
    
    count = 0
    i = 0
    
    while i < len(emoji_text):
        char = emoji_text[i]
        code_point = ord(char)
        
        # 检查是否是主要emoji字符（非修饰符）
        is_main_emoji = (
            # 主要emoji范围
            0x1F600 <= code_point <= 0x1F64F or  # 表情
            0x1F300 <= code_point <= 0x1F5FF or  # 杂项符号
            0x1F680 <= code_point <= 0x1F6FF or  # 交通
            0x1F700 <= code_point <= 0x1F77F or  # 炼金术
            0x1F780 <= code_point <= 0x1F7FF or  # 几何
            0x1F800 <= code_point <= 0x1F8FF or  # 箭头
            0x1F900 <= code_point <= 0x1F9FF or  # 补充符号
            0x1FA00 <= code_point <= 0x1FA6F or  # 棋类
            0x1FA70 <= code_point <= 0x1FAFF or  # 扩展A
            
            # 传统符号
            0x2600 <= code_point <= 0x26FF or    # 杂项符号
            0x2700 <= code_point <= 0x27BF or    # 装饰符号
            
            # 特定重要符号
            0x2B50 <= code_point <= 0x2B55 or    # ⭐⭕
            code_point == 0x3030 or              # 〰️
            code_point == 0x303D or              # 〽️
            code_point == 0x3297 or              # ㊗️
            code_point == 0x3299 or              # ㊙️
            
            # 箭头
            0x2190 <= code_point <= 0x21FF or    # 基本箭头
            0x2B00 <= code_point <= 0x2BFF or    # 补充箭头
            
            # 几何图形
            0x25A0 <= code_point <= 0x25FF or    # 基本几何
            
            # 播放控制
            0x23E9 <= code_point <= 0x23F3 or    # 播放按钮
            code_point == 0x23CF or              # ⏏️
            code_point == 0x2328 or              # ⌨️
            
            # 数字组合 (如1️⃣)
            (0x30 <= code_point <= 0x39) or      # 0-9
            code_point == 0x23 or                # #
            code_point == 0x2A or                # *
            
            # 区域指示符
            0x1F1E6 <= code_point <= 0x1F1FF or  # 🇦-🇿
            
            # 其他重要单个emoji
            code_point == 0x00A9 or              # ©️
            code_point == 0x00AE or              # ®️
            code_point == 0x203C or              # ‼️
            code_point == 0x2049 or              # ⁉️
            code_point == 0x2122 or              # ™️
            code_point == 0x2139 or              # ℹ️
            code_point == 0x231A or              # ⌚
            code_point == 0x231B or              # ⌛
            code_point == 0x24C2 or              # Ⓜ️
            code_point == 0x1F004 or             # 🀄
            code_point == 0x1F0CF                # 🃏
        )
        
        if is_main_emoji:
            count += 1
            
            # 跳过后续的修饰符
            j = i + 1
            while j < len(emoji_text):
                next_code = ord(emoji_text[j])
                if (0xFE00 <= next_code <= 0xFE0F or  # 变体选择器
                    next_code == 0x20E3 or            # ⃣
                    0x1F3FB <= next_code <= 0x1F3FF or # 肤色修饰符
                    next_code == 0x200D):             # 零宽连接符
                    j += 1
                else:
                    break
            i = j
        else:
            i += 1
    
    return count

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
    project_root = Path("C:\\Users\\weiyi\\Documents\\GuessBenchmark")
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
                # 从每组选第一个有效的（包含4个表情符号的）
                valid_in_group = [pair for pair in group if count_emojis(pair['emoji_rep']) == 4]
                if valid_in_group:
                    selected_pairs.append(valid_in_group[0])

            # 如果还没有5个，继续从最少谐音数量的组中补充
            while len(selected_pairs) < 5:
                added_any = False
                for count in sorted_counts:
                    if len(selected_pairs) >= 5:
                        break
                    group = homophonic_groups[count]
                    # 排除已选择的项目，并确保有4个表情符号
                    available = [pair for pair in group 
                               if pair not in selected_pairs and count_emojis(pair['emoji_rep']) == 4]
                    if available:
                        selected_pairs.append(available[0])
                        added_any = True
                
                # 如果这一轮没有添加任何项目，退出循环
                if not added_any:
                    break
            
            # 如果选择的组合数量不足，跳过这个成语
            if len(selected_pairs) == 0:
                print(f"  ❌ 未能选择到有效的表情组合: {txt_file.name}")
                continue
            
            print(f"  🎯 从 {len(valid_pairs)} 个有效表情组合中按谐音数量梯度选择 {len(selected_pairs)} 个")
            
            # 获取成语名称
            idiom_name = selected_pairs[0]['idiom']
            
            # 创建成语对象结构
            idiom_entry = {
                "idiom_index": idiom_index,
                "idiom": idiom_name,
                "emoji_rep": []
            }
            
            # 添加表情组合 - 重新编号索引
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
                # print(f"  ✅ {idiom_name}: {pair['emoji_rep']} (谐音数:{homophonic_count}, 表情数:{emoji_count})")
            
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

def safe_emoji_processing(text):
    """安全的emoji处理"""
    # 保持原始字符，不进行任何标准化
    return text

# 完整的转换流程
def txt_to_json_with_emoji(txt_file, json_file):
    try:
        # 使用utf-8-sig处理BOM
        with open(txt_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        # 不对emoji进行任何处理
        data = {"content": content}
        
        # 确保输出时不转义unicode
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error: {e}")

# 使用示例
txt_to_json_with_emoji('input.txt', 'output.json')

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