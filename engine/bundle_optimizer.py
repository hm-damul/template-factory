import os, json, csv, zipfile
from datetime import datetime

PRODUCT_DIR = "generated/products"
DOWNLOAD_ROOT = "docs/downloads"

BUNDLE_DIR = "generated/bundles"
BUNDLE_DOWNLOAD_ROOT = "docs/downloads_bundles"

PLATFORM_DIR = "generated/platform"

BUNDLE_SIZE = 5
DISCOUNT_RATE = 0.70  # 번들 할인(합계의 70%)
PSYCHO_ENDINGS = [0.99, 0.97, 0.95]  # 심리 가격 마감

def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def category_of(title: str) -> str:
    t = title.lower()
    if "budget" in t or "expense" in t or "finance" in t:
        return "budget"
    if "habit" in t or "routine" in t:
        return "habit"
    if "meal" in t or "grocery" in t:
        return "meal"
    if "study" in t or "student" in t or "learning" in t:
        return "study"
    return "general"

def psych_price(x: float) -> float:
    # 예: 37.12 -> 36.99, 18.34 -> 17.99 처럼 "살짝 낮은" 심리 가격으로 내림
    if x <= 0:
        return 0.0
    base = int(x)  # 내림 정수
    candidates = []
    for end in PSYCHO_ENDINGS:
        candidates.append(base + end)
        candidates.append(max(0, base - 1 + end))
    # x 이하 중 가장 큰 값 선택(너무 낮추지 않음)
    candidates = [c for c in candidates if c <= x]
    if not candidates:
        return round(max(0.99, min(x, 0.99)), 2)
    return round(max(candidates), 2)

def make_zip(zip_path: str, sources: list[tuple[str,str]]):
    ensure_dir(os.path.dirname(zip_path))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for src, arcname in sources:
            if os.path.exists(src):
                z.write(src, arcname=arcname)

def load_verified_products():
    items = []
    if not os.path.exists(PRODUCT_DIR):
        return items
    for fn in os.listdir(PRODUCT_DIR):
        if fn.endswith(".json"):
            p = read_json(f"{PRODUCT_DIR}/{fn}")
            if p.get("state") == "VERIFIED":
                p["__cat"] = category_of(p.get("title",""))
                items.append(p)
    # 점수 우선 정렬
    items.sort(key=lambda x: (-float(x.get("score", 0) or 0), x.get("title","")))
    return items

def bundle_title(cat: str, n: int) -> str:
    # 플랫폼 친화적인 번들 이름
    mapping = {
        "budget": "Budget Planner Bundle",
        "habit": "Habit Tracker Bundle",
        "meal": "Meal Planner Bundle",
        "study": "Study Planner Bundle",
        "general": "Planner Template Bundle",
    }
    base = mapping.get(cat, "Planner Template Bundle")
    return f"{base} Pack {n} ({BUNDLE_SIZE} templates)"

def make_tags_bundle(cat: str):
    # Etsy 번들 태그(13개 제한)
    tags = []
    if cat == "budget": tags += ["budget planner", "expense tracker", "finance planner"]
    if cat == "habit": tags += ["habit tracker", "routine planner", "daily tracker"]
    if cat == "meal": tags += ["meal planner", "grocery list", "weekly meal plan"]
    if cat == "study": tags += ["study planner", "student planner", "learning tracker"]
    tags += ["planner bundle", "printable bundle", "digital download", "instant download", "template pack", "minimalist planner"]
    # 중복 제거 + 13개 제한
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
        if len(out) >= 13:
            break
    return out

def short_desc_bundle(title: str):
    return f"{title}. Bundle pack includes multiple templates in one ZIP. Instant digital download."

def long_desc_bundle(title: str, price: float):
    return (
        f"{title}\n\n"
        f"WHAT YOU GET\n"
        f"- bundle_pack.zip (contains individual product bundles)\n\n"
        f"HOW TO USE\n"
        f"1) Download bundle_pack.zip\n"
        f"2) Open each included bundle.zip per template\n\n"
        f"NOTES\n"
        f"- Digital product. No physical item shipped.\n"
        f"- Price suggestion: ${price}\n"
    )

def main():
    ensure_dir(BUNDLE_DIR)
    ensure_dir(BUNDLE_DOWNLOAD_ROOT)
    ensure_dir(PLATFORM_DIR)

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    products = load_verified_products()
    if not products:
        print("No verified products. Skip bundle optimization.")
        return

    # 카테고리별 그룹
    groups = {}
    for p in products:
        groups.setdefault(p["__cat"], []).append(p)

    bundles = []
    # 카테고리별로 번들 생성
    for cat, items in groups.items():
        # 너무 적으면 일반으로 합치지 않고 스킵(원하면 변경 가능)
        if len(items) < BUNDLE_SIZE:
            continue

        pack_no = 1
        for i in range(0, len(items), BUNDLE_SIZE):
            chunk = items[i:i+BUNDLE_SIZE]
            if len(chunk) < BUNDLE_SIZE:
                break

            bundle_id = f"bundle-{cat}-{pack_no:03d}"
            title = bundle_title(cat, pack_no)

            raw_sum = sum(float(p.get("price", 9.99)) for p in chunk)
            discounted = raw_sum * DISCOUNT_RATE
            price = psych_price(discounted)

            meta = {
                "id": bundle_id,
                "title": title,
                "price": price,
                "created_at": ts,
                "category": cat,
                "items": [{"id": p["id"], "title": p["title"], "price": p.get("price", 9.99)} for p in chunk]
            }
            with open(f"{BUNDLE_DIR}/{bundle_id}.json", "w", encoding="utf-8") as w:
                json.dump(meta, w, ensure_ascii=False, indent=2)

            # 번들 ZIP: 각 상품의 bundle.zip를 폴더로 묶어 넣기
            sources = []
            for p in chunk:
                pid = p["id"]
                src_zip = f"{DOWNLOAD_ROOT}/{pid}/bundle.zip"
                if not os.path.exists(src_zip):
                    continue
                sources.append((src_zip, f"{pid}/bundle.zip"))

            out_zip = f"{BUNDLE_DOWNLOAD_ROOT}/{bundle_id}/bundle_pack.zip"
            make_zip(out_zip, sources)

            bundles.append(meta)
            pack_no += 1

    # 플랫폼 업로드용 번들 CSV 생성
    etsy_path = f"{PLATFORM_DIR}/etsy_bundles.csv"
    with open(etsy_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bundle_id","title","price","tags(semicolon)","short_description","category","generated_at"])
        for b in bundles:
            tags = ";".join(make_tags_bundle(b.get("category","general")))
            w.writerow([b["id"], b["title"][:140], b["price"], tags, short_desc_bundle(b["title"]), b.get("category",""), ts])

    gumroad_path = f"{PLATFORM_DIR}/gumroad_bundles.csv"
    with open(gumroad_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bundle_id","name","price","description","category","generated_at"])
        for b in bundles:
            desc = long_desc_bundle(b["title"], float(b["price"])).replace("\n","\\n")
            w.writerow([b["id"], b["title"][:80], b["price"], desc, b.get("category",""), ts])

    print(f"bundle_optimized_created={len(bundles)} etsy={etsy_path} gumroad={gumroad_path}")

if __name__ == "__main__":
    main()
