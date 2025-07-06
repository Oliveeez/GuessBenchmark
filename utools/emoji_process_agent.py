#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emoji_process_agent.py

Emoji Processing Agent: Fetch emoji SVG vector graphics from multiple CDN sources 
and support conversion to PNG images with specified dimensions.
Supports automatic SVG content repair and multiple conversion methods.
"""

import argparse
import requests

import sys
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List, Dict

import regex
import cairosvg


class EmojiProcessAgent:
    """Emoji Processing Agent Class"""
    
    # Special emoji codepoint mappings
    SPECIAL_MAPPINGS = {}
    
    # CDN source configurations
    CDN_SOURCES = [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/{codepoints}.svg",
        "https://twemoji.maxcdn.com/v/latest/svg/{codepoints}.svg",
        "https://raw.githubusercontent.com/twitter/twemoji/master/assets/svg/{codepoints}.svg",
        "https://unpkg.com/twemoji@latest/assets/svg/{codepoints}.svg"
    ]
    
    # HTTP request headers
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    def __init__(self, verbose: bool = False):
        """
        Initialize Emoji Processing Agent
        
        Args:
            verbose: Whether to display detailed information
        """
        self.verbose = verbose
        
    def log(self, message: str, level: str = "INFO"):
        """Log output with level-based filtering"""
        if self.verbose or level in ["ERROR", "SUCCESS"]:
            prefix = {"INFO": "ℹ️", "ERROR": "❌", "SUCCESS": "✅", "WARNING": "⚠️"}
            print(f"{prefix.get(level, '')} {message}")

    def parse_emoji_sequence(self, emoji_str: str) -> List[str]:
        """
        通过 Unicode Grapheme Cluster 拆分，再挑出真正的 Emoji 序列
        
        Args:
            emoji_str: 包含多个 emoji 的字符串
            
        Returns:
            拆分后的单个 emoji 列表
        """
        emojis = []
        # \X 是 regex 中的「Unicode 拓展 grapheme cluster」
        clusters = regex.findall(r'\X', emoji_str)
        
        print(f"🔍 Parsing emoji sequence: {repr(emoji_str)}")
        for cluster in clusters:
            cps = [f"U+{ord(c):04X}" for c in cluster]
            print(f"  Cluster: {repr(cluster)} -> codepoints: {cps}")
            
            # 如果这个 cluster 里至少有一个字符具有 Emoji 属性，就当它是一个 emoji
            if any(regex.match(r'\p{Emoji}', ch) for ch in cluster):
                emojis.append(cluster)
                print(f"  ✅ Added: {repr(cluster)}")
            else:
                print(f"  ❌ Skipped: {repr(cluster)}")
        
        print(f"🎯 Final result: {emojis} (count: {len(emojis)})")
        return emojis

    # def emoji_to_codepoints_from_parsed_set(self, parsed_emojis: List[str]) -> List[str]:
    #     """
    #     Get the output of parse_emoji_sequence , retuen the codepoint list of parsed_emojis list
        
    #     Args:
    #         parsed_emojis: List of single-emoji strings, e.g. ['1️⃣','⛰️','🧀','🦡']
        
    #     Returns:
    #         List of codepoint strings, e.g. ['31-20e3','26f0','1f9c0','1f9a1']
    #     """
    #     codepoint_list: List[str] = []
    #     for emj in parsed_emojis:
    #         cp_str = self.emoji_to_codepoints(emj)
    #         codepoint_list.append(cp_str)
    #     return codepoint_list

    def emoji_to_codepoints(self, emoji) -> str:
        """
        Convert emoji to codepoint string
        
        Args:
            emoji: Either emoji character string (like '1️⃣') or 
                list of Unicode codepoints (like ['U+0031', 'U+FE0F', 'U+20E3'])
                
        Returns:
            Codepoint string like '31-fe0f-20e3'
        """
        # Check special mappings first (only for string input)
        if isinstance(emoji, str) and hasattr(self, 'SPECIAL_MAPPINGS') and emoji in self.SPECIAL_MAPPINGS:
            return self.SPECIAL_MAPPINGS[emoji]
        
        try:
            codepoints = []
            
            # Handle list input (like ['U+0031', 'U+FE0F', 'U+20E3'])
            if isinstance(emoji, list):
                for code_str in emoji:
                    if isinstance(code_str, str):
                        # Remove 'U+' prefix if present
                        if code_str.startswith('U+'):
                            code_str = code_str[2:]
                        # Convert hex string to int
                        code_int = int(code_str, 16)
                        
                        # Skip variation selector FE0F for Twemoji compatibility
                        if code_int == 0xFE0F:
                            continue
                            
                        codepoints.append(f"{code_int:x}")
                    else:
                        # If it's already an int, skip FE0F
                        if code_str == 0xFE0F:
                            continue
                        codepoints.append(f"{code_str:x}")
            
            # Handle string input (like '1️⃣')
            elif isinstance(emoji, str):
                i = 0
                while i < len(emoji):
                    char = emoji[i]
                    code = ord(char)
                    
                    # Handle surrogate pairs first
                    if 0xD800 <= code <= 0xDBFF and i + 1 < len(emoji):
                        high, low = code, ord(emoji[i + 1])
                        if 0xDC00 <= low <= 0xDFFF:
                            full_code = 0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00)
                            codepoints.append(f"{full_code:x}")
                            i += 2
                            continue
                    
                    # Skip variation selector FE0F for Twemoji compatibility
                    if code == 0xFE0F:
                        i += 1
                        continue
                    
                    # Keep all non-ASCII characters and special Unicode characters
                    if code > 0x7F:
                        codepoints.append(f"{code:x}")
                    # Also keep ASCII digits for number emojis
                    elif 0x30 <= code <= 0x39:  # ASCII digits 0-9
                        codepoints.append(f"{code:x}")
                    
                    i += 1
            else:
                raise ValueError(f"Unsupported input type: {type(emoji)}")
            
            result = '-'.join(codepoints)
            return result
            
        except Exception as e:
            if hasattr(self, 'log'):
                self.log(f"Error parsing emoji codepoints: {e}", "WARNING")
            
            # Fallback handling
            if isinstance(emoji, str):
                return '-'.join(f"{ord(ch):x}" for ch in emoji if ord(ch) > 0x7F)
            elif isinstance(emoji, list):
                fallback_codes = []
                for item in emoji:
                    if isinstance(item, str) and item.startswith('U+'):
                        fallback_codes.append(item[2:].lower())
                    else:
                        fallback_codes.append(str(item).lower())
                return '-'.join(fallback_codes)
            else:
                return ""
    
    def validate_emoji(self, emoji: str) -> bool:
        """Validate if input is a valid emoji"""
        if not emoji:
            return False
        
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF\U00002600-\U000026FF\U00002700-\U000027BF"
            "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
            "\U00003030\U0000203C\U00002049\U000020E3\U0000FE0F\U0000200D]+",
            flags=re.UNICODE
        )
        return bool(emoji_pattern.search(emoji))
    
    def fetch_svg(self, emoji: str) -> Tuple[bytes, str]:
        """
        Fetch SVG from multiple CDN sources
        
        Args:
            emoji: Emoji character
            
        Returns:
            (svg_data, source_name)
        """
        codepoints = self.emoji_to_codepoints(emoji)
        
        
        # Generate all possible sources
        all_sources = []
        base_variants = [codepoints]
        
        # Generate all variants for each CDN source
        for variant in base_variants:
            for i, template in enumerate(self.CDN_SOURCES):
                source_name = ["JsDelivr", "MaxCDN", "GitHub", "Unpkg"][i]
                if variant != codepoints:
                    source_name += f" ({variant})"
                all_sources.append({
                    "name": source_name,
                    "url": template.format(codepoints=variant)
                })
        
        # Try to fetch
        for source in all_sources:
            try:
                self.log(f"Trying to fetch from {source['name']}...")
                
                resp = requests.get(source["url"], timeout=10, headers=self.DEFAULT_HEADERS)
                resp.raise_for_status()
                content = resp.content
                
                # Validate content
                if not self._validate_svg_content(content, source['name']):
                    continue
                
                self.log(f"Successfully fetched SVG from {source['name']} ({len(content)} bytes)", "SUCCESS")
                return content, source["name"]
                
            except requests.RequestException as e:
                self.log(f"{source['name']} request failed: {e}", "ERROR")
            except Exception as e:
                self.log(f"{source['name']} unknown error: {e}", "ERROR")
        
        raise RuntimeError(f"Unable to fetch SVG for emoji '{emoji}' from any source")
    
    def _validate_svg_content(self, content: bytes, source_name: str) -> bool:
        """Validate SVG content validity"""
        if len(content) == 0:
            self.log(f"{source_name} returned empty content", "ERROR")
            return False
        
        content_str = content.decode('utf-8', errors='ignore').lower()
        if content_str.startswith(('<!doctype html', '<html')):
            self.log(f"{source_name} returned HTML page instead of SVG", "ERROR")
            return False
        
        if b'<svg' not in content:
            self.log(f"{source_name} returned content without SVG tags", "ERROR")
            return False
        
        if len(content) < 100 or len(content) > 1024 * 1024:
            self.log(f"{source_name} returned content with abnormal size ({len(content)} bytes)", "ERROR")
            return False
        
        return True
    
    def fix_svg_content(self, svg_data: bytes) -> bytes:
        """Fix common issues in SVG content"""
        try:
            svg_str = svg_data.decode('utf-8', errors='replace')
            
            # Apply fix rules
            fixes = [
                ('\x00', ''), ('\x08', ''), ('\x0b', ''), ('\x0c', ''), ('\x0e', ''), ('\x0f', ''),
                ('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                ('viewBox=', ' viewBox='), ('xmlns=', ' xmlns='),
                ('<svg', '\n<svg'), ('</svg>', '</svg>\n'),
            ]
            
            for old, new in fixes:
                svg_str = svg_str.replace(old, new)
            
            # Ensure XML declaration and namespace
            if not svg_str.strip().startswith('<?xml') and '<svg' in svg_str:
                svg_start = svg_str.find('<svg')
                svg_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_str[svg_start:]
            
            if 'xmlns="http://www.w3.org/2000/svg"' not in svg_str:
                svg_str = svg_str.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            
            # Remove comments and CDATA
            svg_str = re.sub(r'<!--.*?-->', '', svg_str, flags=re.DOTALL)
            svg_str = re.sub(r'<!\[CDATA\[.*?\]\]>', '', svg_str, flags=re.DOTALL)
            
            return svg_str.encode('utf-8')
            
        except Exception as e:
            self.log(f"SVG content fix failed: {e}", "WARNING")
            return svg_data
    
    def validate_svg_xml(self, svg_data: bytes) -> Tuple[bool, str]:
        """Validate SVG XML format"""
        try:
            svg_str = svg_data.decode('utf-8', errors='replace')
            ET.fromstring(svg_str)
            
            if '<svg' not in svg_str.lower():
                return False, "Does not contain SVG tags"
            
            return True, "SVG content is valid"
            
        except ET.ParseError as e:
            return False, f"XML parsing error: {e}"
        except Exception as e:
            return False, f"Validation failed: {e}"
    
    def save_svg(self, svg_data: bytes, output_path: str) -> bool:
        """Save SVG file"""
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(svg_data)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.log(f"SVG saved to {output_path}", "SUCCESS")
                return True
            else:
                self.log(f"SVG file creation failed: {output_path}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error saving SVG: {e}", "ERROR")
            return False
    
    def convert_to_png(self, svg_data: bytes, size: int, output_path: str) -> bool:
        """
        Convert SVG to PNG
        
        Args:
            svg_data: SVG data
            size: Output size
            output_path: Output path
            
        Returns:
            Whether conversion was successful
        """
        # Validate and fix SVG content
        is_valid, error_msg = self.validate_svg_xml(svg_data)
        if not is_valid:
            self.log(f"SVG content validation failed: {error_msg}", "WARNING")
            self.log("Attempting to fix SVG content...")
            
            fixed_svg_data = self.fix_svg_content(svg_data)
            is_valid, error_msg = self.validate_svg_xml(fixed_svg_data)
            
            if is_valid:
                self.log("SVG content fixed successfully", "SUCCESS")
                svg_data = fixed_svg_data
            else:
                self.log(f"SVG fix failed: {error_msg}", "ERROR")
                return False
        
        # Try multiple conversion methods
        methods = [
            ("CairoSVG", self._convert_with_cairosvg),
        ]
        
        for method_name, method_func in methods:
            self.log(f"Trying conversion with {method_name}...")
            if method_func(svg_data, size, output_path):
                return True
        
        self.log("All PNG conversion methods failed", "ERROR")
        return False
    
    def _convert_with_cairosvg(self, svg_data: bytes, size: int, output_path: str) -> bool:
        """Convert using CairoSVG"""
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            
            cairosvg.svg2png(
                bytestring=svg_data,
                write_to=output_path,
                output_width=size,
                output_height=size,
                background_color='transparent'
            )
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.log(f"PNG saved to {output_path} ({size}×{size})", "SUCCESS")
                return True
            return False
            
        except ImportError:
            self.log("CairoSVG not installed, run: pip install cairosvg", "ERROR")
            return False
        except Exception as e:
            self.log(f"CairoSVG conversion failed: {e}", "ERROR")
            return False

    
    def process_emoji(self, emoji: str, size: int, output_format: str = "svg", output_path: str = None) -> str:
        """
        Main method for processing emoji
        
        Args:
            emoji: Emoji character
            size: Output size
            output_format: Output format ('svg' or 'png')
            output_path: Output path (optional)
            
        Returns:
            Path to the output file
        """
        # Validate parameters
        if not self.validate_emoji(emoji):
            self.log(f"'{emoji}' may not be a valid emoji", "WARNING")
        
        if size <= 0:
            raise ValueError("size must be greater than 0")
        
        # Fetch SVG
        svg_data, source = self.fetch_svg(emoji)
        self.log(f"Fetched {len(svg_data)} bytes of SVG data from {source}")
        
        # Generate output path
        if not output_path:
            codepoints = self.emoji_to_codepoints(emoji)
            output_path = f"emoji_{codepoints}.{output_format}"
        
        # Process file
        if output_format == "svg":
            success = self.save_svg(svg_data, output_path)
        else:
            success = self.convert_to_png(svg_data, size, output_path)
        
        if not success:
            raise RuntimeError("File processing failed")
        
        return os.path.abspath(output_path)

def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(
        description="Emoji Processing Agent: Fetch emoji SVG/PNG images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  %(prog)s "1️⃣" 128 --format png -o my_emoji.png
  %(prog)s "👍🏻" 256 --format svg
  %(prog)s "🎉" 512 --format png --verbose
        """
    )
    
    parser.add_argument("emoji", help="Emoji to process, e.g. '1️⃣' or '👍🏻'")
    parser.add_argument("size", type=int, help="Output image size in pixels")
    parser.add_argument("--format", "-f", choices=["svg", "png"], default="svg", help="Output format")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    
    args = parser.parse_args()
    
    try:
        agent = EmojiProcessAgent(verbose=args.verbose)
        output_path = agent.process_emoji(args.emoji, args.size, args.format, args.output)
        print(f"🎉 Completed! File saved at: {output_path}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()