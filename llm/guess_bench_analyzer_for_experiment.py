"""
guess_bench_analyzer_for_experiment.py
GuessBenchmark 推断执行器

职责：
- 支持中文（--task ch）和英文（--task en）两种数据集
- 中文：基于图片所在子目录判断 prompt 类型（sequential/freeform/guided）
- 英文：统一使用英文 idiom 识别 prompt，根据 GT 动态注入 word count hint
- 从 LLM 响应中解析答案（JSON / 正则多种格式）
- 单图和批量推断，结果实时写入 JSON 文件

─── Prompt 设计说明 ─────────────────────────────────────

中文（--task ch）：
  - 1-shot 示例：🐟🎵➰🍚 → 余音绕梁
    同时覆盖语义对应（🎵→音、➰→绕）和谐音对应（🐟→余、🍚→梁），
    引导模型建立正确的谐音推理习惯。
  - inference_chain 限定为中文，格式：emoji→字(类型:理由)，四项以 | 分隔，
    总长度 ≤ 100 字符，便于后续对推理过程做定量分析。

英文（--task en）：
  - 1-shot 示例：📍🧑❤️🔥 → set one's heart ablaze
    覆盖语义直接对应（❤️→heart、🔥→ablaze）和间接语义映射（📍→set、🧑→one's）。
  - 放宽 emoji 映射描述：允许逐词对应、整体意象、视觉隐喻三种映射方式。
  - 根据 GT 动态注入 word count hint，减少模型输出缩略形式或过长短语的情况。
  - 输出格式标准化（大小写、标点）由 _normalize_en 在计算准确率时统一处理，
    不在 prompt 中硬规定，避免引入与成语惯用写法冲突的约束。

─── 英文任务准确率说明 ──────────────────────────────────────

strict_accuracy：标准化精确匹配
  - 统一小写、去标点、合并空格后做完全相等比较
  - 例：gt="trade off"，pred="trade-off" → ✓

match_accuracy：模糊匹配（基于 SequenceMatcher 相似度）
  - 归一化后计算字符级相似度，≥ match_threshold 即判对
  - 默认阈值 0.85，可通过 --match_threshold 调整
  - 例：gt="hit the nail on the head"，pred="hit nail on head" → 视阈值判断

两个指标均记录在结果 JSON 中，方便对比分析。

─── 目录结构约定 ───────────────────────────────────────────

中文数据集（--task ch）：
  {image_dir}/
  └── {idx}_{四字成语}/
      └── 1/
          ├── {idiom}_base_v001.png              → sequential prompt
          ├── seq_varients_pure/
          │   └── *.png                          → freeform prompt
          └── seq_varients_with_guideance/
              └── *.png                          → guided prompt

英文数据集（--task en）：
  {image_dir}/
  └── {idx}_{idiom_with_underscores}/
      └── {idiom}_base.png                       → sequential prompt

─── 输出 JSON 格式 ──────────────────────────────────────────

中文：
[
    {
        "image_name": "一心一意_base_v001.png",
        "image_path": "...",
        "gt": "一心一意",
        "pred": "一心一意",
        "inference_chain": "...",
        "raw_response": "...",
        "model": "gpt-4o",
        "prompt_type": "sequential",
        "task": "ch",
        "success": true,
        "correct": true,
        "error": null
    }
]

英文（额外含双准确率字段）：
[
    {
        "image_name": "trade_off_base.png",
        "image_path": "...",
        "gt": "trade off",
        "pred": "trade-off",
        "inference_chain": "...",
        "raw_response": "...",
        "model": "gpt-4o",
        "prompt_type": "sequential",
        "task": "en",
        "success": true,
        "strict_correct": true,
        "match_correct": true,
        "match_score": 0.941,
        "error": null
    }
]
"""

import json
import logging
import re
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Literal

from unified_client import UnifiedImageLLMClient, create_client

logger = logging.getLogger(__name__)

TaskType = Literal["ch", "en"]

# ══════════════════════════════════════════════════════════
#  Prompt 模板
# ══════════════════════════════════════════════════════════

