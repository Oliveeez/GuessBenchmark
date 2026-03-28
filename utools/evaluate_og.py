"""
evaluate_og.py
Open-ended Generation 实验结果评估器

职责：
- 读取 OG 任务的中文/英文结果 JSON
- 自动检测 task 类型（ch/en）
- 计算论文所需的全部指标
- 输出结构化评估报告 JSON

─── 指标说明 ────────────────────────────────────────────

中文（ch）：
  - accuracy:          整体准确率
  - per_prompt_type:   按 prompt_type (sequential/freeform/guided) 细分准确率
  - error_analysis:    常见错误类型分布

英文（en）：
  - strict_accuracy:   标准化精确匹配准确率
  - match_accuracy:    模糊匹配准确率（默认阈值 0.85）
  - avg_match_score:   平均 match_score
  - match_score_distribution: match_score 分布直方图数据

通用：
  - total / success / error / valid 数量
  - model / task 元信息
  - parse_failure_rate: LLM 响应解析失败率

─── 使用示例 ────────────────────────────────────────────

  # 单文件评估
  python evaluate_og.py results/ch_gemini_2_5_pro_base.json

  # 多文件批量评估
  python evaluate_og.py results/ch_*.json results/en_*.json

  # 指定英文模糊匹配阈值
  python evaluate_og.py results/en_gpt4o.json --match_threshold 0.80

  # 指定输出目录
  python evaluate_og.py results/ch_gpt4o.json --output_dir my_eval_results/
"""

import json
import re
import sys
import logging
from collections import Counter
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════

