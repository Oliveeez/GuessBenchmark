"""
mc_bench_analyzer_for_experiment.py
Multiple-Choice GuessBenchmark 推断执行器

职责：
- 加载 mc_options.json（由 mc_options_generator.py 生成的 A/B/C/D 选项文件）
- 支持中文（--task ch）和英文（--task en）两种数据集
- 将图片和 4 个候选选项一起发送给 MLLM，让模型选择正确选项
- 从 LLM 响应中解析选项字母（A/B/C/D）和 inference_chain
- 单图和批量推断，结果实时写入 JSON 文件

─── Prompt 设计说明 ─────────────────────────────────────

参考 MMBench、SEED-Bench、MMStar 等主流 benchmark 的 MC 评测 prompt：
- 给出 A/B/C/D 四个选项
- 要求模型输出选项字母 + 简要推理链
- 1-shot 示例示范期望的输出格式

中文（--task ch）：
  - 1-shot 示例：👄👂📷⛴ → C. 口耳相传
    覆盖语义对应（👄→口、👂→耳）和谐音对应（⛴→传），
    示范 MC 格式下的推理和选择过程。
  - inference_chain 限定为中文，保持与 open-ended 一致。

英文（--task en）：
  - 1-shot 示例：🧹💨 → B. clear the air
    覆盖视觉隐喻（🧹→clear/sweep）和语义对应（💨→air），
    示范 MC 格式下的推理和选择过程。

─── 参数说明 ────────────────────────────────────────────

  --mc_options    mc_options.json 文件路径（必需）
  --task          ch / en（必需）
  --image_dir     数据集根目录（必需）
  --output        输出 JSON 文件路径（必需）
  --variant_set   【仅 ch】评测的图片子集：base/pure/guided/all（默认 all）
  --start_index   起始文件夹索引，含（默认 1）
  --end_index     终止文件夹索引，含（默认不限）

─── 目录结构约定 ───────────────────────────────────────────

与 guess_bench_analyzer_for_experiment.py 完全一致，参见该文件头部注释。

─── 输出 JSON 格式 ──────────────────────────────────────────

[
    {
        "image_name": "一心一意_base_v001.png",
        "image_path": "...",
        "gt": "一心一意",
        "gt_option": "C",
        "options": {"A": "三心二意", "B": "坐享其成", "C": "一心一意", "D": "画蛇添足"},
        "pred_option": "C",
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
"""

import json
import logging
import re
import os
from pathlib import Path
from typing import Optional, Literal

from unified_client import UnifiedImageLLMClient, create_client

logger = logging.getLogger(__name__)

TaskType   = Literal["ch", "en"]
VariantSet = Literal["base", "pure", "guided", "all"]

# ══════════════════════════════════════════════════════════
#  Prompt 模板
# ══════════════════════════════════════════════════════════

# ── 中文 MC Prompt ──────────────────────────────────────
#
# Few-shot 设计说明：
#   参照 MMBench、MMStar 等主流 benchmark 的 MC prompt 设计，
#   加入 1 条 MC 格式的 few-shot 示例，示范输出格式和推理方式。
#   示例选用"口耳相传"，包含语义对应（👄→口、👂→耳）
#   和谐音对应（⛴→传/船≈传），覆盖两种映射类型。

_CH_MC_FEW_SHOT = (
    "Here is one example to illustrate the expected format:\n"
    "Emojis: 👄 👂 📷 ⛴\n"
    "Options:\n"
    "A. 薪火相传\n"
    "B. 不可思议\n"
    "C. 口耳相传\n"
    "D. 言传身教\n\n"
    "Output: "
    '{{"answer": "C", "inference_chain": '
    '"👄→口(语义:嘴巴) | 👂→耳(语义:耳朵) | 📷→相(语义:相机/相) | ⛴→传(谐音:船/chuán≈传/chuán)"}}\n\n'
    "Now identify the idiom for the image below.\n"
)

