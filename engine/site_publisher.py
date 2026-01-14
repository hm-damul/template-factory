import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"

SITE_ROOT = "docs"
SITE_PRODUCTS = "docs/products"

BUNDLE_DIR = "generated/bundles"
BUNDLE_SITE_ROOT = "docs/bundles"
BUNDLE_DOWNLOAD_ROOT = "docs/downloads_bundles"

def main():
    os.makedirs(SITE_ROOT, exist_ok=True)
    os.makedirs(SITE_PRODUCTS, exist_ok=True)
        # 번들 페이지 생성
    os.makedirs(BUNDLE_SITE_ROOT, exist_ok=True)
    bundles = []
    if os.path.exists(BUNDLE_DIR):
        for fn in os.listdir(BUNDLE_DIR):
            if fn.endswith(".json"):
                b = json.load(open(f"{BUNDLE_DIR}/{fn}", "r", encoding="utf-8"))
                bundles.append(b)
        bundles.sort(key=lambda x: x.get("id", ""))

    for b in bundles:
        bid = b["id"]
        btitle = b["title"]
        bprice = b["price"]
        items_html = "".join([f"<li>{it['title']} — ${it['price']}</li>" for it in b["items"]])
        page = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{btitle}</title></head>
<body>
  <p><a href="../index.html">← Back to list</a></p>
  <h1>{btitle}</h1>
  <p>Price: ${bprice}</p>
  <p><b>Includes:</b></p>
  <ul>{items_html}</ul>
  <p><b>Download:</b> <a href="../downloads_bundles/{bid}/bundle_pack.zip">bundle_pack.zip</a></p>
</body>
</html>"""
        with open(f"{BUNDLE_SITE_ROOT}/{bid}.html", "w", encoding="utf-8") as w:
            w.write(page)

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
       if 'bundles' in locals():
        blis = []
        for b in bundles:
            blis.append(f'<li><a href="bundles/{b["id"]}.html">{b["title"]}</a> — ${b["price"]}</li>')
        bundle_links = "<h2>Bundles</h2><ul>" + "".join(blis) + "</ul>"

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
    {bundle_links}
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
