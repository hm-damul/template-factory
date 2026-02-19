import hashlib
ids = [
    '20260214-140141-ai-dev-income',
    '20260214-133737-ai-powered-passive-income-syst',
    '20260214-130903-ai-trading-bot'
]
for pid in ids:
    seed = int(hashlib.md5(pid.encode()).hexdigest(), 16)
    print(f"{pid}: {seed % 5}")
