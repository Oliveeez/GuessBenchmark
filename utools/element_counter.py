#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os
from typing import Any, Union

def analyze_json_file(file_path: str) -> None:
    try:
        if not os.path.exists(file_path):
            print(f"错误: 文件 '{file_path}' 不存在")
            return
        
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        print(f"分析文件对象数量: {len(data)}")
        
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
    except Exception as e:
        print(f"发生错误: {e}")

def main():
    for file_path in sys.argv[1:]:
        analyze_json_file(file_path)

if __name__ == "__main__":
    main()