# ── 中文 Prompt ──────────────────────────────────────────
#
# Few-shot 设计说明：
#   参照 BIG-Bench、MMBench 等主流 benchmark 的做法，对于需要
#   创意联想（尤其是谐音映射）的任务，加入 1 条 few-shot 示例
#   可显著降低模型"走最字面语义"的倾向，同时示范期望的
#   inference_chain 格式，便于后续对推理过程做定量分析。
#   示例选用"余音绕梁"，同时包含语义对应（🎵→音、➰→绕）
#   和谐音对应（🐟→余、🍚→梁），覆盖两种映射类型。

_CH_FEW_SHOT = (
    "Here is one example to illustrate the reasoning format:\n"
    "Emojis: 🐟 🎵 ➰ 🍚\n"
    "Output: "
    '{{"idiom": "余音绕梁", "inference_chain": '
    '"🐟→余(谐音:鱼/yú≈余/yú) | 🎵→音(语义:音乐声音) | ➰→绕(语义:缠绕循环) | 🍚→梁(谐音:粮/liáng≈梁/liáng)"}}\n\n'
    "Now identify the idiom for the image below.\n"
)

_CH_PROMPT_TEMPLATE = (
    "You are a linguistic expert tasked with identifying Chinese four-character idioms (成语) "
    "based on a set of four emojis. {order_instruction} "
    "Each emoji corresponds to exactly one character in the idiom. The mapping can be either:\n"
    "1) Semantic Match (语义对应): The emoji's meaning aligns with the character's meaning.\n"
    "2) Phonetic Match (谐音对应): The emoji's Chinese name (pinyin) matches or closely "
    "resembles the character's pronunciation.\n\n"
    + _CH_FEW_SHOT
    + "You MUST output a single JSON object with NO additional text. "
    "Use Chinese for the inference_chain. "
    "Format inference_chain as: emoji→字(类型:理由) for each of the four emojis, joined by ' | '. "
    "Keep inference_chain under 100 characters.\n"
    '{{"idiom": "四字成语", "inference_chain": "emoji→字(类型:理由) | ..."}}'
)

_CH_ORDER_INSTRUCTIONS = {
    "sequential": (
        "The four emojis are arranged horizontally from left to right. "
        "Read them in that order (left to right)."
    ),
    "freeform": (
        "The emojis may be arranged in circular, diagonal, grid, or other non-linear patterns. "
        "Determine the most natural reading order yourself."
    ),
    "guided": (
        "The image contains numerical labels or connecting arrows that indicate the reading order. "
        "Follow those cues strictly to determine the sequence."
    ),
}

_CH_SYSTEM_PROMPT = (
    "You are an expert in Chinese linguistics and culture. "
    "Always respond with a single valid JSON object, no markdown, no extra text. "
    "The idiom field must contain exactly four Chinese characters (四字成语). "
    "The inference_chain field must be written in Chinese."
)

# ── 英文 Prompt ──────────────────────────────────────────
#
# 英文 idiom 的 emoji 设计可能是整体意象映射而非逐词对应，
# 因此放宽描述，允许整体隐喻和部分词汇映射共存。
# 不在 prompt 中硬规定输出格式（大小写、冠词等），
# 由 _normalize_en 在计算 strict_accuracy / match_accuracy 时统一处理。
# GT 的词数通过 gt_word_count 参数动态注入，帮助模型锁定长度范围。
#
# Few-shot 设计说明：
#   示例选用 "set one's heart ablaze"，覆盖语义直接对应（❤️→heart、🔥→ablaze）
#   和间接语义映射（📍→set、🧑→one's），同时示范期望的 inference_chain 格式。

_EN_FEW_SHOT = (
    "Here is one example to illustrate the reasoning format:\n"
    "Emojis: 📍 🧑 ❤️ 🔥\n"
    'Output: {"idiom": "set one\'s heart ablaze", "inference_chain": '
    '"📍→set (semantic: a pin being fixed in place = to set/fix) | '
    "🧑→one's (semantic: a person = one's/someone's) | "
    "❤️→heart (semantic: heart) | "
    '🔥→ablaze (semantic: fire/flames = ablaze)"}\n\n'
    "Now identify the idiom for the image below.\n"
)


