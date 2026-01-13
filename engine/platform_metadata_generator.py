import os, json, csv
from datetime import datetime

PRODUCT_DIR = "generated/products"
OUT_DIR = "generated/platform"

# Etsy 태그는 최대 13개가 일반적이라(플랫폼별 다름), 여기선 13개로 맞춤
def make_tags(title: str):
    base = title.lower()
    tags = []
    # 아주 단순 규칙(나중에 AI로 교체 가능)
    if "budget" in base: tags += ["budget planner", "finance tracker", "expense tracker"]
    if "habit" in base: tags += ["habit tracker", "daily tracker", "routine planner"]
    if "meal" in base: tags += ["meal planner", "grocery list", "weekly meals"]
    if "study" in base: tags += ["study planner", "student planner", "learning tracker"]

    # 공통 태그
    tags += ["printable template", "digital download", "planner bundle", "minimalist planner", "instant download"]

    # 중복 제거 + 13개 제한
    out = []
    for t in tags:
        t = t.strip()
        if t and t not in out:
            out.append(t)
        if len(out) >= 13:
            break
    return out

def etsy_title(title: str):
    # Etsy는 제목 길이 제한이 있을 수 있어(플랫폼 정책/현황에 따라), 너무 길면 자름
    t = f"{title} | Printable Template | Instant Download"
    return t[:140]

def gumroad_name(title: str):
    return title[:80]

def short_description(title: str):
    return f"{title}. Includes CSV template + print-friendly HTML + ZIP bundle. Instant digital download."

def long_description(title: str, price: float):
    return (
        f"{title}\n\n"
        f"WHAT YOU GET\n"
        f"- bundle.zip (recommended)\n"
        f"- template.csv (editable)\n"
        f"- printable.html (print or Save as PDF)\n"
        f"- instructions.txt\n\n"
        f"HOW TO USE\n"
        f"1) Download bundle.zip\n"
        f"2) Open template.csv in Excel / Google Sheets\n"
        f"3) Print printable.html if needed\n\n"
        f"NOTES\n"
        f"- Digital product. No physical item shipped.\n"
        f"- Price suggestion: ${price}\n"
    )

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    verified = []
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        p = json.load(open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8"))
        if p.get("state") == "VERIFIED":
            verified.append(p)

    verified.sort(key=lambda x: (-x.get("score", 0), x.get("title", "")))

    # Etsy CSV (간단 버전)
    etsy_path = f"{OUT_DIR}/etsy_listings.csv"
    with open(etsy_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "title", "price", "tags(semicolon)", "short_description", "generated_at"])
        for p in verified:
            pid = p["id"]
            title = etsy_title(p["title"])
            price = p.get("price", 9.99)
            tags = ";".join(make_tags(p["title"]))
            w.writerow([pid, title, price, tags, short_description(p["title"]), ts])

    # Gumroad CSV (간단 버전)
    gumroad_path = f"{OUT_DIR}/gumroad_products.csv"
    with open(gumroad_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "name", "price", "description", "generated_at"])
        for p in verified:
            pid = p["id"]
            name = gumroad_name(p["title"])
            price = p.get("price", 9.99)
            desc = long_description(p["title"], float(price)).replace("\n", "\\n")
            w.writerow([pid, name, price, desc, ts])

    print(f"platform_metadata_created: etsy={etsy_path}, gumroad={gumroad_path}, count={len(verified)}")

if __name__ == "__main__":
    main()
