"""
guess_bench_analyzer.py
GuessBenchmark 推断执行器

职责：
- 根据图片版本号（v0 / v2-v7 / v8-v25）动态生成 prompt
- 从 LLM 响应中解析成语（支持 JSON / 纯文本 / 正则多种格式）
- 单图和批量推断，结果实时写入 JSON 文件
- 只通过 unified_client 与 API 交互，不直接接触底层 API

输出 JSON 格式：
    [
        {
            "image_name": "一心一意_v0_001.png",
            "gt": "一心一意",
            "pred": "一心一意",
            "inference_chain": "...",
            "model": "gpt-4o",
            "success": true
        },
        ...
    ]
"""

import json
import logging
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from unified_client import UnifiedImageLLMClient, create_client

logger = logging.getLogger(__name__)

# ── Prompt 模板 ──────────────────────────────────────

_BASE_PROMPT = (
    "You are a linguistic expert tasked with identifying Chinese four-character idioms (成语) "
    "based on a set of four emojis. {order_instruction} "
    "Each emoji corresponds to one character in the idiom. The mapping can be either:\n"
    "1) Semantic Match: The emoji's meaning aligns with the character's meaning.\n"
    "2) Phonetic Match: The emoji's Chinese pronunciation (pinyin) matches or closely "
    "resembles the character's pronunciation.\n\n"
    "You MUST output a single JSON object with NO additional text:\n"
    '{{"idiom": "四字成语", "inference_chain": "step-by-step reasoning..."}}'
)

_ORDER_INSTRUCTIONS = {
    # v0：四个 emoji 水平顺序排列
    "sequential": "Each emoji corresponds to one character in sequential order (left to right).",
    # v2-v7：圆形/对角线/矩形等布局，模型需自判断读取顺序
    "freeform": (
        "The emojis may be arranged in circular, diagonal, rectangular, or other patterns. "
        "You need to determine the appropriate reading order yourself."
    ),
    # v8-v25：图中有数字序号或箭头指示顺序
    "guided": (
        "Follow the numerical sequence or connecting arrows shown in the image "
        "to determine the reading order of the emojis."
    ),
}

_SYSTEM_PROMPT = (
    "You are an expert in Chinese linguistics and culture. "
    "Always respond with a single valid JSON object, no markdown, no extra text."
)


# ── 核心类 ───────────────────────────────────────────

