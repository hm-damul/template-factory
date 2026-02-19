
from pathlib import Path

p = Path(r"d:\auto\MetaPassiveIncome_FINAL\src\product_generator.py")
lines = p.read_text(encoding="utf-8").splitlines()

target = 'Starter</button>'
found = False
for i, line in enumerate(lines):
    if target in line:
        print(f"Found target at {i}: {repr(line)}")
        found = True

if not found:
    print("Target not found.")
    if len(lines) > 1264:
        print(f"Line 1264: {repr(lines[1264])}")
