#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git项目文件树生成器
支持自定义深度、过滤规则等功能
"""

import os
import sys
import argparse
from pathlib import Path
import subprocess

class GitTreeGenerator:
    def __init__(self, max_depth=None, show_hidden=False, git_only=False, ignore_patterns=None):
        self.max_depth = max_depth
        self.show_hidden = show_hidden
        self.git_only = git_only
        self.ignore_patterns = ignore_patterns or []
        self.git_root = self._find_git_root()
        
    def _find_git_root(self):
        """查找git项目根目录"""
        try:
            result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], 
                                  capture_output=True, text=True, check=True)
            return Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def _is_git_tracked(self, path):
        """检查文件是否被git跟踪"""
        if not self.git_root:
            return True
        try:
            # 检查文件是否被git跟踪
            result = subprocess.run(['git', 'ls-files', str(path)], 
                                  capture_output=True, text=True, cwd=self.git_root)
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    
    def _should_ignore(self, path):
        """检查是否应该忽略此路径"""
        name = path.name
        
        # 隐藏文件检查
        if not self.show_hidden and name.startswith('.') and name not in ['.gitignore', '.gitkeep']:
            return True
        
        # 自定义忽略模式
        for pattern in self.ignore_patterns:
            if pattern in name:
                return True
        
        # 常见的应该忽略的目录和文件
        common_ignores = {
            '__pycache__', '.pyc', 'node_modules', '.DS_Store', 
            '.vscode', '.idea', '*.log', '.pytest_cache', 'dist', 'build'
        }
        
        for ignore in common_ignores:
            if ignore.startswith('*') and name.endswith(ignore[1:]):
                return True
            elif ignore == name:
                return True
        
        return False
    
    def _get_tree_symbols(self, is_last, depth):
        """获取树状结构的符号"""
        if depth == 0:
            return ""
        
        prefix = "    " * (depth - 1)
        if is_last:
            return prefix + "└── "
        else:
            return prefix + "├── "
    
    def generate_tree(self, root_path=None, current_depth=0):
        """生成文件树"""
        if root_path is None:
            root_path = Path('.')
        
        root_path = Path(root_path).resolve()
        
        # 打印根目录
        if current_depth == 0:
            print(f"📁 {root_path.name}/")
            if self.git_root:
                print(f"   (Git项目根目录: {self.git_root})")
            print()
        
        if self.max_depth is not None and current_depth >= self.max_depth:
            return
        
        try:
            # 获取所有子项目
            items = []
            for path in root_path.iterdir():
                if self._should_ignore(path):
                    continue
                
                if self.git_only and not self._is_git_tracked(path):
                    continue
                
                items.append(path)
            
            # 排序：目录在前，文件在后，同类型按名称排序
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            
            # 打印树状结构
            for i, path in enumerate(items):
                is_last = (i == len(items) - 1)
                symbol = self._get_tree_symbols(is_last, current_depth + 1)
                
                if path.is_dir():
                    print(f"{symbol}📁 {path.name}/")
                    # 递归打印子目录
                    self.generate_tree(path, current_depth + 1)
                else:
                    # 根据文件扩展名选择图标
                    icon = self._get_file_icon(path.suffix)
                    print(f"{symbol}{icon} {path.name}")
        
        except PermissionError:
            print(f"⚠️  权限不足，无法访问: {root_path}")
    
    def _get_file_icon(self, extension):
        """根据文件扩展名返回合适的图标"""
        icons = {
            '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
            '.json': '📋', '.md': '📖', '.txt': '📄', '.yml': '⚙️',
            '.yaml': '⚙️', '.xml': '📰', '.csv': '📊', '.pdf': '📕',
            '.jpg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.svg': '🎨',
            '.mp4': '🎬', '.mp3': '🎵', '.zip': '📦', '.tar': '📦',
            '.gz': '📦', '.exe': '⚙️', '.dll': '🔧', '.so': '🔧',
            '.gitignore': '🚫', '.dockerfile': '🐳', '.sh': '📜',
            '.bat': '📜', '.ps1': '📜'
        }
        return icons.get(extension.lower(), '📄')

def main():
    parser = argparse.ArgumentParser(description='生成Git项目的可视化文件树')
    parser.add_argument('-d', '--depth', type=int, help='最大显示深度')
    parser.add_argument('-a', '--all', action='store_true', help='显示隐藏文件')
    parser.add_argument('-g', '--git-only', action='store_true', help='只显示Git跟踪的文件')
    parser.add_argument('-i', '--ignore', nargs='*', help='要忽略的文件/目录模式')
    parser.add_argument('path', nargs='?', default='.', help='要扫描的路径（默认为当前目录）')
    
    args = parser.parse_args()
    
    generator = GitTreeGenerator(
        max_depth=args.depth,
        show_hidden=args.all,
        git_only=args.git_only,
        ignore_patterns=args.ignore or []
    )
    
    try:
        generator.generate_tree(args.path)
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()