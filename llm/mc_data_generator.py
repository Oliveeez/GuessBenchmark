"""
mc_options_generator.py
Multiple-Choice 选项中间文件生成器

职责：
- 读取含 distractors 的 JSON（_with_distractors.json）
- 对每个 idiom：取前 3 个 distractor + GT，随机打乱分配 A/B/C/D
- 输出中间文件 mc_options.json，供 MC 实验脚本使用

输出格式：
[
    {
        "idiom_index": 1,
        "idiom": "一心一意",
        "options": {
            "A": "三心二意",
            "B": "一心一意",
            "C": "坐享其成",
            "D": "画蛇添足"
        },
        "gt_option": "B"
    },
    ...
]

使用示例：
  # 中文
  python mc_options_generator.py \\
      --task ch \\
      --source ../data_generation/chinese_idiom_complete_with_distractors.json

  # 英文
  python mc_options_generator.py \\
      --task en \\
      --source ../data_multi_language_section/English/filtered_json/Eng_Idioms_with_distractors.json

  # 指定输出路径
  python mc_options_generator.py \\
      --task ch \\
      --source ../data_generation/chinese_idiom_complete_with_distractors.json \\
      --output ../data_generation/mc_options_ch.json

  # 固定随机种子（可复现）
  python mc_options_generator.py \\
      --task ch \\
      --source ../data_generation/chinese_idiom_complete_with_distractors.json \\
      --seed 42
"""

import json
import random
import logging
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

TaskType = Literal["ch", "en"]

OPTION_LABELS = ["A", "B", "C", "D"]


def generate_mc_options(
    source_path: str,
    task: TaskType,
    output_path: Optional[str] = None,
    seed: Optional[int] = 42,
    start_index: int = 1,
    end_index: Optional[int] = None,
) -> list[dict]:
    """
    读取 _with_distractors.json，为每个 idiom 生成 A/B/C/D 选项。

    策略：
    - 取 distractors 列表的前 3 个作为干扰项
    - 加上 GT idiom 本身，共 4 个候选
    - 随机打乱后分配到 A/B/C/D
    - 记录 GT 对应的选项字母

    Args:
        source_path:  含 distractors 的 JSON 文件路径
        task:         "ch" 或 "en"
        output_path:  输出文件路径（默认：源文件同目录下 mc_options_{task}.json）
        seed:         随机种子（None 则不固定）
        start_index:  起始 idiom_index（含）
        end_index:    终止 idiom_index（含）

    Returns:
        生成的 MC 选项列表
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"数据源文件不存在: {source_path}")

    # 确定输出路径
    if output_path is None:
        output_path = source_path.parent / f"mc_options_{task}.json"
    else:
        output_path = Path(output_path)

    # 设置随机种子
    if seed is not None:
        random.seed(seed)
        print(f"🎲 随机种子: {seed}")

    # 加载数据
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ 已加载数据源: {source_path}，共 {len(data)} 条")

    # 逐条生成选项
    mc_options = []
    skipped_no_distractor = 0
    skipped_out_of_range = 0

    for item in data:
        idiom_index = item.get("idiom_index", 0)
        idiom = item.get("idiom", "")

        # 范围过滤
        if idiom_index < start_index:
            skipped_out_of_range += 1
            continue
        if end_index is not None and idiom_index > end_index:
            skipped_out_of_range += 1
            continue

        # 检查 distractors
        distractors = item.get("distractors", [])
        if not isinstance(distractors, list) or len(distractors) < 3:
            logger.warning(
                f"idiom_index={idiom_index} '{idiom}' 的 distractors 不足 3 个 "
                f"（实际 {len(distractors)}），跳过"
            )
            skipped_no_distractor += 1
            continue

        # 取前 3 个 distractor + GT
        selected_distractors = distractors[:3]
        candidates = selected_distractors + [idiom]

        # 随机打乱
        random.shuffle(candidates)

        # 分配 A/B/C/D
        options = {}
        gt_option = None
        for label, candidate in zip(OPTION_LABELS, candidates):
            options[label] = candidate
            if candidate == idiom:
                gt_option = label

        if gt_option is None:
            # 理论上不会走到这里，作为防御性检查
            logger.error(
                f"idiom_index={idiom_index} '{idiom}' 无法找到 GT 选项，跳过"
            )
            continue

        mc_options.append({
            "idiom_index": idiom_index,
            "idiom": idiom,
            "options": options,
            "gt_option": gt_option,
        })

    # 写入输出文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mc_options, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"\n{'─' * 58}")
    print(f"  任务类型            : {task.upper()}")
    print(f"  数据源              : {source_path}")
    print(f"  数据总量            : {len(data)}")
    print(f"  范围过滤跳过        : {skipped_out_of_range}")
    print(f"  distractors 不足跳过: {skipped_no_distractor}")
    print(f"  成功生成            : {len(mc_options)}")
    print(f"  输出文件            : {output_path}")
    print(f"{'─' * 58}")

    # GT 选项分布统计
    dist = {label: 0 for label in OPTION_LABELS}
    for entry in mc_options:
        dist[entry["gt_option"]] += 1
    print(f"\n  GT 选项分布:")
    for label in OPTION_LABELS:
        pct = dist[label] / len(mc_options) * 100 if mc_options else 0
        print(f"    {label}: {dist[label]} ({pct:.1f}%)")
    print()

    return mc_options


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
        description="为 MC 实验生成 A/B/C/D 选项中间文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 中文
  python mc_options_generator.py \\
      --task ch \\
      --source ../data_generation/chinese_idiom_complete_with_distractors.json

  # 英文
  python mc_options_generator.py \\
      --task en \\
      --source ../data_multi_language_section/English/filtered_json/Eng_Idioms_with_distractors.json

  # 指定输出路径和随机种子
  python mc_options_generator.py \\
      --task ch \\
      --source ../data_generation/chinese_idiom_complete_with_distractors.json \\
      --output ../data_generation/mc_options_ch.json \\
      --seed 42
        """,
    )

    parser.add_argument(
        "--task", required=True, choices=["ch", "en"],
        help="数据集类型：ch=中文成语，en=英文idiom",
    )
    parser.add_argument(
        "--source", required=True,
        help="含 distractors 的 JSON 文件路径（_with_distractors.json）",
    )
    parser.add_argument(
        "--output", default=None,
        help="输出文件路径（默认：源文件同目录下 mc_options_{task}.json）",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子（默认 42，设为 -1 不固定）",
    )
    parser.add_argument(
        "--start_index", type=int, default=1,
        help="起始 idiom_index（含，默认 1）",
    )
    parser.add_argument(
        "--end_index", type=int, default=None,
        help="终止 idiom_index（含，默认不限）",
    )

    args = parser.parse_args()

    seed = args.seed if args.seed >= 0 else None

    generate_mc_options(
        source_path=args.source,
        task=args.task,
        output_path=args.output,
        seed=seed,
        start_index=args.start_index,
        end_index=args.end_index,
    )