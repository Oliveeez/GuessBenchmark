"""
evaluate_mc.py
Multiple-Choice 实验结果评估器

职责：
- 读取 MC 任务的中文/英文结果 JSON
- 自动检测 task 类型（ch/en）
- 计算论文所需的全部指标（含 position bias 分析）
- 输出结构化评估报告 JSON

─── 指标说明 ────────────────────────────────────────────

通用：
  - accuracy:               整体准确率
  - total / success / error / valid 数量
  - parse_failure_rate:     LLM 响应解析失败率（success 但 pred_option 为 None）

中文（ch）额外：
  - per_prompt_type:        按 prompt_type (sequential/freeform/guided) 细分准确率

Position Bias 分析（MC 论文必备）：
  - gt_option_distribution:   GT 选项分布（验证选项均匀性）
  - pred_option_distribution: 模型预测选项分布（揭示选项偏好）
  - per_option_accuracy:      每个选项位置（A/B/C/D）上 GT 对应的准确率
  - position_bias_std:        选项准确率的标准差（越大说明 bias 越严重）

Confusion Matrix：
  - confusion_matrix:         GT option × Pred option 的计数矩阵

─── 使用示例 ────────────────────────────────────────────

  python evaluate_mc.py results/mc_ch_gpt4o_base.json
  python evaluate_mc.py results/mc_ch_*.json results/mc_en_*.json
  python evaluate_mc.py results/mc_en_gpt4o.json --output_dir my_eval/
"""

import json
import math
import sys
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OPTION_LABELS = ["A", "B", "C", "D"]


# ══════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════

def _detect_task(data: list[dict]) -> Optional[str]:
    """自动检测 task 类型。"""
    for item in data:
        task = item.get("task")
        if task in ("ch", "en"):
            return task
    return None


# ══════════════════════════════════════════════════════════
#  核心评估逻辑
# ══════════════════════════════════════════════════════════