def _build_en_prompt(gt_word_count: Optional[int] = None) -> str:
    """
    生成英文任务 prompt。

    Args:
        gt_word_count: GT idiom 的单词数（从文件夹名解析得到）。
                       不为 None 时在 prompt 中注入长度提示，
                       减少模型输出缩略形式或过长短语的情况。
    """
    length_hint = (
        f"The idiom you are looking for consists of exactly {gt_word_count} word(s). "
        if gt_word_count is not None
        else ""
    )
    return (
        "You are a linguistic expert tasked with identifying an English idiom based on a set of emojis. "
        "The emojis are arranged horizontally from left to right. "
        "The emojis collectively hint at the idiom. Each emoji may:\n"
        "1) Directly represent a word in the idiom (Semantic Match).\n"
        "2) Sound like a word in the idiom in English (Phonetic Match).\n"
        "3) Serve as a visual metaphor for the overall theme or a key concept of the idiom.\n\n"
        + _EN_FEW_SHOT
        + length_hint
        + "You MUST output a single JSON object with NO additional text:\n"
        '{"idiom": "the english idiom", "inference_chain": "emoji→word (type: reason) | ..."}'
    )

# 默认（无 GT）英文 prompt，供无 GT 场景或向后兼容使用
_EN_PROMPT = _build_en_prompt(gt_word_count=None)

_EN_SYSTEM_PROMPT = (
    "You are an expert in English linguistics and idiomatic expressions. "
    "Always respond with a single valid JSON object, no markdown, no extra text."
)

# 默认模糊匹配阈值
DEFAULT_MATCH_THRESHOLD = 0.85


# ══════════════════════════════════════════════════════════
#  英文标准化工具
# ══════════════════════════════════════════════════════════

