import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"

SITE_ROOT = "docs"
SITE_PRODUCTS = "docs/products"

def main():
    os.makedirs(SITE_ROOT, exist_ok=True)
    os.makedirs(SITE_PRODUCTS, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # VERIFIED만 노출
    products = []
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        p = json.load(open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8"))
        if p.get("state") == "VERIFIED":
            products.append(p)

    products.sort(key=lambda x: (-x.get("score", 0), x.get("title", "")))

    # 상세 페이지 생성
    for p in products:
        pid = p["id"]
        title = p["title"]
        price = p["price"]

        src_html = f"{TEMPLATE_DIR}/{pid}.html"
        if not os.path.exists(src_html):
            continue

        body = open(src_html, "r", encoding="utf-8").read()

        out = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <p><a href="../index.html">← Back to list</a></p>
  {body}
  <hr/>
  <p><b>Download files:</b></p>
<ul>
  <li><a href="../downloads/{pid}/bundle.zip">bundle.zip</a> (recommended)</li>
  <li><a href="../downloads/{pid}/template.csv">template.csv</a></li>
  <li><a href="../downloads/{pid}/printable.html">printable.html</a> (print or Save as PDF)</li>
  <li><a href="../downloads/{pid}/instructions.txt">instructions.txt</a></li>
</ul>


</body>
</html>
"""
        with open(f"{SITE_PRODUCTS}/{pid}.html", "w", encoding="utf-8") as w:
            w.write(out)

    # 인덱스 생성
    items = []
    for p in products:
        pid = p["id"]
        items.append(f'<li><a href="products/{pid}.html">{p["title"]}</a> — ${p["price"]}</li>')

    index = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Template Store (MVP)</title></head>
<body>
  <h1>Template Store (MVP)</h1>
  <p>Generated at: {ts}</p>
  <p>VERIFIED products: {len(products)}</p>
  <ul>
    {''.join(items)}
  </ul>
</body>
</html>
"""
    with open(f"{SITE_ROOT}/index.html", "w", encoding="utf-8") as w:
        w.write(index)

    # .nojekyll 유지
    nojekyll = f"{SITE_ROOT}/.nojekyll"
    if not os.path.exists(nojekyll):
        open(nojekyll, "w", encoding="utf-8").write("")

    print(f"published_verified={len(products)}")

if __name__ == "__main__":
    main()
