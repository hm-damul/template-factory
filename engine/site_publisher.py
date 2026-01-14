import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"

SITE_ROOT = "docs"
SITE_PRODUCTS = "docs/products"

# Bundles
BUNDLE_DIR = "generated/bundles"
BUNDLE_SITE_ROOT = "docs/bundles"
BUNDLE_DOWNLOAD_ROOT = "docs/downloads_bundles"


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def main():
    ensure_dir(SITE_ROOT)
    ensure_dir(SITE_PRODUCTS)

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1) VERIFIED products only
    products = []
    if os.path.exists(PRODUCT_DIR):
        for fn in os.listdir(PRODUCT_DIR):
            if fn.endswith(".json"):
                p = read_json(f"{PRODUCT_DIR}/{fn}")
                if p.get("state") == "VERIFIED":
                    products.append(p)

    products.sort(key=lambda x: (-float(x.get("score", 0) or 0), x.get("title", "")))

    # 2) Product detail pages
    for p in products:
        pid = p["id"]
        title = p["title"]
        price = p.get("price", 9.99)

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

    # 3) Bundles (safe even if none)
    bundles = []
    if os.path.exists(BUNDLE_DIR):
        for fn in os.listdir(BUNDLE_DIR):
            if fn.endswith(".json"):
                b = read_json(f"{BUNDLE_DIR}/{fn}")
                # 최소 필드 방어
                if b.get("id") and b.get("title") and b.get("price") is not None:
                    bundles.append(b)

    bundles.sort(key=lambda x: x.get("id", ""))

    ensure_dir(BUNDLE_SITE_ROOT)

    for b in bundles:
        bid = b["id"]
        btitle = b["title"]
        bprice = b["price"]
        items = b.get("items", [])

        items_html = "".join([f"<li>{it.get('title','')} — ${it.get('price','')}</li>" for it in items])

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

    # 4) Build index.html (products + bundles)
    product_items = []
    for p in products:
        pid = p["id"]
        product_items.append(f'<li><a href="products/{pid}.html">{p["title"]}</a> — ${p.get("price", 9.99)}</li>')

    bundle_section = ""
    if bundles:
        bundle_items = []
        for b in bundles:
            bundle_items.append(f'<li><a href="bundles/{b["id"]}.html">{b["title"]}</a> — ${b["price"]}</li>')
        bundle_section = "<h2>Bundles</h2><ul>" + "".join(bundle_items) + "</ul>"

    index = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Template Store (MVP)</title></head>
<body>
  <h1>Template Store (MVP)</h1>
  <p>Generated at: {ts}</p>

  {bundle_section}

  <h2>Products</h2>
  <p>VERIFIED products: {len(products)}</p>
  <ul>
    {''.join(product_items)}
  </ul>
</body>
</html>
"""
    with open(f"{SITE_ROOT}/index.html", "w", encoding="utf-8") as w:
        w.write(index)

    # 5) Ensure .nojekyll exists
    nojekyll = f"{SITE_ROOT}/.nojekyll"
    if not os.path.exists(nojekyll):
        open(nojekyll, "w", encoding="utf-8").write("")

    print(f"published_verified={len(products)} bundles={len(bundles)}")


if __name__ == "__main__":
    main()
