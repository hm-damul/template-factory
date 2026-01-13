import os
import json

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"

REQUIRED = ["<h2>Overview</h2>", "<h2>How to Use</h2>", "<h2>Monthly Table</h2>"]

def main():
    verified = 0
    rejected = 0

    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue

        p_path = f"{PRODUCT_DIR}/{fn}"
        product = json.load(open(p_path, "r", encoding="utf-8"))
        pid = product["id"]

        t_path = f"{TEMPLATE_DIR}/{pid}.html"
        if not os.path.exists(t_path):
            product["state"] = "REJECTED"
        else:
            html = open(t_path, "r", encoding="utf-8").read()
            ok = all(x in html for x in REQUIRED) and len(html) > 500
            product["state"] = "VERIFIED" if ok else "REJECTED"

        with open(p_path, "w", encoding="utf-8") as w:
            json.dump(product, w, ensure_ascii=False, indent=2)

        if product["state"] == "VERIFIED":
            verified += 1
        else:
            rejected += 1

    print(f"verified={verified} rejected={rejected}")

if __name__ == "__main__":
    main()
