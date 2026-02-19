
from pathlib import Path

p = Path(r"d:\auto\MetaPassiveIncome_FINAL\src\product_generator.py")
lines = p.read_text(encoding="utf-8").splitlines()

# Fix 1: Buttons
start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'data-plan="Starter" data-price="$19"' in line:
        # We found the first button.
        # The div start should be above.
        # Search backwards for <div class="row">
        found_start = False
        for j in range(i, max(0, i-5), -1):
            if '<div class="row">' in lines[j]:
                start_idx = j
                found_start = True
                break
        
        if found_start:
            # Search forward for closing div
            for k in range(i, min(len(lines), i+10)):
                if '</div>' in lines[k]:
                    end_idx = k
                    break
            break

if start_idx != -1 and end_idx != -1:
    print(f"Found button block at {start_idx}-{end_idx}")
    # Replace lines [start_idx : end_idx+1]
    new_block_lines = [
        '      <div class="row" id="plan-buttons">',
        '        <!-- Dynamic buttons injected by JS -->',
        '      </div>'
    ]
    # Slice assignment replaces the range
    lines[start_idx : end_idx+1] = new_block_lines
    print("Replaced button block.")
else:
    print("Button block not found by content search.")

# Fix 2: JS URL rewrite
js_idx = -1
for i, line in enumerate(lines):
    if 'if (isLocalPreview() && url && url.indexOf("/api/pay/download") !== -1) {' in line:
        js_idx = i
        break

if js_idx != -1:
    print(f"Found JS block at {js_idx}")
    # Add false && to the condition
    if "false &&" not in lines[js_idx]:
        lines[js_idx] = lines[js_idx].replace('if (', 'if (false && ')
        print("Disabled JS block.")
    else:
        print("JS block already disabled.")
else:
    print("JS block not found by content search.")

p.write_text("\n".join(lines), encoding="utf-8")
