#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import sys
import os

def filter_data(input_file, output_file):
    """
    过滤JSON数据，只保留每个对象中emoji_rep数组里index为1的元素
    
    Args:
        input_file (str): 输入JSON文件路径
        output_file (str): 输出JSON文件路径
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        
        # 读取输入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证数据格式
        if not isinstance(data, list):
            raise ValueError("输入JSON文件应该包含一个数组")
        
        # 过滤数据
        filtered_data = []
        for i, item in enumerate(data):
            try:
                # 检查必要的字段
                if not all(key in item for key in ['idiom_index', 'idiom', 'emoji_rep']):
                    print(f"警告: 第{i+1}个对象缺少必要字段，跳过处理")
                    continue
                
                # 找到index为1的emoji_rep
                filtered_emoji_rep = [rep for rep in item['emoji_rep'] if rep.get('index') == 1]
                
                # 如果没有找到index为1的元素，跳过或给出警告
                if not filtered_emoji_rep:
                    print(f"警告: 第{i+1}个对象(idiom: {item.get('idiom', 'unknown')})没有index为1的emoji_rep")
                
                # 构造新的对象
                filtered_item = {
                    "idiom_index": item['idiom_index'],
                    "idiom": item['idiom'],
                    "emoji_rep": filtered_emoji_rep
                }
                filtered_data.append(filtered_item)
                
            except Exception as e:
                print(f"处理第{i+1}个对象时出错: {e}")
                continue
        
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 写入输出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=4)
        
        print(f"成功处理 {len(filtered_data)} 个对象")
        print(f"过滤后的数据已保存到: {output_file}")
        
    except FileNotFoundError as e:
        print(f"文件错误: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        sys.exit(1)

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(
        description='过滤JSON数据，只保留每个对象中emoji_rep数组里index为1的元素',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python data_filter.py --input input.json --output output.json
        """
    )
    
    parser.add_argument(
        '--input', 
        required=True, 
        help='输入JSON文件路径'
    )
    parser.add_argument(
        '--output', 
        required=True, 
        help='输出JSON文件路径'
    )
    
    args = parser.parse_args()
    
    # 执行过滤操作
    filter_data(args.input, args.output)

if __name__ == "__main__":
    main()