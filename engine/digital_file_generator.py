import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"

# 다운로드 파일은 docs 아래에 둬야 GitHub Pages에서 바로 내려받을 수 있음
DOWNLOAD_ROOT = "docs/downloads"

def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

def csv_template(title: str) -> str:
    # 아주 기본적인 “템플릿 실물” CSV
    # 나중에 더 고급으로 확장 가능
    return (
        "Section,Item,Value,Notes\n"
        f"Meta,Title,{title},\n"
        "Monthly,Week 1,,\n"
        "Monthly,Week 2,,\n"
        "Monthly,Week 3,,\n"
        "Monthly,Week 4,,\n"
        "Tracking,Goal,,\n"
        "Tracking,Result,,\n"
    )

def txt_instructions(title: str) -> str:
    return f"""# {title}

This package includes:
- template.csv  (editable spreadsheet-style template)
- printable.html (print-friendly template)
- instructions.txt (this file)

How to use:
1) Download template.csv
2) Open it with Excel, Google Sheets, or Numbers
3) Fill weekly and review monthly

Tip:
Start simple and keep tracking consistent.
"""

def printable_html(title: str, pid: str, price: float, ts: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Printable — {title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-bottom: 6px; }}
    .meta {{ color: #555; margin-bottom: 18px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #999; padding: 10px; }}
    .small {{ color:#666; font-size: 12px; margin-top: 14px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">ID: {pid} · Price: ${price} · Generated: {ts}</div>

  <h2>Monthly Planner</h2>
  <table>
    <tr><th>Week</th><th>Goal</th><th>Result</th><th>Notes</th></tr>
    <tr><td>1</td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td></tr>
    <tr><td>4</td><td></td><td></td><td></td></tr>
  </table>

  <p class="small">Print tip: Use your browser’s Print → Save as PDF if you want a PDF.</p>
</body>
</html>
"""

def main():
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    created = 0

    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue

        p_path = f"{PRODUCT_DIR}/{fn}"
        product = json.load(open(p_path, "r", encoding="utf-8"))

        if product.get("state") != "VERIFIED":
            continue

        pid = product["id"]
        title = product["title"]
        price = float(product.get("price", 9.99))

        out_dir = f"{DOWNLOAD_ROOT}/{pid}"
        # 파일들이 이미 있으면 덮어쓰기해도 무방(항상 최신 생성 시간 반영)
        write_file(f"{out_dir}/template.csv", csv_template(title))
        write_file(f"{out_dir}/instructions.txt", txt_instructions(title))
        write_file(f"{out_dir}/printable.html", printable_html(title, pid, price, ts))

        created += 1

    print(f"download_files_created_for_verified={created}")

if __name__ == "__main__":
    main()
