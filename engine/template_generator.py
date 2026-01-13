import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
OUT_DIR = "generated/templates"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    count = 0
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue

        path = f"{PRODUCT_DIR}/{fn}"
        product = json.load(open(path, "r", encoding="utf-8"))

        pid = product["id"]
        title = product["title"]
        price = product["price"]

        out_path = f"{OUT_DIR}/{pid}.html"
        if os.path.exists(out_path):
            continue

        html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <p>Generated at: {ts}</p>
  <p>Price: ${price}</p>

  <h2>Overview</h2>
  <ul>
    <li>Purpose: help users organize information</li>
    <li>Format: printable-style sections</li>
  </ul>

  <h2>How to Use</h2>
  <ol>
    <li>Print or copy into your preferred tool.</li>
    <li>Fill weekly, review monthly.</li>
  </ol>

  <h2>Monthly Table</h2>
  <table border="1" cellpadding="6">
    <tr><th>Week</th><th>Goal</th><th>Result</th></tr>
    <tr><td>1</td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td></tr>
    <tr><td>4</td><td></td><td></td></tr>
  </table>

  <h2>Notes</h2>
  <p>Write your notes here.</p>

  <h2>Tips</h2>
  <p>Consistency beats perfection.</p>
</body>
</html>
"""
        with open(out_path, "w", encoding="utf-8") as w:
            w.write(html)

        count += 1

    print(f"templates_created={count}")

if __name__ == "__main__":
    main()
