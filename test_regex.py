import re
text = "Unlock Your Passive Income with 마이크로 SaaS 대시보드 UI (MVP)"
# 한글 완성형, 자모, 호환자모 모두 포함
regex = '[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]'
cleaned = re.sub(regex, '', text)
print(f"Original: {text}")
print(f"Cleaned: {cleaned}")
if re.search(regex, cleaned):
    print("STILL HAS KOREAN")
else:
    print("CLEAN")
