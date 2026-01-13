import os, json, zipfile
from datetime import datetime

PRODUCT_DIR = "generated/products"
DOWNLOAD_ROOT = "docs/downloads"
BUNDLE_OUT_DIR = "generated/bundles"
BUNDLE_DOWNLOAD_ROOT = "docs/downloads_bundles"

BUNDLE_SIZE = 5  # 3~5 추천. 여기서는 5로 고정.

def load_verified():
    items = []
    for fn in os.listdir(PRODUCT_DIR):
        if fn.endswith(".json"):
            p = json.load(open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8"))
            if p.get("state") == "VERIFIED":
                items.append(p)
    items.sort(key=lambda x: (-x.get("score", 0), x.get("title", "")))
    return items

def make_zip(zip_path: str, sources: list[tuple[str,str]]):
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for src, arcname in sources:
            if os.path.exists(src):
                z.write(src, arcname=arcname)

def main():
    os.makedirs(BUNDLE_OUT_DIR, exist_ok=True)
    os.makedirs(BUNDLE_DOWNLOAD_ROOT, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    verified = load_verified()
    if not verified:
        print("No verified products. Skip bundles.")
        return

    created = 0
    for i in range(0, len(verified), BUNDLE_SIZE):
        chunk = verified[i:i+BUNDLE_SIZE]
        if len(chunk) < 2:
            continue

        bundle_id = f"bundle-{i//BUNDLE_SIZE+1:03d}"
        title = f"Bundle Pack {i//BUNDLE_SIZE+1} ({len(chunk)} templates)"
        # 가격은 단순: 구성 합의 70% (할인 번들). 원하면 규칙 바꿀 수 있음.
        price = round(sum(float(p.get("price", 9.99)) for p in chunk) * 0.70, 2)

        # 번들 메타데이터 JSON
        meta = {
            "id": bundle_id,
            "title": title,
            "price": price,
            "created_at": ts,
            "items": [{"id": p["id"], "title": p["title"], "price": p.get("price", 9.99)} for p in chunk]
        }
        with open(f"{BUNDLE_OUT_DIR}/{bundle_id}.json", "w", encoding="utf-8") as w:
            json.dump(meta, w, ensure_ascii=False, indent=2)

        # 번들 ZIP 만들기: 각 상품의 bundle.zip를 묶어서 하나로
        sources = []
        for p in chunk:
            pid = p["id"]
            src_zip = f"{DOWNLOAD_ROOT}/{pid}/bundle.zip"
            # ZIP 안에서 파일명 충돌 방지 위해 폴더를 넣어줌
            arcname = f"{pid}/bundle.zip"
            sources.append((src_zip, arcname))

        out_zip = f"{BUNDLE_DOWNLOAD_ROOT}/{bundle_id}/bundle_pack.zip"
        make_zip(out_zip, sources)

        created += 1

    print(f"bundles_created={created}")

if __name__ == "__main__":
    main()