def _normalize_en(text: str) -> str:
    """英文 idiom 标准化：统一小写、去标点、合并空格。"""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_score(a: str, b: str) -> float:
    """计算两个标准化字符串的 SequenceMatcher 相似度。"""
    na, nb = _normalize_en(a), _normalize_en(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _detect_task(data: list[dict]) -> Optional[str]:
    """自动检测 task 类型。"""
    for item in data:
        task = item.get("task")
        if task in ("ch", "en"):
            return task
    # 回退：看字段
    for item in data:
        if "correct" in item and "strict_correct" not in item:
            return "ch"
        if "strict_correct" in item:
            return "en"
    return None


# ══════════════════════════════════════════════════════════
#  中文评估
# ══════════════════════════════════════════════════════════

def _evaluate_ch(data: list[dict]) -> dict:
    """评估中文 OG 结果。"""
    total = len(data)
    success = sum(1 for r in data if r.get("success"))
    errors = sum(1 for r in data if r.get("error"))
    valid = [r for r in data if r.get("gt") is not None and r.get("success")]
    parse_failures = sum(1 for r in data if r.get("success") and r.get("pred") is None)

    correct = sum(1 for r in valid if r.get("correct"))
    accuracy = correct / len(valid) if valid else 0.0

    # 按 prompt_type 细分
    per_prompt_type = {}
    prompt_types = sorted(set(r.get("prompt_type", "unknown") for r in valid))
    for pt in prompt_types:
        pt_items = [r for r in valid if r.get("prompt_type") == pt]
        pt_correct = sum(1 for r in pt_items if r.get("correct"))
        per_prompt_type[pt] = {
            "total": len(pt_items),
            "correct": pt_correct,
            "accuracy": pt_correct / len(pt_items) if pt_items else 0.0,
        }

    # 错误分析：pred 不为 None 但不正确的样本
    wrong = [r for r in valid if r.get("correct") is False and r.get("pred")]
    error_preds = Counter(r["pred"] for r in wrong)
    top_wrong_preds = error_preds.most_common(20)

    # GT 与 pred 的字符级重叠分析（辅助 error analysis）
    char_overlap_stats = []
    for r in wrong:
        gt, pred = r["gt"], r["pred"]
        overlap = sum(1 for c in pred if c in gt)
        char_overlap_stats.append({
            "gt": gt,
            "pred": pred,
            "overlap_chars": overlap,
            "overlap_ratio": overlap / len(gt) if gt else 0,
        })
    # 按 overlap 降序取 top
    char_overlap_stats.sort(key=lambda x: x["overlap_ratio"], reverse=True)

    return {
        "total_samples": total,
        "success_count": success,
        "error_count": errors,
        "valid_count": len(valid),
        "parse_failure_count": parse_failures,
        "parse_failure_rate": parse_failures / success if success else 0.0,
        "correct_count": correct,
        "accuracy": round(accuracy, 6),
        "per_prompt_type": per_prompt_type,
        "top_wrong_predictions": [
            {"pred": pred, "count": count} for pred, count in top_wrong_preds
        ],
        "partial_match_examples": char_overlap_stats[:20],
    }


# ══════════════════════════════════════════════════════════
#  英文评估
# ══════════════════════════════════════════════════════════

def _evaluate_en(data: list[dict], match_threshold: float = 0.85) -> dict:
    """评估英文 OG 结果。"""
    total = len(data)
    success = sum(1 for r in data if r.get("success"))
    errors = sum(1 for r in data if r.get("error"))
    valid = [r for r in data if r.get("gt") is not None and r.get("success")]
    parse_failures = sum(1 for r in data if r.get("success") and r.get("pred") is None)

    # ── strict accuracy ──
    strict_correct = 0
    for r in valid:
        if r.get("strict_correct") is not None:
            if r["strict_correct"]:
                strict_correct += 1
        elif r.get("gt") and r.get("pred"):
            if _normalize_en(r["pred"]) == _normalize_en(r["gt"]):
                strict_correct += 1

    strict_accuracy = strict_correct / len(valid) if valid else 0.0

    # ── match accuracy & scores ──
    match_scores = []
    match_correct = 0
    for r in valid:
        if r.get("match_score") is not None:
            score = r["match_score"]
        elif r.get("gt") and r.get("pred"):
            score = _match_score(r["pred"], r["gt"])
        else:
            score = 0.0
        match_scores.append(score)
        if score >= match_threshold:
            match_correct += 1

    match_accuracy = match_correct / len(valid) if valid else 0.0
    avg_match_score = sum(match_scores) / len(match_scores) if match_scores else 0.0

    # match_score 分布（直方图 bin）
    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    score_distribution = {}
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        label = f"{lo:.1f}-{hi:.1f}"
        count = sum(1 for s in match_scores if lo <= s < hi)
        score_distribution[label] = count
    # 最后一个 bin 包含 1.0
    score_distribution["1.0"] = sum(1 for s in match_scores if s == 1.0)
    score_distribution["0.9-1.0"] = (
        score_distribution.get("0.9-1.0", 0) - score_distribution["1.0"]
    )
    if score_distribution["0.9-1.0"] < 0:
        score_distribution["0.9-1.0"] = 0

    # 不同阈值下的 match_accuracy（方便论文对比）
    threshold_sweep = {}
    for thr in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
        cnt = sum(1 for s in match_scores if s >= thr)
        threshold_sweep[f"threshold_{thr:.2f}"] = {
            "correct": cnt,
            "accuracy": round(cnt / len(valid), 6) if valid else 0.0,
        }

    # 错误分析
    wrong_strict = [
        r for r in valid
        if r.get("gt") and r.get("pred")
        and _normalize_en(r["pred"]) != _normalize_en(r["gt"])
    ]
    error_preds = Counter(
        _normalize_en(r["pred"]) for r in wrong_strict
    )
    top_wrong_preds = error_preds.most_common(20)

    # near-miss 分析（score >= 0.5 但 strict 不对）
    near_misses = []
    for r in wrong_strict:
        score = r.get("match_score")
        if score is None and r.get("pred") and r.get("gt"):
            score = _match_score(r["pred"], r["gt"])
        if score and score >= 0.5:
            near_misses.append({
                "gt": r["gt"],
                "pred": r["pred"],
                "match_score": round(score, 4),
            })
    near_misses.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "total_samples": total,
        "success_count": success,
        "error_count": errors,
        "valid_count": len(valid),
        "parse_failure_count": parse_failures,
        "parse_failure_rate": round(parse_failures / success, 6) if success else 0.0,
        "strict_correct_count": strict_correct,
        "strict_accuracy": round(strict_accuracy, 6),
        "match_threshold": match_threshold,
        "match_correct_count": match_correct,
        "match_accuracy": round(match_accuracy, 6),
        "avg_match_score": round(avg_match_score, 6),
        "match_score_distribution": score_distribution,
        "threshold_sweep": threshold_sweep,
        "top_wrong_predictions": [
            {"pred": pred, "count": count} for pred, count in top_wrong_preds
        ],
        "near_miss_examples": near_misses[:30],
    }


