import os, json
from datetime import datetime

PRODUCT_DIR = "generated/products"
SITE_PRODUCTS_DIR = "docs/products"
I18N_ROOT = "docs/i18n"

# 원하는 언어(국가)만 유지하세요
LANGS = [
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("ja", "日本語"),
]

# "AI 번역 키가 아직 없을 때"는 기본 사전/치환만 적용 (깨지지 않게)
BASE_DICT = {
    "Back to list": {
        "fr": "← Retour à la liste",
        "de": "← Zurück zur Liste",
        "ja": "← 一覧に戻る",
    },
    "Download files:": {
        "fr": "Téléchargements :",
        "de": "Downloads:",
        "ja": "ダウンロード:",
    },
    "recommended": {
        "fr": "recommandé",
        "de": "empfohlen",
        "ja": "おすすめ",
    },
    "print or Save as PDF": {
        "fr": "imprimer ou enregistrer en PDF",
        "de": "drucken oder als PDF speichern",
        "ja": "印刷またはPDF保存",
    },
    "Digital product. No physical item shipped.": {
        "fr": "Produit numérique. Aucun article physique ne sera expédié.",
        "de": "Digitales Produkt. Kein physischer Versand.",
        "ja": "デジタル商品です。物理的な配送はありません。",
    },
}

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def read_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def translate_snippet(text: str, lang: str) -> str:
    # 최소 번역: 고정 문구만 번역
    out = text
    for k, v in BASE_DICT.items():
        out = out.replace(k, v.get(lang, k))
    return out

def load_verified_products():
    items = []
    if not os.path.exists(PRODUCT_DIR):
        return items
    for fn in os.listdir(PRODUCT_DIR):
        if fn.endswith(".json"):
            p = read_json(f"{PRODUCT_DIR}/{fn}")
            if p.get("state") == "VERIFIED":
                items.append(p)
    items.sort(key=lambda x: x.get("id",""))
    return items

def main():
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    products = load_verified_products()
    if not products:
        print("No verified products. Skip i18n.")
        return

    # 각 언어별 폴더 생성
    for lang, _label in LANGS:
        ensure_dir(f"{I18N_ROOT}/{lang}/products")
        ensure_dir(f"{I18N_ROOT}/{lang}/bundles")

    # 제품 상세 페이지를 복제/치환
    for p in products:
        pid = p["id"]
        src = f"{SITE_PRODUCTS_DIR}/{pid}.html"
        if not os.path.exists(src):
            continue

        html = open(src, "r", encoding="utf-8").read()

        for lang, _label in LANGS:
            out_html = translate_snippet(html, lang)

            # 링크 경로 보정: i18n 페이지에서 index로 돌아갈 때
            out_html = out_html.replace('href="../index.html"', 'href="../../index.html"')

            # 다운로드 경로는 동일(언어별로 파일 복제 안 함)
            # products/xxx.html 에서 docs/downloads/xxx로 연결 그대로 사용

            out_path = f"{I18N_ROOT}/{lang}/products/{pid}.html"
            with open(out_path, "w", encoding="utf-8") as w:
                w.write(out_html)

    # 언어별 인덱스 생성
    for lang, label in LANGS:
        items = []
        for p in products:
            pid = p["id"]
            title = p.get("title","")
            price = p.get("price", 9.99)
            items.append(f'<li><a href="products/{pid}.html">{title}</a> — ${price}</li>')

        page = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Store ({label})</title></head>
<body>
  <p><a href="../../index.html">← Back to main</a></p>
  <h1>Store ({label})</h1>
  <p>Generated at: {ts}</p>
  <ul>{''.join(items)}</ul>
</body>
</html>
"""
        out = f"{I18N_ROOT}/{lang}/index.html"
        with open(out, "w", encoding="utf-8") as w:
            w.write(translate_snippet(page, lang))

    print(f"i18n_generated_langs={[l for l,_ in LANGS]} products={len(products)}")

if __name__ == "__main__":
    main()
