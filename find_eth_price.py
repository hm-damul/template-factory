import os

target_dir = r"d:\auto\MetaPassiveIncome_FINAL\outputs"
search_term = "0.0196"

print(f"Searching for '{search_term}' in {target_dir}...")

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith((".html", ".md", ".json", ".txt", ".py", ".js")):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if search_term in content:
                        print(f"Found in: {file_path}")
                        # Print context
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if search_term in line:
                                print(f"  Line {i+1}: {line.strip()}")
            except Exception as e:
                pass