# ══════════════════════════════════════════════════════════
#  主评估入口
# ══════════════════════════════════════════════════════════

def evaluate_og(
    result_file: str,
    match_threshold: float = 0.85,
    output_dir: str = "evaluate_result",
) -> dict:
    """
    评估单个 OG 结果文件。

    Args:
        result_file:     结果 JSON 文件路径
        match_threshold: 英文模糊匹配阈值
        output_dir:      输出目录

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
    if task == "ch":
        metrics = _evaluate_ch(data)
    else:
        metrics = _evaluate_en(data, match_threshold=match_threshold)

    # 组装报告
    report = {
        "meta": {
            "source_file": str(result_path.resolve()),
            "source_filename": result_path.name,
            "task": task,
            "eval_type": "open_generation",
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
    _print_summary_og(report, out_path)

    return report


def _print_summary_og(report: dict, out_path: Path):
    """打印评估摘要。"""
    meta = report["meta"]
    m = report["metrics"]
    task = meta["task"]

    print(f"\n{'═' * 60}")
    print(f"  OG Evaluation Report")
    print(f"{'═' * 60}")
    print(f"  Source          : {meta['source_filename']}")
    print(f"  Task            : {task.upper()}")
    print(f"  Model           : {meta['model']}")
    print(f"  Total samples   : {m['total_samples']}")
    print(f"  Success         : {m['success_count']}")
    print(f"  Errors          : {m['error_count']}")
    print(f"  Valid (has GT)  : {m['valid_count']}")
    print(f"  Parse failures  : {m['parse_failure_count']} ({m['parse_failure_rate']:.2%})")

    if task == "ch":
        print(f"  ── Accuracy ─────────────────────────────────")
        print(f"  Correct         : {m['correct_count']}/{m['valid_count']}")
        print(f"  Accuracy        : {m['accuracy']:.4f} ({m['accuracy'] * 100:.2f}%)")
        if m.get("per_prompt_type"):
            print(f"  ── Per prompt_type ──────────────────────────")
            for pt, info in m["per_prompt_type"].items():
                print(f"    {pt:<14}: {info['correct']}/{info['total']} ({info['accuracy'] * 100:.1f}%)")
    else:
        print(f"  ── Strict Accuracy ──────────────────────────")
        print(f"  Correct         : {m['strict_correct_count']}/{m['valid_count']}")
        print(f"  Strict Accuracy : {m['strict_accuracy']:.4f} ({m['strict_accuracy'] * 100:.2f}%)")
        print(f"  ── Match Accuracy (threshold={m['match_threshold']}) ────")
        print(f"  Match correct   : {m['match_correct_count']}/{m['valid_count']}")
        print(f"  Match Accuracy  : {m['match_accuracy']:.4f} ({m['match_accuracy'] * 100:.2f}%)")
        print(f"  Avg match score : {m['avg_match_score']:.4f}")

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
        description="OG (Open-ended Generation) 实验结果评估",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python evaluate_og.py results/ch_gemini_2_5_pro_base.json
  python evaluate_og.py results/ch_*.json results/en_*.json
  python evaluate_og.py results/en_gpt4o.json --match_threshold 0.80
  python evaluate_og.py results/en_gpt4o.json --output_dir my_eval/
        """,
    )

    parser.add_argument(
        "files", nargs="+",
        help="结果 JSON 文件路径（支持 glob 通配符）",
    )
    parser.add_argument(
        "--match_threshold", type=float, default=0.85,
        help="英文模糊匹配阈值（默认 0.85）",
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
            evaluate_og(
                result_file=fpath,
                match_threshold=args.match_threshold,
                output_dir=args.output_dir,
            )
        except Exception as e:
            print(f"❌ 评估失败 [{fpath}]: {e}\n")