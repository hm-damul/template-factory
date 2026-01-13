import os
import json
from datetime import datetime

TOPICS_PATH = "generated/topics.txt"
OUT_PATH = "generated/topics_scored.jsonl"

PRICE_TABLE = {
    "Budget Planner": 9.99,
    "Habit Tracker": 10.99,
    "Meal Planner": 10.99,
    "Study Planner": 10.99,
}

def score(topic: str) -> float:
    base = 50.0
    if "Small Business" in topic:
        base += 10
    if "Budget" in topic:
        base += 5
    return base

def price(topic: str) -> float:
    for k, v in PRICE_TABLE.items():
        if topic.startswith(k):
            return v
    return 9.99

def main():
    if not os.path.exists(TOPICS_PATH):
        raise FileNotFoundError("generated/topics.txt not found")

    os.makedirs("generated", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    out = []
    with open(TOPICS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("#"):
                continue
            out.append({
                "topic": t,
                "score": score(t),
                "price": price(t),
                "generated_at": ts,
            })

    with open(OUT_PATH, "w", encoding="utf-8") as w:
        for row in out:
            w.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"scored={len(out)} -> {OUT_PATH}")

if __name__ == "__main__":
    main()
