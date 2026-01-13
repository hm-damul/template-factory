
import os
import zipfile

DOWNLOAD_ROOT = "docs/downloads"

def make_zip(zip_path: str, files: list[tuple[str, str]]):
    # files: [(absolute_path, arcname_inside_zip), ...]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for src, arcname in files:
            if os.path.exists(src):
                z.write(src, arcname=arcname)

def main():
    if not os.path.exists(DOWNLOAD_ROOT):
        print("No downloads directory yet. Skipping zip generation.")
        return

    created = 0
    for pid in os.listdir(DOWNLOAD_ROOT):
        pdir = os.path.join(DOWNLOAD_ROOT, pid)
        if not os.path.isdir(pdir):
            continue

        template_csv = os.path.join(pdir, "template.csv")
        printable_html = os.path.join(pdir, "printable.html")
        instructions_txt = os.path.join(pdir, "instructions.txt")

        # 최소 1개 파일은 있어야 zip 생성
        if not (os.path.exists(template_csv) or os.path.exists(printable_html) or os.path.exists(instructions_txt)):
            continue

        zip_path = os.path.join(pdir, "bundle.zip")

        make_zip(zip_path, [
            (template_csv, "template.csv"),
            (printable_html, "printable.html"),
            (instructions_txt, "instructions.txt"),
        ])

        created += 1

    print(f"bundle_zip_created={created}")

if __name__ == "__main__":
    main()
