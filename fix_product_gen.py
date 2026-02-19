
from pathlib import Path

p = Path(r"d:\auto\MetaPassiveIncome_FINAL\src\product_generator.py")
txt = p.read_text(encoding="utf-8")

# Fix 1: Hardcoded buttons
old_block = """      <div class="row">
        <button class="btn" data-action="choose-plan" data-plan="Starter" data-price="$19">Starter</button>
        <button class="btn" data-action="choose-plan" data-plan="Pro" data-price="$49">Pro</button>
        <button class="btn" data-action="choose-plan" data-plan="Enterprise" data-price="$199">Enterprise</button>
      </div>"""

new_block = """      <div class="row" id="plan-buttons">
        <!-- Dynamic buttons injected by JS -->
      </div>"""

if old_block in txt:
    txt = txt.replace(old_block, new_block)
    print("Replaced buttons.")
else:
    print("Button block not found. Trying loose match...")
    # Try replacing just the buttons if the div wrapper has different spacing
    buttons_only = """        <button class="btn" data-action="choose-plan" data-plan="Starter" data-price="$19">Starter</button>
        <button class="btn" data-action="choose-plan" data-plan="Pro" data-price="$49">Pro</button>
        <button class="btn" data-action="choose-plan" data-plan="Enterprise" data-price="$199">Enterprise</button>"""
    if buttons_only in txt:
        # We also need to add the id to the previous line
        # This is tricky without regex, but we can try to find the line before
        pass

# Fix 2: JS URL rewrite
js_signature = 'if (isLocalPreview() && url && url.indexOf("/api/pay/download") !== -1) {'
if js_signature in txt:
    # Disable this block by making the condition false
    txt = txt.replace(js_signature, 'if (false && isLocalPreview() && url && url.indexOf("/api/pay/download") !== -1) {')
    print("Disabled JS URL rewrite.")
else:
    print("JS block not found.")

p.write_text(txt, encoding="utf-8")
