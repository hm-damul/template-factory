import os, json

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"
OUT_DIR = "docs/i18n"  # 웹에서 바로 접근 가능하게 docs 아래 생성

LANGS = {
    "DE": {"Overview":"Übersicht","How to Use":"Anleitung","Monthly Table":"Monatliche Tabelle","Notes":"Notizen","Tips":"Tipps"},
    "FR": {"Overview":"Présentation","How to Use":"Mode d’emploi","Monthly Table":"Tableau mensuel","Notes":"Notes","Tips":"Conseils"},
    "JA": {"Overview":"概要","How to Use":"使い方","Monthly Table":"月次表","Notes":"メモ","Tips":"ヒント"},
}

def translate(html: str, mapping: dict) -> str:
    for k,v in mapping.items():
        html = html.replace(f"<h2>{k}</h2>", f"<h2>{v}</h2>")
    return html

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    created = 0
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        p = json.load(open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8"))
        if p.get("state") != "VERIFIED":
            continue
        pid = p["id"]
        src = f"{TEMPLATE_DIR}/{pid}.html"
        if not os.path.exists(src):
            continue
        base = open(src, "r", encoding="utf-8").read()

        for lang, mapping in LANGS.items():
            lang_dir = f"{OUT_DIR}/{lang}"
            os.makedirs(lang_dir, exist_ok=True)
            out = translate(base, mapping)
            with open(f"{lang_dir}/{pid}.html", "w", encoding="utf-8") as w:
                w.write(out)
            created += 1

    print(f"i18n_pages_created={created}")

if __name__ == "__main__":
    main()
