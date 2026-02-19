# 파일명: brain_module.py
import random


class CATPBrain:
    def __init__(self):
        self.quality_threshold = 90

    def analyze_trends(self):
        # 성공 사례 기반 암호화폐 트렌드 키워드
        trends = [
            "Defi Dashboard",
            "NFT Minting Landing",
            "Crypto Portfolio Tracker",
            "Web3 SaaS UI",
        ]
        selected = random.choice(trends)
        print(f"[분석 완료] 오늘의 타겟 주제: {selected}")
        return selected

    def quality_check(self, content):
        # AI 검수 로직 (시뮬레이션)
        # 90점 미만은 False를 반환하여 재생성을 유도합니다.
        score = random.randint(85, 100)
        print(f"[품질 검수] 현재 점수: {score}")

        if score >= self.quality_threshold:
            print("✅ 품질 통과 (90점 이상)")
            return True, score
        else:
            print("❌ 품질 미달 (폐기 및 재생성 대상)")
            return False, score