def _evaluate_mc(data: list[dict], task: str) -> dict:
    """评估 MC 结果（中英文通用逻辑 + ch 额外 prompt_type 细分）。"""
    total = len(data)
    success = sum(1 for r in data if r.get("success"))
    errors = sum(1 for r in data if r.get("error"))
    valid = [r for r in data if r.get("gt_option") is not None and r.get("success")]
    parse_failures = sum(
        1 for r in data if r.get("success") and r.get("pred_option") is None
    )

    correct = sum(1 for r in valid if r.get("correct"))
    accuracy = correct / len(valid) if valid else 0.0

    # ── GT 选项分布 ──
    gt_dist = Counter(r.get("gt_option") for r in valid)
    gt_option_distribution = {
        label: gt_dist.get(label, 0) for label in OPTION_LABELS
    }

    # ── 模型预测选项分布 ──
    pred_dist = Counter()
    for r in valid:
        p = r.get("pred_option")
        if p in OPTION_LABELS:
            pred_dist[p] += 1
        else:
            pred_dist["INVALID"] += 1
    pred_option_distribution = {
        label: pred_dist.get(label, 0) for label in OPTION_LABELS
    }
    pred_option_distribution["INVALID"] = pred_dist.get("INVALID", 0)

    # ── 每个选项位置的准确率（Position Bias 核心指标）──
    per_option_accuracy = {}
    per_option_acc_values = []
    for label in OPTION_LABELS:
        items_at_pos = [r for r in valid if r.get("gt_option") == label]
        if items_at_pos:
            corr = sum(1 for r in items_at_pos if r.get("correct"))
            acc = corr / len(items_at_pos)
        else:
            corr = 0
            acc = 0.0
        per_option_accuracy[label] = {
            "total": len(items_at_pos),
            "correct": corr,
            "accuracy": round(acc, 6),
        }
        if items_at_pos:
            per_option_acc_values.append(acc)

    # position bias 标准差
    if len(per_option_acc_values) >= 2:
        mean_acc = sum(per_option_acc_values) / len(per_option_acc_values)
        variance = sum((x - mean_acc) ** 2 for x in per_option_acc_values) / len(per_option_acc_values)
        position_bias_std = round(math.sqrt(variance), 6)
    else:
        position_bias_std = 0.0

    # ── Confusion Matrix：GT option × Pred option ──
    confusion_matrix = {}
    for gt_label in OPTION_LABELS:
        row = {}
        for pred_label in OPTION_LABELS + ["INVALID"]:
            row[pred_label] = 0
        confusion_matrix[gt_label] = row

    for r in valid:
        gt_opt = r.get("gt_option")
        pred_opt = r.get("pred_option")
        if gt_opt in OPTION_LABELS:
            if pred_opt in OPTION_LABELS:
                confusion_matrix[gt_opt][pred_opt] += 1
            else:
                confusion_matrix[gt_opt]["INVALID"] += 1

    # ── 按 prompt_type 细分（ch 有效，en 通常只有 sequential）──
    per_prompt_type = {}
    prompt_types = sorted(set(r.get("prompt_type", "unknown") for r in valid))
    for pt in prompt_types:
        pt_items = [r for r in valid if r.get("prompt_type") == pt]
        pt_correct = sum(1 for r in pt_items if r.get("correct"))
        per_prompt_type[pt] = {
            "total": len(pt_items),
            "correct": pt_correct,
            "accuracy": round(pt_correct / len(pt_items), 6) if pt_items else 0.0,
        }

    # ── 错误分析：模型选错时选的是哪个 distractor ──
    wrong = [r for r in valid if r.get("correct") is False and r.get("pred_option")]
    wrong_chosen_idioms = []
    for r in wrong:
        pred_opt = r.get("pred_option")
        options = r.get("options", {})
        chosen_idiom = options.get(pred_opt, "unknown")
        wrong_chosen_idioms.append(chosen_idiom)
    wrong_idiom_counter = Counter(wrong_chosen_idioms)
    top_wrong_chosen = wrong_idiom_counter.most_common(20)

    # ── distractor 类型分析（如果 distractor 有类型信息，此处统计错选分布）──
    # 简化版：统计错选时 pred_option 与 gt_option 的位置距离
    position_distance = Counter()
    for r in wrong:
        gt_opt = r.get("gt_option")
        pred_opt = r.get("pred_option")
        if gt_opt in OPTION_LABELS and pred_opt in OPTION_LABELS:
            dist = abs(OPTION_LABELS.index(pred_opt) - OPTION_LABELS.index(gt_opt))
            position_distance[dist] += 1

    return {
        "total_samples": total,
        "success_count": success,
        "error_count": errors,
        "valid_count": len(valid),
        "parse_failure_count": parse_failures,
        "parse_failure_rate": round(parse_failures / success, 6) if success else 0.0,
        "correct_count": correct,
        "accuracy": round(accuracy, 6),
        "per_prompt_type": per_prompt_type,
        "gt_option_distribution": gt_option_distribution,
        "pred_option_distribution": pred_option_distribution,
        "per_option_accuracy": per_option_accuracy,
        "position_bias_std": position_bias_std,
        "confusion_matrix": confusion_matrix,
        "top_wrong_chosen_idioms": [
            {"idiom": idiom, "count": count} for idiom, count in top_wrong_chosen
        ],
        "wrong_position_distance": {str(k): v for k, v in sorted(position_distance.items())},
    }


# ══════════════════════════════════════════════════════════
#  主评估入口
# ══════════════════════════════════════════════════════════

def evaluate_mc(
    result_file: str,
    output_dir: str = "evaluate_result",
) -> dict:
    """
    评估单个 MC 结果文件。

    Args:
        result_file: 结果 JSON 文件路径
        output_dir:  输出目录

    Returns:
        评估报告 dict
    """
    result_path = Path(result_file)
    if not result_path.exists():
        raise FileNotFoundError(f"结果文件不存在: {result_file}")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        raise ValueError(f"结果文件为空: {result_file}")

    # 自动检测 task
    task = _detect_task(data)
    if task is None:
        raise ValueError(f"无法自动检测 task 类型: {result_file}")

    # 提取模型名
    models = set(r.get("model", "unknown") for r in data)
    model = models.pop() if len(models) == 1 else "/".join(sorted(models))

    # 执行评估
    metrics = _evaluate_mc(data, task)

    # 组装报告
    report = {
        "meta": {
            "source_file": str(result_path.resolve()),
            "source_filename": result_path.name,
            "task": task,
            "eval_type": "multiple_choice",
            "model": model,
        },
        "metrics": metrics,
    }

    # 写入输出
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{result_path.stem}_analysis.json"
    out_path = out_dir / out_name

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印摘要
    _print_summary_mc(report, out_path)

    return report


