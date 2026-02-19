import hashlib

products = [
    "20260214-140141-ai-dev-income",
    "20260214-133737-ai-powered-passive-income-syst",
    "20260214-130903-ai-trading-bot"
]

image_pools = {
    "ai": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=2000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1675271591211-126ad94c495d?q=80&w=2000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=2000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1593349480506-8433a14cc64e?q=80&w=2000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1672911739264-2f306ca8a221?q=80&w=2000&auto=format&fit=crop"
    ]
}

for pid in products:
    seed = int(hashlib.md5(pid.encode()).hexdigest(), 16)
    idx = seed % len(image_pools["ai"])
    print(f"{pid}: {idx} -> {image_pools['ai'][idx]}")