class GuessBenchmarkAnalyzer:
    """
    GuessBenchmark 推断执行器

    使用示例：
        analyzer = GuessBenchmarkAnalyzer(model="gpt-4o")

        # 单张图片
        result = analyzer.analyze_image("images/一心一意_v0_001.png", gt="一心一意")

        # 批量推断（自动从文件名解析 gt）
        analyzer.analyze_batch(
            image_dir="images/",
            output_file="results/gpt4o_results.json",
        )

        # 切换模型继续推断
        analyzer.switch_model("gemini-2.5-flash")
        analyzer.analyze_batch(...)
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: Optional[str] = None,
        config_file: str = "config.env",
        max_tokens: int = 512,
        temperature: float = 0.2,
    ):
        """
        Args:
            model:        使用的模型名称
            provider:     指定 provider（None 则用 config.env 中的设置）
            config_file:  配置文件路径
            max_tokens:   生成最大 token 数
            temperature:  采样温度（推断任务建议用低温度）
        """
        self.client: UnifiedImageLLMClient = create_client(
            model=model,
            provider=provider,
            config_file=config_file,
        )
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"GuessBenchmarkAnalyzer 初始化完成: {self.client}")

    # ── Prompt 生成 ──────────────────────────────────

    @staticmethod
    def get_version_num(image_name: str) -> int:
        """从图片文件名提取版本号，例如 '一心一意_v3_001.png' → 3"""
        m = re.search(r"v(\d+)", image_name)
        return int(m.group(1)) if m else 0

    @classmethod
    def prompt_generator(cls, image_name: str) -> tuple[str, str]:
        """
        根据图片版本号生成对应的 (prompt, system_prompt)。

        版本策略：
            v0          → 顺序排列（sequential）
            v2  – v7    → 自由布局（freeform），模型自判断顺序
            v8  – v25   → 有引导标记（guided），按数字/箭头读取
            其他        → 默认 sequential

        Returns:
            (prompt, system_prompt)
        """
        v = cls.get_version_num(image_name)

        if v == 0:
            order_key = "sequential"
        elif 2 <= v <= 7:
            order_key = "freeform"
        elif 8 <= v <= 25:
            order_key = "guided"
        else:
            order_key = "sequential"

        prompt = _BASE_PROMPT.format(
            order_instruction=_ORDER_INSTRUCTIONS[order_key]
        )
        return prompt, _SYSTEM_PROMPT

    # ── 响应解析 ─────────────────────────────────────

    @staticmethod
    def _extract_idiom_and_chain(response: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 LLM 响应中提取成语和推理链。

        解析顺序：
        1. 尝试直接 JSON 解析
        2. 正则提取 ```json ... ``` 代码块
        3. 正则提取 { ... } 内容
        4. 回退：直接用正则提取四字成语

        Returns:
            (idiom, inference_chain)，无法解析时返回 (None, None)
        """
        if not response:
            return None, None

        text = response.strip()

        # 1. 去掉 markdown 代码块包裹
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            text = code_block.group(1)

        # 2. 尝试直接解析 JSON（也处理首尾有多余文字的情况）
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                idiom_raw = data.get("idiom", "")
                chain = data.get("inference_chain", "")
                # 提取纯汉字
                idiom = "".join(re.findall(r"[\u4e00-\u9fff]", idiom_raw))[:4]
                if len(idiom) == 4:
                    return idiom, chain
            except json.JSONDecodeError:
                pass

        # 3. 回退：在各汉字连续段中寻找长度恰好为4的段，或取末尾4字
        logger.warning("JSON 解析失败，使用正则回退提取成语")
        seqs = re.findall(r"[\u4e00-\u9fff]+", text)
        for seq in seqs:
            if len(seq) == 4:
                return seq, None
        # 最后兜底：取最长连续段末尾4字（末尾通常是成语）
        if seqs:
            longest = max(seqs, key=len)
            if len(longest) >= 4:
                return longest[-4:], None
        return None, None

    # ── 单图推断 ─────────────────────────────────────

    def analyze_image(
        self,
        image_path: str,
        gt: Optional[str] = None,
    ) -> dict:
        """
        对单张图片进行推断。

        Args:
            image_path:  图片文件路径
            gt:          ground truth 成语（可选，用于计算是否正确）

        Returns:
            {
                "image_name": str,
                "gt": str | None,
                "pred": str | None,
                "inference_chain": str | None,
                "model": str,
                "success": bool,
                "correct": bool | None,  # gt 为 None 时此字段也为 None
            }
        """
        image_name = Path(image_path).name
        prompt, system_prompt = self.prompt_generator(image_name)

        response = self.client.send_image(
            image_path,
            prompt,
            system_prompt=system_prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        pred, chain = self._extract_idiom_and_chain(response)
        success = pred is not None
        correct = (pred == gt) if (gt is not None and pred is not None) else None

        return {
            "image_name": image_name,
            "gt": gt,
            "pred": pred,
            "inference_chain": chain,
            "raw_response": response,
            "model": self.client.current_model,
            "success": success,
            "correct": correct,
        }

    # ── 批量推断 ─────────────────────────────────────

    @staticmethod
    def _parse_gt_from_filename(image_name: str) -> Optional[str]:
        """
        从文件名解析 ground truth 成语。

        支持格式：
            一心一意_v0_001.png   → 一心一意
            一心一意.png          → 一心一意
            idiom_一心一意_v3.png → 一心一意
        """
        stem = Path(image_name).stem
        # 取下划线分割后的第一段纯汉字
        parts = stem.split("_")
        for p in parts:
            chinese = "".join(re.findall(r"[\u4e00-\u9fff]", p))
            if len(chinese) == 4:
                return chinese
        return None

    def analyze_batch(
        self,
        image_dir: str,
        output_file: str,
        gt_json: Optional[str] = None,
        extensions: tuple = (".png", ".jpg", ".jpeg"),
        resume: bool = True,
    ) -> list[dict]:
        """
        批量推断目录下的所有图片。

        Args:
            image_dir:   图片目录
            output_file: 结果输出 JSON 文件路径
            gt_json:     可选，ground truth JSON 文件路径
                         格式: [{"image_name": "xxx.png", "gt": "成语"}, ...]
                         不提供则从文件名解析
            extensions:  接受的图片扩展名
            resume:      True 时跳过 output_file 中已存在的图片（断点续传）

        Returns:
            全部结果列表
        """
        image_dir = Path(image_dir)
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 收集图片列表
        all_images = sorted([
            p for p in image_dir.iterdir()
            if p.suffix.lower() in extensions
        ])
        if not all_images:
            logger.warning(f"目录 {image_dir} 中没有找到图片")
            return []

        # 加载 gt 映射
        gt_map: dict[str, str] = {}
        if gt_json and Path(gt_json).exists():
            with open(gt_json, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    gt_map[item["image_name"]] = item.get("gt", "")
            logger.info(f"已加载 ground truth: {len(gt_map)} 条")

        # 断点续传：读取已完成的图片名
        done_names: set[str] = set()
        existing_results: list[dict] = []
        if resume and output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_results = json.load(f)
                done_names = {r["image_name"] for r in existing_results}
                logger.info(f"断点续传：跳过已完成的 {len(done_names)} 张图片")
            except Exception:
                logger.warning("无法读取已有结果文件，将从头开始")

        # 过滤待处理列表
        todo = [p for p in all_images if p.name not in done_names]
        logger.info(
            f"共 {len(all_images)} 张图片，待处理 {len(todo)} 张 "
            f"（模型: {self.client.current_model}）"
        )

        results = list(existing_results)
        correct_count = sum(1 for r in results if r.get("correct"))
        total_with_gt = sum(1 for r in results if r.get("gt"))

        # 实时写入回调
        def on_result(idx: int, image_path: str, response: str):
            pass  # 写入在下方统一处理

        for idx, image_path in enumerate(todo, start=1):
            image_name = image_path.name
            gt = gt_map.get(image_name) or self._parse_gt_from_filename(image_name)

            print(
                f"[{idx}/{len(todo)}] {image_name}  gt={gt or '?'}",
                end="  ",
                flush=True,
            )

            record = self.analyze_image(str(image_path), gt=gt)
            results.append(record)

            status = "✓" if record["correct"] else ("✗" if record["correct"] is False else "?")
            print(f"pred={record['pred'] or 'FAIL'}  {status}")

            if record.get("correct"):
                correct_count += 1
            if record.get("gt"):
                total_with_gt += 1

            # 实时写入（防止中途崩溃丢失数据）
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        # 统计
        success_count = sum(1 for r in results if r["success"])
        acc = correct_count / total_with_gt * 100 if total_with_gt else 0
        print(f"\n{'─' * 50}")
        print(f"  总计        : {len(results)} 张")
        print(f"  API 成功    : {success_count}")
        print(f"  有 GT 样本  : {total_with_gt}")
        print(f"  预测正确    : {correct_count}")
        print(f"  准确率      : {acc:.2f}%")
        print(f"  模型        : {self.client.current_model}")
        print(f"  结果文件    : {output_file}")
        print(f"{'─' * 50}\n")

        return results

    # ── 便捷接口 ─────────────────────────────────────

    def switch_model(self, model: str) -> "GuessBenchmarkAnalyzer":
        """切换模型（返回 self，支持链式调用）"""
        self.client.switch_model(model)
        return self

    def switch_provider(self, provider: str) -> "GuessBenchmarkAnalyzer":
        """切换 provider（返回 self，支持链式调用）"""
        self.client.switch_provider(provider)
        return self

    def print_status(self):
        """打印当前配置状态"""
        self.client.print_status()

    def __repr__(self):
        return (
            f"GuessBenchmarkAnalyzer("
            f"model={self.client.current_model!r}, "
            f"provider={self.client.current_provider!r})"
        )


# ── 命令行入口 ───────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="GuessBenchmark 批量推断")
    parser.add_argument("--image_dir",  required=True,  help="图片目录")
    parser.add_argument("--output",     required=True,  help="输出 JSON 文件路径")
    parser.add_argument("--model",      default="gpt-4o", help="模型名称")
    parser.add_argument("--provider",   default=None,   help="API provider")
    parser.add_argument("--gt_json",    default=None,   help="ground truth JSON 文件")
    parser.add_argument("--config",     default="config.env", help="配置文件路径")
    parser.add_argument("--no_resume",  action="store_true",  help="禁用断点续传")
    parser.add_argument("--max_tokens", type=int, default=512, help="最大生成 token 数")
    parser.add_argument("--temperature", type=float, default=0.2, help="采样温度")
    args = parser.parse_args()

    analyzer = GuessBenchmarkAnalyzer(
        model=args.model,
        provider=args.provider,
        config_file=args.config,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    analyzer.print_status()

    analyzer.analyze_batch(
        image_dir=args.image_dir,
        output_file=args.output,
        gt_json=args.gt_json,
        resume=not args.no_resume,
    )