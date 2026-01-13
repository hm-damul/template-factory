import os
import json
import hashlib
from datetime import datetime

SCORED_PATH = "generated/topics_scored.jsonl"
OUT_DIR = "generated/products"

def pid_from_topic(topic: str) -> str:
    h = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:10]
    return f"p-{h}"

def main():
    if not os.path.exists(SCORED_PATH):
        raise FileNotFoundError("generated/topics_scored.jsonl not found")

    os.makedirs(OUT_DIR, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    created = 0

    with open(SCORED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            topic = row["topic"]
            pid = pid_from_topic(topic)

            out_path = f"{OUT_DIR}/{pid}.json"
            if os.path.exists(out_path):
                continue

            product = {
                "id": pid,
                "title": topic,
                "price": row["price"],
                "score": row["score"],
                "state": "DRAFT",
                "created_at": ts,
                "language": "EN",
            }

            with open(out_path, "w", encoding="utf-8") as w:
                json.dump(product, w, ensure_ascii=False, indent=2)
            created += 1

    print(f"created_products={created}")

if __name__ == "__main__":
    main()
