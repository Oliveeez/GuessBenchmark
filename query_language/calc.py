from collections import defaultdict

input_file = "llm_idiom_guess_results.txt"

# 跳过表头
with open(input_file, encoding="utf-8") as f:
    next(f)
    stats = defaultdict(lambda: [0, 0])  # {难度: [正确数, 总数]}
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 5:
            continue
        correct = int(parts[3])
        difficulty = int(parts[4])
        stats[difficulty][1] += 1
        if correct:
            stats[difficulty][0] += 1

print("谐音个数\t正确数\t总数\t正确率")
for diff in sorted(stats):
    right, total = stats[diff]
    acc = right / total if total else 0
    print(f"{diff}\t{right}\t{total}\t{acc:.2%}")