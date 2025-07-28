import glob
import os

path = "/data/tianyu_data/appendix/GuessBenchmark/data_generation_alt/idiom_emoji_questions"
txt_files = glob.glob(os.path.join(path, "*.txt"))
print(f"该目录下有 {len(txt_files)} 个txt文件")