_CH_MC_PROMPT_TEMPLATE = (
    "You are a linguistic expert tasked with identifying Chinese four-character idioms (成语) "
    "based on a set of four emojis. {order_instruction} "
    "Each emoji corresponds to exactly one character in the idiom. The mapping can be either:\n"
    "1) Semantic Match (语义对应): The emoji's meaning aligns with the character's meaning.\n"
    "2) Phonetic Match (谐音对应): The emoji's Chinese name (pinyin) matches or closely "
    "resembles the character's pronunciation.\n\n"
    + _CH_MC_FEW_SHOT
    + "Options:\n"
    "A. {option_A}\n"
    "B. {option_B}\n"
    "C. {option_C}\n"
    "D. {option_D}\n\n"
    "Select the correct idiom from the options above. "
    "You MUST output a single JSON object with NO additional text. "
    "The answer field must be exactly one letter: A, B, C, or D. "
    "Use Chinese for the inference_chain. "
    "Format inference_chain as: emoji→字(类型:理由) for each emoji, joined by ' | '. "
    "Keep inference_chain under 100 characters.\n"
    '{{"answer": "A/B/C/D", "inference_chain": "emoji→字(类型:理由) | ..."}}'
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

_CH_MC_SYSTEM_PROMPT = (
    "You are an expert in Chinese linguistics and culture. "
    "Always respond with a single valid JSON object, no markdown, no extra text. "
    "The answer field must contain exactly one uppercase letter: A, B, C, or D. "
    "The inference_chain field must be written in Chinese."
)

# ── 英文 MC Prompt ──────────────────────────────────────
#
# Few-shot 设计说明：
#   示例选用 "clear the air"，覆盖视觉隐喻映射（🧹→clear：扫帚代表清扫/清除）
#   和语义直接对应（💨→air），示范 MC 格式下的推理和选择过程。

_EN_MC_FEW_SHOT = (
    "Here is one example to illustrate the expected format:\n"
    "Emojis: 🧹 💨\n"
    "Options:\n"
    "A. break the ice\n"
    "B. clear the air\n"
    "C. up in the air\n"
    "D. bite the bullet\n\n"
    "Output: "
    '{{"answer": "B", "inference_chain": '
    '"🧹→clear (metaphor: a broom represents sweeping/clearing) | '
    '💨→air (semantic: air/wind)"}}\n\n'
    "Now identify the idiom for the image below.\n"
)

_EN_MC_PROMPT_TEMPLATE = (
    "You are a linguistic expert tasked with identifying an English idiom based on a set of emojis. "
    "The emojis are arranged horizontally from left to right. "
    "The emojis collectively hint at the idiom. Each emoji may:\n"
    "1) Directly represent a word in the idiom (Semantic Match).\n"
    "2) Serve as a visual metaphor for the overall theme or a key concept of the idiom.\n\n"
    + _EN_MC_FEW_SHOT
    + "Options:\n"
    "A. {option_A}\n"
    "B. {option_B}\n"
    "C. {option_C}\n"
    "D. {option_D}\n\n"
    "Select the correct idiom from the options above. "
    "You MUST output a single JSON object with NO additional text. "
    "The answer field must be exactly one letter: A, B, C, or D.\n"
    '{{"answer": "A/B/C/D", "inference_chain": "emoji→word (type: reason) | ..."}}'
)

_EN_MC_SYSTEM_PROMPT = (
    "You are an expert in English linguistics and idiomatic expressions. "
    "Always respond with a single valid JSON object, no markdown, no extra text. "
    "The answer field must contain exactly one uppercase letter: A, B, C, or D."
)


# ══════════════════════════════════════════════════════════
#  核心类
# ══════════════════════════════════════════════════════════

class MCBenchmarkAnalyzer:
    """
    Multiple-Choice GuessBenchmark 推断执行器（支持中/英文双任务）

    使用示例：
        # 中文 MC 批量推断
        analyzer = MCBenchmarkAnalyzer(model="gpt-4o", task="ch")
        analyzer.analyze_batch(
            image_dir="variants_chinese/sequential/",
            mc_options_file="mc_options_ch.json",
            output_file="results/mc_ch_gpt4o.json",
        )

        # 英文 MC 批量推断
        analyzer = MCBenchmarkAnalyzer(model="gpt-4o", task="en")
        analyzer.analyze_batch(
            image_dir="variants_english/sequential/",
            mc_options_file="mc_options_en.json",
            output_file="results/mc_en_gpt4o.json",
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
    ):
        if task not in ("ch", "en"):
            raise ValueError(f"task 必须为 'ch' 或 'en'，得到: {task!r}")

        self.task: TaskType = task
        self.client: UnifiedImageLLMClient = create_client(
            model=model,
            provider=provider,
            config_file=config_file,
        )
        self.max_tokens = max_tokens
        self.temperature = temperature

        # MC 选项映射表：idiom → {options, gt_option}
        self._mc_map: dict[str, dict] = {}

        logger.info(
            f"MCBenchmarkAnalyzer 初始化完成: task={task}, {self.client}"
        )

    # ══════════════════════════════════════════════════════
    #  MC 选项加载
    # ══════════════════════════════════════════════════════

    def load_mc_options(self, mc_options_file: str):
        """
        加载 mc_options.json，建立 idiom → 选项的映射。

        映射 key 处理：
        - 中文：idiom 原文（如 "一心一意"）
        - 英文：统一小写（如 "trade off"）
        """
        mc_path = Path(mc_options_file)
        if not mc_path.exists():
            raise FileNotFoundError(f"MC 选项文件不存在: {mc_options_file}")

        with open(mc_path, "r", encoding="utf-8") as f:
            mc_data = json.load(f)

        self._mc_map.clear()
        for entry in mc_data:
            idiom = entry["idiom"]
            key = idiom if self.task == "ch" else idiom.lower().strip()
            self._mc_map[key] = {
                "options": entry["options"],
                "gt_option": entry["gt_option"],
            }

        logger.info(f"已加载 MC 选项: {len(self._mc_map)} 条 ({mc_path})")

    def _get_mc_options(self, gt: str) -> Optional[dict]:
        """根据 GT idiom 查找对应的 MC 选项。"""
        key = gt if self.task == "ch" else gt.lower().strip()
        return self._mc_map.get(key)

    # ══════════════════════════════════════════════════════
    #  Prompt 生成
    # ══════════════════════════════════════════════════════

    @staticmethod
    def build_ch_prompt(prompt_type: str, options: dict) -> tuple[str, str]:
        """生成中文 MC 任务的 (prompt, system_prompt)。"""
        order_instr = _CH_ORDER_INSTRUCTIONS.get(
            prompt_type, _CH_ORDER_INSTRUCTIONS["sequential"]
        )
        prompt = _CH_MC_PROMPT_TEMPLATE.format(
            order_instruction=order_instr,
            option_A=options["A"],
            option_B=options["B"],
            option_C=options["C"],
            option_D=options["D"],
        )
        return prompt, _CH_MC_SYSTEM_PROMPT

    @staticmethod
    def build_en_prompt(options: dict) -> tuple[str, str]:
        """生成英文 MC 任务的 (prompt, system_prompt)。"""
        prompt = _EN_MC_PROMPT_TEMPLATE.format(
            option_A=options["A"],
            option_B=options["B"],
            option_C=options["C"],
            option_D=options["D"],
        )
        return prompt, _EN_MC_SYSTEM_PROMPT

    def build_prompt(
        self,
        prompt_type: str,
        options: dict,
    ) -> tuple[str, str]:
        """根据当前 task 生成对应 MC prompt。"""
        if self.task == "ch":
            return self.build_ch_prompt(prompt_type, options)
        else:
            return self.build_en_prompt(options)

    # ══════════════════════════════════════════════════════
    #  响应解析
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _extract_mc_answer(response: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 LLM 响应中提取选项字母和推理链。

        解析顺序：
        1. JSON 解析（含 markdown 代码块处理）
        2. 正则回退：匹配 "answer": "X" 或独立的 A/B/C/D

        Returns:
            (answer_letter, inference_chain)
            answer_letter: "A" / "B" / "C" / "D" 或 None
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
                    answer = data.get("answer", "").strip().upper()
                    chain = data.get("inference_chain", "")
                    if answer in ("A", "B", "C", "D"):
                        return answer, chain
                except json.JSONDecodeError:
                    pass

            # 正则回退 1：匹配 "answer" 字段
            logger.warning("JSON 解析失败，使用正则回退提取 MC answer")
            answer_match = re.search(
                r'"?answer"?\s*[:：]\s*"?([A-Da-d])"?', text
            )
            if answer_match:
                return answer_match.group(1).upper(), None

            # 正则回退 2：匹配独立的单字母（句首或行首的 A/B/C/D）
            letter_match = re.search(r'\b([A-D])\b', text)
            if letter_match:
                return letter_match.group(1).upper(), None

        except Exception as e:
            logger.error(f"_extract_mc_answer 解析异常: {e}")

        return None, None

    # ══════════════════════════════════════════════════════
    #  GT 解析工具（复用 open-ended 版本的逻辑）
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

    @staticmethod
    def _parse_folder_index(folder_name: str) -> Optional[int]:
        """从文件夹名称解析整数前缀索引。"""
        try:
            return int(folder_name.split("_", 1)[0])
        except (ValueError, IndexError):
            return None

    # ══════════════════════════════════════════════════════
    #  图片收集（与 open-ended 版本逻辑一致）
    # ══════════════════════════════════════════════════════

    def _collect_images_ch(
        self,
        image_dir: str,
        variant_set: str = "all",
        start_index: int = 1,
        end_index: Optional[int] = None,
    ) -> list[dict]:
        """
        遍历中文数据集目录，收集符合条件的图片及元数据。
        逻辑与 guess_bench_analyzer_for_experiment.py 中完全一致。
        """
        root = Path(image_dir)

        if not root.exists():
            raise FileNotFoundError(f"中文数据集目录不存在: {image_dir}")
        if not root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {image_dir}")

        items = []
        idiom_folders = sorted(
            [p for p in root.iterdir() if p.is_dir()],
            key=lambda p: self._parse_folder_index(p.name) or float("inf"),
        )

        for idiom_folder in idiom_folders:
            folder_idx = self._parse_folder_index(idiom_folder.name)
            if folder_idx is None:
                logger.warning(f"无法解析文件夹索引，跳过: {idiom_folder.name}")
                continue
            if folder_idx < start_index:
                continue
            if end_index is not None and folder_idx > end_index:
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
                if variant_set in ("base", "all"):
                    for f in sorted(set_dir.glob("*.png")):
                        if "v001" in f.stem:
                            items.append({"path": f, "gt": gt, "prompt_type": "sequential"})

                if variant_set in ("pure", "all"):
                    pure_dir = set_dir / "seq_varients_pure"
                    if pure_dir.is_dir():
                        for f in sorted(pure_dir.glob("*.png")):
                            if variant_set == "all" or "v002" in f.stem or "v003" in f.stem:
                                items.append({"path": f, "gt": gt, "prompt_type": "freeform"})

                if variant_set in ("guided", "all"):
                    guide_dir = set_dir / "seq_varients_with_guideance"
                    if guide_dir.is_dir():
                        for f in sorted(guide_dir.glob("*.png")):
                            if variant_set == "all" or "v004" in f.stem or "v005" in f.stem:
                                items.append({"path": f, "gt": gt, "prompt_type": "guided"})
            except Exception as e:
                logger.error(f"遍历子目录失败 [{idiom_folder}]: {e}，跳过此成语")
                continue

        logger.info(
            f"中文数据集：共收集 {len(items)} 张图片 "
            f"(variant_set={variant_set}, index={start_index}~{end_index or 'end'})"
        )
        return items

    def _collect_images_en(
        self,
        image_dir: str,
        start_index: int = 1,
        end_index: Optional[int] = None,
    ) -> list[dict]:
        """
        遍历英文数据集目录，收集符合条件的图片及元数据。
        逻辑与 guess_bench_analyzer_for_experiment.py 中完全一致。
        """
        root = Path(image_dir)

        if not root.exists():
            raise FileNotFoundError(f"英文数据集目录不存在: {image_dir}")
        if not root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {image_dir}")

        items = []
        idiom_folders = sorted(
            [p for p in root.iterdir() if p.is_dir()],
            key=lambda p: self._parse_folder_index(p.name) or float("inf"),
        )

        for idiom_folder in idiom_folders:
            folder_idx = self._parse_folder_index(idiom_folder.name)
            if folder_idx is None:
                logger.warning(f"无法解析文件夹索引，跳过: {idiom_folder.name}")
                continue
            if folder_idx < start_index:
                continue
            if end_index is not None and folder_idx > end_index:
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

        logger.info(
            f"英文数据集：共收集 {len(items)} 张图片 "
            f"(index={start_index}~{end_index or 'end'})"
        )
        return items

    def collect_images(
        self,
        image_dir: str,
        variant_set: str = "all",
        start_index: int = 1,
        end_index: Optional[int] = None,
    ) -> list[dict]:
        """根据当前 task 收集符合条件的图片。"""
        if self.task == "ch":
            return self._collect_images_ch(
                image_dir, variant_set=variant_set,
                start_index=start_index, end_index=end_index,
            )
        else:
            return self._collect_images_en(
                image_dir, start_index=start_index, end_index=end_index,
            )

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
        对单张图片进行 MC 推断。

        任何异常都会被捕获并记录在 record["error"] 字段中，
        不会向上抛出，确保批量任务不因单张图片失败而中断。
        """
        image_name = Path(image_path).name

        # 查找 MC 选项
        mc_info = self._get_mc_options(gt) if gt else None

        def _failed_record(error_msg: str) -> dict:
            return {
                "image_name": image_name,
                "image_path": str(image_path),
                "gt": gt,
                "gt_option": mc_info["gt_option"] if mc_info else None,
                "options": mc_info["options"] if mc_info else None,
                "pred_option": None,
                "inference_chain": None,
                "raw_response": None,
                "model": self.client.current_model,
                "prompt_type": prompt_type,
                "task": self.task,
                "success": False,
                "correct": None,
                "error": error_msg,
            }

        if mc_info is None:
            return _failed_record(f"MC 选项文件中未找到对应 GT: {gt!r}")

        options = mc_info["options"]
        gt_option = mc_info["gt_option"]

        # ── 构建 Prompt ──────────────────────────────────
        try:
            prompt, system_prompt = self.build_prompt(prompt_type, options)
        except Exception as e:
            logger.error(f"build_prompt 异常 [{image_name}]: {e}")
            return _failed_record(f"prompt构建失败: {e}")

        # ── API 调用 ────────────────────────────────────
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
            pred_option, chain = self._extract_mc_answer(response)
        except Exception as e:
            logger.error(f"响应解析异常 [{image_name}]: {e}")
            pred_option, chain = None, None

        success = pred_option is not None

        record = {
            "image_name": image_name,
            "image_path": str(image_path),
            "gt": gt,
            "gt_option": gt_option,
            "options": options,
            "pred_option": pred_option,
            "inference_chain": chain,
            "raw_response": response,
            "model": self.client.current_model,
            "prompt_type": prompt_type,
            "task": self.task,
            "success": success,
            "correct": (pred_option == gt_option) if (pred_option and gt_option) else None,
            "error": None,
        }

        return record

    # ══════════════════════════════════════════════════════
    #  批量推断
    # ══════════════════════════════════════════════════════

    def analyze_batch(
        self,
        image_dir: str,
        mc_options_file: str,
        output_file: str,
        resume: bool = True,
        variant_set: str = "all",
        start_index: int = 1,
        end_index: Optional[int] = None,
    ) -> list[dict]:
        """
        批量 MC 推断整个数据集目录。

        单张图片的任何异常均被捕获并记录，不中断整批任务。
        结果每处理一张立即写入磁盘（断点续传保护）。

        Args:
            image_dir:       数据集根目录
            mc_options_file: MC 选项 JSON 文件路径
            output_file:     结果输出 JSON 文件路径
            resume:          True 时跳过已存在结果的图片（断点续传）
            variant_set:     图片子集（仅 ch 有效）
            start_index:     起始文件夹索引，含
            end_index:       终止文件夹索引，含
        """
        output_file = Path(output_file)

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"无法创建输出目录 {output_file.parent}: {e}") from e

        # 加载 MC 选项
        self.load_mc_options(mc_options_file)

        # 收集图片
        all_items = self.collect_images(
            image_dir,
            variant_set=variant_set,
            start_index=start_index,
            end_index=end_index,
        )
        if not all_items:
            logger.warning(f"未找到任何图片，目录: {image_dir}")
            return []

        # 检查 MC 选项覆盖率
        missing_gt = set()
        for item in all_items:
            gt = item["gt"]
            if self._get_mc_options(gt) is None:
                missing_gt.add(gt)
        if missing_gt:
            logger.warning(
                f"⚠️  有 {len(missing_gt)} 个 idiom 在 MC 选项文件中未找到，"
                f"相关图片将跳过。示例: {list(missing_gt)[:5]}"
            )

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

        idx_range_str = f"{start_index} ~ {end_index if end_index is not None else 'end'}"
        print(f"\n{'═' * 58}")
        print(f"  Task            : {self.task.upper()} (Multiple-Choice)")
        print(f"  Model           : {self.client.current_model}")
        if self.task == "ch":
            print(f"  Variant set     : {variant_set}")
        print(f"  Index range     : {idx_range_str}")
        print(f"  MC 选项文件     : {mc_options_file}")
        print(f"  MC 选项数       : {len(self._mc_map)}")
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

            # 获取 GT 选项字母用于打印
            mc_info = self._get_mc_options(gt)
            gt_label = mc_info["gt_option"] if mc_info else "?"

            print(
                f"[{idx}/{len(todo)}] [{prompt_type[:3].upper()}] "
                f"{image_path.name}  gt={gt or '?'}({gt_label})",
                end="  ",
                flush=True,
            )

            # ── 单图推断 ──
            try:
                record = self.analyze_image(str(image_path), gt=gt, prompt_type=prompt_type)
            except Exception as e:
                logger.error(f"analyze_image 未预期异常 [{image_path.name}]: {e}")
                record = {
                    "image_name": image_path.name,
                    "image_path": str(image_path),
                    "gt": gt,
                    "gt_option": gt_label,
                    "options": mc_info["options"] if mc_info else None,
                    "pred_option": None,
                    "inference_chain": None,
                    "raw_response": None,
                    "model": self.client.current_model,
                    "prompt_type": prompt_type,
                    "task": self.task,
                    "success": False,
                    "correct": None,
                    "error": f"未预期异常: {e}",
                }

            results.append(record)

            # 打印行尾状态
            if record.get("error"):
                print(f"ERROR: {record['error']}")
                error_count += 1
            else:
                pred = record.get("pred_option") or "FAIL"
                status = "✓" if record.get("correct") else (
                    "✗" if record.get("correct") is False else "?"
                )
                print(f"pred={pred}  {status}")

            # ── 实时写入 ──
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

        valid = [r for r in results if r.get("gt_option") is not None]
        correct = sum(1 for r in valid if r.get("correct"))
        acc = correct / len(valid) * 100 if valid else 0.0

        print(f"\n{'─' * 58}")
        print(f"  总计            : {total} 张")
        print(f"  API 成功        : {success_count}")
        print(f"  处理异常        : {error_count}")
        print(f"  模型            : {self.client.current_model}")
        print(f"  有 GT 样本      : {len(valid)}")
        print(f"  正确数          : {correct}")
        print(f"  准确率          : {acc:.2f}%")

        if self.task == "ch":
            print(f"  ── 按 prompt_type 细分 ────────────────────")
            for pt in ("sequential", "freeform", "guided"):
                pt_valid = [r for r in valid if r.get("prompt_type") == pt]
                if pt_valid:
                    pt_correct = sum(1 for r in pt_valid if r.get("correct"))
                    pct = pt_correct / len(pt_valid) * 100
                    print(f"  {pt:<14}: {pt_correct}/{len(pt_valid)} ({pct:.1f}%)")

        # 选项分布统计（分析 position bias）
        print(f"  ── 模型选项分布（position bias 分析）────────")
        pred_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "FAIL": 0}
        for r in valid:
            p = r.get("pred_option")
            if p in pred_dist:
                pred_dist[p] += 1
            else:
                pred_dist["FAIL"] += 1
        for label in ["A", "B", "C", "D", "FAIL"]:
            count = pred_dist[label]
            pct = count / len(valid) * 100 if valid else 0
            print(f"    {label:4}: {count} ({pct:.1f}%)")

        print(f"  结果文件        : {output_file}")
        print(f"{'─' * 58}\n")

    # ══════════════════════════════════════════════════════
    #  便捷接口
    # ══════════════════════════════════════════════════════

    def switch_model(self, model: str) -> "MCBenchmarkAnalyzer":
        """切换模型（返回 self，支持链式调用）"""
        self.client.switch_model(model)
        return self

    def switch_provider(self, provider: str) -> "MCBenchmarkAnalyzer":
        """切换 provider（返回 self，支持链式调用）"""
        self.client.switch_provider(provider)
        return self

    def print_status(self):
        """打印当前配置状态"""
        self.client.print_status()
        print(f"  Task            : {self.task.upper()} (MC)")
        print(f"  MC options      : {len(self._mc_map)} loaded")

    def __repr__(self):
        return (
            f"MCBenchmarkAnalyzer("
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
        description="Multiple-Choice GuessBenchmark 批量推断（支持中文/英文双任务）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 中文成语 MC，全部五张，gpt-4o
  python mc_bench_analyzer_for_experiment.py \\
      --task ch \\
      --image_dir /path/to/variants_chinese/ \\
      --mc_options /path/to/mc_options_ch.json \\
      --output results/mc_ch_gpt4o_all.json

  # 中文成语 MC，仅 base 图（v001），索引 1~100
  python mc_bench_analyzer_for_experiment.py \\
      --task ch --variant_set base \\
      --start_index 1 --end_index 100 \\
      --image_dir /path/to/variants_chinese/ \\
      --mc_options /path/to/mc_options_ch.json \\
      --output results/mc_ch_gpt4o_base_1to100.json

  # 英文 idiom MC
  python mc_bench_analyzer_for_experiment.py \\
      --task en \\
      --image_dir /path/to/variants_english/ \\
      --mc_options /path/to/mc_options_en.json \\
      --output results/mc_en_gpt4o.json

  # 禁用断点续传，从头重跑
  python mc_bench_analyzer_for_experiment.py \\
      --task ch \\
      --image_dir /path/to/variants_chinese/ \\
      --mc_options /path/to/mc_options_ch.json \\
      --output results/mc_ch_gpt4o.json \\
      --no_resume
        """,
    )

    parser.add_argument(
        "--task", required=True, choices=["ch", "en"],
        help="数据集类型：ch=中文成语，en=英文idiom",
    )
    parser.add_argument("--image_dir",    required=True, help="数据集根目录")
    parser.add_argument("--mc_options",   required=True, help="MC 选项 JSON 文件路径（mc_options_generator.py 输出）")
    parser.add_argument("--output",       required=True, help="输出 JSON 文件路径")
    parser.add_argument("--model",        default="gpt-4o", help="模型名称（默认 gpt-4o）")
    parser.add_argument("--provider",     default=None,  help="API provider（默认读 config.env）")
    parser.add_argument("--config",       default="config.env", help="配置文件路径")
    parser.add_argument("--no_resume",    action="store_true", help="禁用断点续传，从头重跑")
    parser.add_argument("--max_tokens",   type=int,   default=512, help="最大生成 token 数")
    parser.add_argument("--temperature",  type=float, default=0.2, help="采样温度")
    parser.add_argument(
        "--variant_set",
        choices=["base", "pure", "guided", "all"],
        default="all",
        help=(
            "【仅 --task ch 有效】评测的图片子集（默认 all）：\n"
            "  base   - 仅 v001 基础图（sequential prompt）\n"
            "  pure   - 仅 v002、v003（freeform prompt）\n"
            "  guided - 仅 v004、v005（guided prompt）\n"
            "  all    - 全部五张（默认）"
        ),
    )
    parser.add_argument(
        "--start_index", type=int, default=1,
        help="起始文件夹索引，含（默认 1）",
    )
    parser.add_argument(
        "--end_index", type=int, default=None,
        help="终止文件夹索引，含（默认不限，跑全部）",
    )

    args = parser.parse_args()

    analyzer = MCBenchmarkAnalyzer(
        model=args.model,
        task=args.task,
        provider=args.provider,
        config_file=args.config,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    analyzer.print_status()

    analyzer.analyze_batch(
        image_dir=args.image_dir,
        mc_options_file=args.mc_options,
        output_file=args.output,
        resume=not args.no_resume,
        variant_set=args.variant_set,
        start_index=args.start_index,
        end_index=args.end_index,
    )