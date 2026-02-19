# 파일명: deploy_module.py
import os
import shutil
import subprocess


def deploy_to_vercel():
    print("🚀 Vercel 최적화 배포 가동...")

    output_dir = "outputs"
    if not os.path.exists(output_dir):
        print("❌ outputs 폴더가 없습니다.")
        return

    # 1. 404 에러 방지: 가장 점수가 높은 파일을 index.html로 복사
    html_files = [
        f for f in os.listdir(output_dir) if f.endswith(".html") and f != "index.html"
    ]
    if html_files:
        # 가장 최근에 생성된(또는 점수가 포함된) 파일을 메인으로 설정
        source_file = os.path.join(output_dir, html_files[-1])
        target_file = os.path.join(output_dir, "index.html")
        shutil.copy2(source_file, target_file)
        print(f"📦 {html_files[-1]} 파일을 메인 페이지로 설정 완료.")

    # 2. Vercel 배포 실행
    try:
        print("🌐 서버로 전송 중... (잠시만 기다려주세요)")
        # shell=True와 인코딩 설정을 위해 리스트가 아닌 문자열로 전달 시도
        result = subprocess.run(
            "vercel outputs --prod --yes",
            capture_output=True,
            text=True,
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )

        if result.returncode == 0:
            print("✨ [최종 성공] 전 세계 배포 완료!")
            for line in result.stdout.split("\n"):
                if "https://" in line and "vercel.app" in line:
                    clean_url = line.strip().split()[-1]  # URL만 깔끔하게 추출
                    print(f"🔗 접속 주소: {clean_url}")
                    break
        else:
            print(f"❌ 배포 실패: {result.stderr}")

    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")


if __name__ == "__main__":
    deploy_to_vercel()