def _print_summary_mc(report: dict, out_path: Path):
    """打印评估摘要。"""
    meta = report["meta"]
    m = report["metrics"]
    task = meta["task"]

    print(f"\n{'═' * 60}")
    print(f"  MC Evaluation Report")
    print(f"{'═' * 60}")
    print(f"  Source          : {meta['source_filename']}")
    print(f"  Task            : {task.upper()}")
    print(f"  Model           : {meta['model']}")
    print(f"  Total samples   : {m['total_samples']}")
    print(f"  Success         : {m['success_count']}")
    print(f"  Errors          : {m['error_count']}")
    print(f"  Valid (has GT)  : {m['valid_count']}")
    print(f"  Parse failures  : {m['parse_failure_count']} ({m['parse_failure_rate']:.2%})")
    print(f"  ── Accuracy ─────────────────────────────────")
    print(f"  Correct         : {m['correct_count']}/{m['valid_count']}")
    print(f"  Accuracy        : {m['accuracy']:.4f} ({m['accuracy'] * 100:.2f}%)")

    if m.get("per_prompt_type"):
        print(f"  ── Per prompt_type ──────────────────────────")
        for pt, info in m["per_prompt_type"].items():
            print(f"    {pt:<14}: {info['correct']}/{info['total']} ({info['accuracy'] * 100:.1f}%)")

    print(f"  ── Position Bias Analysis ───────────────────")
    print(f"  GT distribution   : {m['gt_option_distribution']}")
    print(f"  Pred distribution : { {k: v for k, v in m['pred_option_distribution'].items() if v > 0} }")
    print(f"  Per-option accuracy:")
    for label in OPTION_LABELS:
        info = m["per_option_accuracy"].get(label, {})
        if info.get("total", 0) > 0:
            print(f"    {label}: {info['correct']}/{info['total']} ({info['accuracy'] * 100:.1f}%)")
    print(f"  Position bias σ : {m['position_bias_std']:.4f}")

    print(f"  ── Confusion Matrix (GT × Pred) ────────────")
    header = "       " + "  ".join(f"{l:>5}" for l in OPTION_LABELS + ["INV"])
    print(f"  {header}")
    for gt_label in OPTION_LABELS:
        row = m["confusion_matrix"].get(gt_label, {})
        vals = [str(row.get(l, 0)).rjust(5) for l in OPTION_LABELS]
        vals.append(str(row.get("INVALID", 0)).rjust(5))
        print(f"    {gt_label}:  {'  '.join(vals)}")

    print(f"  ── Output ───────────────────────────────────")
    print(f"  Report saved to : {out_path}")
    print(f"{'═' * 60}\n")


# ══════════════════════════════════════════════════════════
#  命令行入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import glob

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="MC (Multiple-Choice) 实验结果评估",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python evaluate_mc.py results/mc_ch_gpt4o_base.json
  python evaluate_mc.py results/mc_ch_*.json results/mc_en_*.json
  python evaluate_mc.py results/mc_en_gpt4o.json --output_dir my_eval/
        """,
    )

    parser.add_argument(
        "files", nargs="+",
        help="结果 JSON 文件路径（支持 glob 通配符）",
    )
    parser.add_argument(
        "--output_dir", default="evaluate_result",
        help="输出目录（默认 evaluate_result/）",
    )

    args = parser.parse_args()

    # 展开 glob
    all_files = []
    for pattern in args.files:
        expanded = glob.glob(pattern)
        if expanded:
            all_files.extend(expanded)
        else:
            all_files.append(pattern)

    if not all_files:
        print("❌ 未找到任何文件")
        sys.exit(1)

    print(f"📂 共找到 {len(all_files)} 个文件待评估\n")

    for fpath in sorted(all_files):
        try:
            evaluate_mc(
                result_file=fpath,
                output_dir=args.output_dir,
            )
        except Exception as e:
            print(f"❌ 评估失败 [{fpath}]: {e}\n")