
from pathlib import Path

p = Path(r"d:\auto\MetaPassiveIncome_FINAL\src\product_generator.py")
out_p = Path(r"d:\auto\MetaPassiveIncome_FINAL\debug_output.txt")
lines = p.read_text(encoding="utf-8").splitlines()

res = []
target = 'Starter</button>'
found = False
for i, line in enumerate(lines):
    if target in line:
        res.append(f"Found target at {i}: {repr(line)}")
        found = True

if not found:
    res.append("Target not found.")
    if len(lines) > 1264:
        res.append(f"Line 1264: {repr(lines[1264])}")

out_p.write_text("\n".join(res), encoding="utf-8")
