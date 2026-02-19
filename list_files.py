import os

root = r"d:\auto\MetaPassiveIncome_FINAL"
output_file = r"d:\auto\MetaPassiveIncome_FINAL\file_dump.txt"
print(f"Writing to {output_file}")
try:
    with open(output_file, "w", encoding="utf-8") as out:
        for dirpath, dirnames, filenames in os.walk(root):
            for f in filenames:
                path = os.path.join(dirpath, f)
                out.write(path + "\n")
    print("Done")
except Exception as e:
    print(f"Error: {e}")
