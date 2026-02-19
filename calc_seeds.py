import hashlib
p1 = "20260214-140141-ai-dev-income"
p2 = "20260214-133737-ai-powered-passive-income-syst"
s1 = int(hashlib.md5(p1.encode()).hexdigest(), 16) % 3
s2 = int(hashlib.md5(p2.encode()).hexdigest(), 16) % 3
print(f"S1: {s1}, S2: {s2}")
