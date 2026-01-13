import os
from datetime import datetime

OUT_PATH = "generated/topics.txt"

TEMPLATE_TYPES = [
    "Budget Planner",
    "Habit Tracker",
    "Meal Planner",
    "Study Planner",
]

TARGETS = [
    "Freelancers",
    "Students",
    "Couples",
    "Families",
    "Small Business Owners",
]

MAX_TOPICS_PER_RUN = 30

def load_existing():
    if not os.path.exists(OUT_PATH):
        return set()
    s = set()
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                s.add(line)
    return s

def main():
    os.makedirs("generated", exist_ok=True)

    existing = load_existing()

    candidates = []
    for t in TEMPLATE_TYPES:
        for target in TARGETS:
            candidates.append(f"{t} for {target}")

    new_topics = [x for x in candidates if x not in existing]
    new_topics = new_topics[:MAX_TOPICS_PER_RUN]

    merged = sorted(existing.union(new_topics))

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# Generated at {ts}\n")
        for t in merged:
            f.write(t + "\n")

    print(f"existing={len(existing)} new_added={len(new_topics)} total={len(merged)}")

if __name__ == "__main__":
    main()