def _normalize_en(text: str) -> str:
    """
    英文 idiom 标准化：统一小写、去标点、合并空格。

    例：
        "Trade-Off!"  → "trade off"
        "break a leg" → "break a leg"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)    # 标点替换为空格
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_score(a: str, b: str) -> float:
    """
    计算两个标准化字符串的 SequenceMatcher 相似度（0.0 ~ 1.0）。
    任一输入为空时返回 0.0。
    """
    na, nb = _normalize_en(a), _normalize_en(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


# ══════════════════════════════════════════════════════════
#  核心类
# ══════════════════════════════════════════════════════════

class GuessBenchmarkAnalyzer:
    """
    GuessBenchmark 推断执行器（支持中/英文双任务）

    使用示例：
        # 中文批量推断
        analyzer = GuessBenchmarkAnalyzer(model="gpt-4o", task="ch")
        analyzer.analyze_batch(
            image_dir="variants_chinese/sequential/",
            output_file="results/ch_gpt4o.json",
        )

        # 英文批量推断（默认阈值 0.85）
        analyzer = GuessBenchmarkAnalyzer(model="gpt-4o", task="en")
        analyzer.analyze_batch(
            image_dir="variants_english/sequential/",
            output_file="results/en_gpt4o.json",
        )
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        task: TaskType = "ch",
        provider: Optional[str] = None,
        config_file: str = "config.env",
        max_tokens: int = 512,
        temperature: float = 0.2,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    ):
        """
        Args:
            model:            使用的模型名称
            task:             "ch"（中文成语）或 "en"（英文 idiom）
            provider:         指定 provider（None 则用 config.env 中的设置）
            config_file:      配置文件路径
            max_tokens:       生成最大 token 数
            temperature:      采样温度
            match_threshold:  英文模糊匹配阈值，0.0~1.0（默认 0.85）
        """
        if task not in ("ch", "en"):
            raise ValueError(f"task 必须为 'ch' 或 'en'，得到: {task!r}")

        self.task: TaskType = task
        self.match_threshold = match_threshold
        self.client: UnifiedImageLLMClient = create_client(
            model=model,
            provider=provider,
            config_file=config_file,
        )
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(
            f"GuessBenchmarkAnalyzer 初始化完成: "
            f"task={task}, match_threshold={match_threshold}, {self.client}"
        )

    # ══════════════════════════════════════════════════════
    #  Prompt 生成
    # ══════════════════════════════════════════════════════

    @staticmethod
    def build_ch_prompt(prompt_type: str) -> tuple[str, str]:
        """生成中文任务的 (prompt, system_prompt)。"""
        order_instr = _CH_ORDER_INSTRUCTIONS.get(
            prompt_type, _CH_ORDER_INSTRUCTIONS["sequential"]
        )
        prompt = _CH_PROMPT_TEMPLATE.format(order_instruction=order_instr)
        return prompt, _CH_SYSTEM_PROMPT

    @staticmethod
    def build_en_prompt(gt: Optional[str] = None) -> tuple[str, str]:
        """
        生成英文任务的 (prompt, system_prompt)。

        Args:
            gt: 当前样本的 ground truth idiom（用于计算 word count hint）。
                为 None 时不注入长度提示。
        """
        gt_word_count = len(gt.split()) if gt else None
        return _build_en_prompt(gt_word_count), _EN_SYSTEM_PROMPT

    def build_prompt(self, prompt_type: str = "sequential", gt: Optional[str] = None) -> tuple[str, str]:
        """
        根据当前 task 生成对应 prompt。

        Args:
            prompt_type: 中文任务的 prompt 类型（sequential/freeform/guided）。
            gt:          当前样本 GT（英文任务用于注入 word count hint）。
        """
        if self.task == "ch":
            return self.build_ch_prompt(prompt_type)
        else:
            return self.build_en_prompt(gt)

    # ══════════════════════════════════════════════════════
    #  响应解析
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _extract_ch_idiom(response: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 LLM 响应中提取中文四字成语和推理链。

        解析顺序：
        1. JSON 解析（含 markdown 代码块处理）
        2. 正则回退：汉字连续段中找长度恰好为 4 的段
        3. 最终兜底：取最长连续汉字段的末尾 4 字
        """
        if not response:
            return None, None

        try:
            text = response.strip()

            # 去掉 ```json ... ``` 包裹
            code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if code_block:
                text = code_block.group(1)

            # 尝试 JSON 解析
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    idiom_raw = data.get("idiom", "")
                    chain = data.get("inference_chain", "")
                    idiom = "".join(re.findall(r"[\u4e00-\u9fff]", idiom_raw))[:4]
                    if len(idiom) == 4:
                        return idiom, chain
                except json.JSONDecodeError:
                    pass

            # 正则回退
            logger.warning("JSON 解析失败，使用正则回退提取中文成语")
            seqs = re.findall(r"[\u4e00-\u9fff]+", text)
            for seq in seqs:
                if len(seq) == 4:
                    return seq, None
            if seqs:
                longest = max(seqs, key=len)
                if len(longest) >= 4:
                    return longest[-4:], None

        except Exception as e:
            logger.error(f"_extract_ch_idiom 解析异常: {e}")

        return None, None

    @staticmethod
    def _extract_en_idiom(response: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 LLM 响应中提取英文 idiom 和推理链。
        提取后统一转小写，便于后续比对。
        """
        if not response:
            return None, None

        try:
            text = response.strip()

            # 去掉 ```json ... ``` 包裹
            code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if code_block:
                text = code_block.group(1)

            # 尝试 JSON 解析
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    idiom = data.get("idiom", "").strip().lower()
                    chain = data.get("inference_chain", "")
                    if idiom:
                        return idiom, chain
                except json.JSONDecodeError:
                    pass

            # 回退：取第一行非空文本
            logger.warning("JSON 解析失败，使用文本回退提取英文 idiom")
            for line in text.split("\n"):
                line = line.strip().lower()
                if line and len(line) < 100:
                    return line, None

        except Exception as e:
            logger.error(f"_extract_en_idiom 解析异常: {e}")

        return None, None

    def extract_prediction(self, response: str) -> tuple[Optional[str], Optional[str]]:
        """根据当前 task 选择对应的提取方法。"""
        if self.task == "ch":
            return self._extract_ch_idiom(response)
        else:
            return self._extract_en_idiom(response)

    # ══════════════════════════════════════════════════════
    #  英文准确率计算
    # ══════════════════════════════════════════════════════

    def _eval_en(self, pred: str, gt: str) -> dict:
        """
        计算英文预测结果的双重准确率指标。

        Returns:
            {
                "strict_correct": bool,   # 标准化后精确匹配
                "match_correct":  bool,   # 模糊匹配 ≥ match_threshold
                "match_score":    float,  # 实际相似度（0.0~1.0）
            }
        """
        try:
            score = _match_score(pred, gt)
            strict = _normalize_en(pred) == _normalize_en(gt)
            fuzzy = score >= self.match_threshold
            return {
                "strict_correct": strict,
                "match_correct": fuzzy,
                "match_score": round(score, 4),
            }
        except Exception as e:
            logger.error(f"_eval_en 计算异常 pred={pred!r} gt={gt!r}: {e}")
            return {
                "strict_correct": False,
                "match_correct": False,
                "match_score": 0.0,
            }

    # ══════════════════════════════════════════════════════
    #  GT 解析工具
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _parse_gt_from_folder(folder_name: str, task: TaskType) -> Optional[str]:
        """
        从成语文件夹名称提取 ground truth。

        中文：  "1_一丘之貉"   → "一丘之貉"
        英文：  "1_trade_off"  → "trade off"
        """
        try:
            parts = folder_name.split("_", 1)
            if len(parts) < 2:
                return None
            name_part = parts[1]

            if task == "ch":
                chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", name_part))
                return chinese if chinese else None
            else:
                return name_part.replace("_", " ").strip() or None
        except Exception as e:
            logger.error(f"_parse_gt_from_folder 解析异常 folder={folder_name!r}: {e}")
            return None

    # ══════════════════════════════════════════════════════
    #  图片收集
    # ══════════════════════════════════════════════════════

    def _collect_images_ch(self, image_dir: str) -> list[dict]:
        """遍历中文数据集目录，收集所有图片及元数据。"""
        root = Path(image_dir)

        if not root.exists():
            raise FileNotFoundError(f"中文数据集目录不存在: {image_dir}")
        if not root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {image_dir}")

        items = []

        try:
            idiom_folders = sorted(root.iterdir())
        except PermissionError as e:
            raise PermissionError(f"无权限访问目录: {image_dir}") from e

        for idiom_folder in idiom_folders:
            if not idiom_folder.is_dir():
                continue

            gt = self._parse_gt_from_folder(idiom_folder.name, "ch")
            if not gt:
                logger.warning(f"无法解析 GT，跳过: {idiom_folder.name}")
                continue

            set_dir = idiom_folder / "1"
            if not set_dir.is_dir():
                logger.warning(f"缺少 '1' 子目录，跳过: {idiom_folder}")
                continue

            try:
                # base → sequential
                for f in sorted(set_dir.glob("*.png")):
                    items.append({"path": f, "gt": gt, "prompt_type": "sequential"})

                # pure 变体 → freeform
                pure_dir = set_dir / "seq_varients_pure"
                if pure_dir.is_dir():
                    for f in sorted(pure_dir.glob("*.png")):
                        items.append({"path": f, "gt": gt, "prompt_type": "freeform"})

                # guidance 变体 → guided
                guide_dir = set_dir / "seq_varients_with_guideance"
                if guide_dir.is_dir():
                    for f in sorted(guide_dir.glob("*.png")):
                        items.append({"path": f, "gt": gt, "prompt_type": "guided"})

            except Exception as e:
                logger.error(f"遍历子目录失败 [{idiom_folder}]: {e}，跳过此成语")
                continue

        logger.info(f"中文数据集：共收集 {len(items)} 张图片")
        return items

    def _collect_images_en(self, image_dir: str) -> list[dict]:
        """遍历英文数据集目录，收集所有图片及元数据。"""
        root = Path(image_dir)

        if not root.exists():
            raise FileNotFoundError(f"英文数据集目录不存在: {image_dir}")
        if not root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {image_dir}")

        items = []

        try:
            idiom_folders = sorted(root.iterdir())
        except PermissionError as e:
            raise PermissionError(f"无权限访问目录: {image_dir}") from e

        for idiom_folder in idiom_folders:
            if not idiom_folder.is_dir():
                continue

            gt = self._parse_gt_from_folder(idiom_folder.name, "en")
            if not gt:
                logger.warning(f"无法解析 GT，跳过: {idiom_folder.name}")
                continue

            try:
                for f in sorted(idiom_folder.glob("*.png")):
                    items.append({"path": f, "gt": gt.lower(), "prompt_type": "sequential"})
            except Exception as e:
                logger.error(f"遍历子目录失败 [{idiom_folder}]: {e}，跳过此 idiom")
                continue

        logger.info(f"英文数据集：共收集 {len(items)} 张图片")
        return items

    def collect_images(self, image_dir: str) -> list[dict]:
        """根据当前 task 收集图片。"""
        if self.task == "ch":
            return self._collect_images_ch(image_dir)
        else:
            return self._collect_images_en(image_dir)

    # ══════════════════════════════════════════════════════
    #  单图推断
    # ══════════════════════════════════════════════════════

    def analyze_image(
        self,
        image_path: str,
        gt: Optional[str] = None,
        prompt_type: str = "sequential",
    ) -> dict:
        """
        对单张图片进行推断。

        任何异常都会被捕获并记录在 record["error"] 字段中，
        不会向上抛出，确保批量任务不因单张图片失败而中断。

        中文任务结果包含：correct
        英文任务结果包含：strict_correct / match_correct / match_score
        """
        image_name = Path(image_path).name

        # 构造失败时的兜底记录（确保字段完整）
        def _failed_record(error_msg: str) -> dict:
            base = {
                "image_name": image_name,
                "image_path": str(image_path),
                "gt": gt,
                "pred": None,
                "inference_chain": None,
                "raw_response": None,
                "model": self.client.current_model,
                "prompt_type": prompt_type,
                "task": self.task,
                "success": False,
                "error": error_msg,
            }
            if self.task == "ch":
                base["correct"] = None
            else:
                base["strict_correct"] = None
                base["match_correct"]  = None
                base["match_score"]    = None
            return base

        # ── API 调用 ────────────────────────────────────
        try:
            # 英文任务：将 GT 传入以动态注入 word count hint；中文任务忽略 gt 参数
            prompt, system_prompt = self.build_prompt(prompt_type, gt=gt)
        except Exception as e:
            logger.error(f"build_prompt 异常 [{image_name}]: {e}")
            return _failed_record(f"prompt构建失败: {e}")

        try:
            response = self.client.send_image(
                image_path,
                prompt,
                system_prompt=system_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception as e:
            logger.error(f"API 调用异常 [{image_name}]: {e}")
            return _failed_record(f"API调用异常: {e}")

        # ── 响应解析 ────────────────────────────────────
        try:
            pred, chain = self.extract_prediction(response)
        except Exception as e:
            logger.error(f"响应解析异常 [{image_name}]: {e}")
            pred, chain = None, None

        success = pred is not None

        record = {
            "image_name": image_name,
            "image_path": str(image_path),
            "gt": gt,
            "pred": pred,
            "inference_chain": chain,
            "raw_response": response,
            "model": self.client.current_model,
            "prompt_type": prompt_type,
            "task": self.task,
            "success": success,
            "error": None,
        }

        # ── 指标计算 ────────────────────────────────────
        try:
            if self.task == "ch":
                record["correct"] = (
                    (pred == gt) if (gt is not None and pred is not None) else None
                )
            else:
                if gt is not None and pred is not None:
                    eval_result = self._eval_en(pred, gt)
                    record["strict_correct"] = eval_result["strict_correct"]
                    record["match_correct"]  = eval_result["match_correct"]
                    record["match_score"]    = eval_result["match_score"]
                else:
                    record["strict_correct"] = None
                    record["match_correct"]  = None
                    record["match_score"]    = None
        except Exception as e:
            logger.error(f"指标计算异常 [{image_name}]: {e}")
            record["error"] = f"指标计算异常: {e}"
            if self.task == "ch":
                record.setdefault("correct", None)
            else:
                record.setdefault("strict_correct", None)
                record.setdefault("match_correct", None)
                record.setdefault("match_score", None)

        return record

    # ══════════════════════════════════════════════════════
    #  批量推断
    # ══════════════════════════════════════════════════════

    def analyze_batch(
        self,
        image_dir: str,
        output_file: str,
        resume: bool = True,
    ) -> list[dict]:
        """
        批量推断整个数据集目录。

        单张图片的任何异常均被捕获并记录，不中断整批任务。
        结果每处理一张立即写入磁盘（断点续传保护）。

        Args:
            image_dir:    数据集根目录
            output_file:  结果输出 JSON 文件路径
            resume:       True 时跳过已存在结果的图片（断点续传）

        Returns:
            全部结果列表
        """
        output_file = Path(output_file)

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"无法创建输出目录 {output_file.parent}: {e}") from e

        # 收集图片（目录不存在等硬错误在此抛出，不继续）
        all_items = self.collect_images(image_dir)
        if not all_items:
            logger.warning(f"未找到任何图片，目录: {image_dir}")
            return []

        # 断点续传
        done_names: set[str] = set()
        existing_results: list[dict] = []
        if resume and output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_results = json.load(f)
                done_names = {r["image_name"] for r in existing_results}
                logger.info(f"断点续传：已完成 {len(done_names)} 张，跳过")
            except json.JSONDecodeError as e:
                logger.warning(f"结果文件 JSON 格式损坏，从头开始: {e}")
            except Exception as e:
                logger.warning(f"无法读取已有结果文件，从头开始: {e}")

        todo = [item for item in all_items if item["path"].name not in done_names]

        print(f"\n{'═' * 58}")
        print(f"  Task            : {self.task.upper()}")
        print(f"  Model           : {self.client.current_model}")
        if self.task == "en":
            print(f"  Match threshold : {self.match_threshold}")
        print(f"  数据集目录      : {image_dir}")
        print(f"  总图片数        : {len(all_items)}")
        print(f"  待处理          : {len(todo)}")
        print(f"  输出文件        : {output_file}")
        print(f"{'═' * 58}\n")

        results = list(existing_results)
        error_count = 0

        for idx, item in enumerate(todo, start=1):
            image_path = item["path"]
            gt = item["gt"]
            prompt_type = item["prompt_type"]

            print(
                f"[{idx}/{len(todo)}] [{prompt_type[:3].upper()}] "
                f"{image_path.name}  gt={gt or '?'}",
                end="  ",
                flush=True,
            )

            # ── 单图推断（异常已在 analyze_image 内部捕获）──
            try:
                record = self.analyze_image(str(image_path), gt=gt, prompt_type=prompt_type)
            except Exception as e:
                # 理论上不会走到这里，但作为最后一道防线
                logger.error(f"analyze_image 未预期异常 [{image_path.name}]: {e}")
                record = {
                    "image_name": image_path.name,
                    "image_path": str(image_path),
                    "gt": gt, "pred": None, "inference_chain": None,
                    "raw_response": None, "model": self.client.current_model,
                    "prompt_type": prompt_type, "task": self.task,
                    "success": False, "error": f"未预期异常: {e}",
                }
                if self.task == "ch":
                    record["correct"] = None
                else:
                    record.update({"strict_correct": None, "match_correct": None, "match_score": None})

            results.append(record)

            # 打印行尾状态
            if record.get("error"):
                print(f"ERROR: {record['error']}")
                error_count += 1
            elif self.task == "ch":
                status = "✓" if record.get("correct") else (
                    "✗" if record.get("correct") is False else "?"
                )
                print(f"pred={record['pred'] or 'FAIL'}  {status}")
            else:
                sc = "✓" if record.get("strict_correct") else (
                    "✗" if record.get("strict_correct") is False else "?"
                )
                mc = "✓" if record.get("match_correct") else (
                    "✗" if record.get("match_correct") is False else "?"
                )
                score = record.get("match_score")
                score_str = f"{score:.3f}" if score is not None else "N/A"
                print(
                    f"pred={record['pred'] or 'FAIL'}  "
                    f"strict={sc}  match={mc}({score_str})"
                )

            # ── 实时写入（写入失败不中断，记录警告）──
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"实时写入失败（第{idx}张后）: {e}，继续运行但数据可能未保存")

        # 最终统计
        if error_count > 0:
            print(f"\n⚠️  共有 {error_count} 张图片处理失败，详情见结果 JSON 的 error 字段")

        self._print_summary(results, output_file)

        # 最终确保结果写入一次
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"最终写入失败: {e}")

        return results

    def _print_summary(self, results: list[dict], output_file: Path):
        """打印最终统计信息。"""
        total = len(results)
        success_count = sum(1 for r in results if r.get("success"))
        error_count   = sum(1 for r in results if r.get("error"))

        print(f"\n{'─' * 58}")
        print(f"  总计            : {total} 张")
        print(f"  API 成功        : {success_count}")
        print(f"  处理异常        : {error_count}")
        print(f"  模型            : {self.client.current_model}")

        if self.task == "ch":
            valid = [r for r in results if r.get("gt") is not None]
            correct = sum(1 for r in valid if r.get("correct"))
            acc = correct / len(valid) * 100 if valid else 0.0

            print(f"  有 GT 样本      : {len(valid)}")
            print(f"  正确数          : {correct}")
            print(f"  准确率          : {acc:.2f}%")
            print(f"  ── 细分准确率 ──────────────────────────────")
            for pt in ("sequential", "freeform", "guided"):
                pt_valid = [r for r in valid if r.get("prompt_type") == pt]
                if pt_valid:
                    pt_correct = sum(1 for r in pt_valid if r.get("correct"))
                    pct = pt_correct / len(pt_valid) * 100
                    print(f"  {pt:<14}: {pt_correct}/{len(pt_valid)} ({pct:.1f}%)")

        else:
            valid = [r for r in results if r.get("gt") is not None]
            strict_correct = sum(1 for r in valid if r.get("strict_correct"))
            match_correct  = sum(1 for r in valid if r.get("match_correct"))
            strict_acc = strict_correct / len(valid) * 100 if valid else 0.0
            match_acc  = match_correct  / len(valid) * 100 if valid else 0.0
            scores = [
                r["match_score"] for r in valid
                if r.get("match_score") is not None
            ]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            print(f"  有 GT 样本      : {len(valid)}")
            print(f"  ── strict_accuracy（标准化精确匹配）────────")
            print(f"  正确数          : {strict_correct}/{len(valid)}")
            print(f"  strict_accuracy : {strict_acc:.2f}%")
            print(f"  ── match_accuracy（模糊匹配 ≥ {self.match_threshold}）────────")
            print(f"  正确数          : {match_correct}/{len(valid)}")
            print(f"  match_accuracy  : {match_acc:.2f}%")
            print(f"  平均 match_score: {avg_score:.4f}")

        print(f"  结果文件        : {output_file}")
        print(f"{'─' * 58}\n")

    # ══════════════════════════════════════════════════════
    #  便捷接口
    # ══════════════════════════════════════════════════════

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
        print(f"  Task            : {self.task.upper()}")
        if self.task == "en":
            print(f"  Match threshold : {self.match_threshold}")

    def __repr__(self):
        return (
            f"GuessBenchmarkAnalyzer("
            f"task={self.task!r}, "
            f"model={self.client.current_model!r}, "
            f"provider={self.client.current_provider!r})"
        )


