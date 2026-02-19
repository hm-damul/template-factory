
from pathlib import Path

p = Path(r"d:\auto\MetaPassiveIncome_FINAL\src\product_generator.py")
lines = p.read_text(encoding="utf-8").splitlines()

print("--- BUTTONS ---")
for i in range(1260, 1270):
    if i < len(lines):
        print(f"{i}: {repr(lines[i])}")

print("\n--- JS ---")
for i in range(1520, 1535):
    if i < len(lines):
        print(f"{i}: {repr(lines[i])}")