# ══════════════════════════════════════════════════════════
#  命令行入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="GuessBenchmark 批量推断（支持中文/英文双任务）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 中文成语，gpt-4o
  python guess_bench_analyzer.py \\
      --task ch \\
      --image_dir /path/to/variants_chinese/sequential/ \\
      --output results/ch_gpt4o.json

  # 英文 idiom，gpt-4o，默认模糊阈值 0.85
  python guess_bench_analyzer.py \\
      --task en \\
      --image_dir /path/to/variants_english/sequential/ \\
      --output results/en_gpt4o.json

  # 英文 idiom，自定义模糊阈值 0.75
  python guess_bench_analyzer.py \\
      --task en \\
      --image_dir /path/to/variants_english/sequential/ \\
      --output results/en_gpt4o.json \\
      --match_threshold 0.75

  # 禁用断点续传，从头重跑
  python guess_bench_analyzer.py \\
      --task ch \\
      --image_dir /path/to/variants_chinese/sequential/ \\
      --output results/ch_gpt4o.json \\
      --no_resume
        """,
    )

    parser.add_argument(
        "--task", required=True, choices=["ch", "en"],
        help="数据集类型：ch=中文成语，en=英文idiom",
    )
    parser.add_argument("--image_dir",        required=True,  help="数据集根目录")
    parser.add_argument("--output",           required=True,  help="输出 JSON 文件路径")
    parser.add_argument("--model",            default="gpt-4o", help="模型名称（默认 gpt-4o）")
    parser.add_argument("--provider",         default=None,   help="API provider（默认读 config.env）")
    parser.add_argument("--config",           default="config.env", help="配置文件路径")
    parser.add_argument("--no_resume",        action="store_true",  help="禁用断点续传，从头重跑")
    parser.add_argument("--max_tokens",       type=int,   default=512,  help="最大生成 token 数")
    parser.add_argument("--temperature",      type=float, default=0.2,  help="采样温度")
    parser.add_argument(
        "--match_threshold", type=float, default=DEFAULT_MATCH_THRESHOLD,
        help=f"英文模糊匹配阈值，0.0~1.0（默认 {DEFAULT_MATCH_THRESHOLD}）",
    )

    args = parser.parse_args()

    analyzer = GuessBenchmarkAnalyzer(
        model=args.model,
        task=args.task,
        provider=args.provider,
        config_file=args.config,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        match_threshold=args.match_threshold,
    )
    analyzer.print_status()

    analyzer.analyze_batch(
        image_dir=args.image_dir,
        output_file=args.output,
        resume=not args.no_resume,
    )