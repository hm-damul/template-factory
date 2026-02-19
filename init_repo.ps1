# GitHub 저장소 초기화 및 푸시 스크립트

Write-Host "--- GitHub 저장소 초기화 시작 ---" -ForegroundColor Cyan

# 1. git 초기화 확인
if (!(Test-Path .git)) {
    git init
    Write-Host "[OK] Git 저장소가 초기화되었습니다." -ForegroundColor Green
} else {
    Write-Host "[INFO] 이미 Git 저장소가 존재합니다." -ForegroundColor Yellow
}

# 2. .gitignore 확인 (이미 업데이트됨)
Write-Host "[INFO] .gitignore 파일을 확인합니다."

# 3. 모든 파일 추가 (gitignore에 의해 필터링됨)
git add .
Write-Host "[OK] 파일이 스테이징 영역에 추가되었습니다." -ForegroundColor Green

# 4. 첫 커밋
git commit -m "Initial commit for Meta Passive Income (Autonomous System)"
Write-Host "[OK] 첫 커밋이 완료되었습니다." -ForegroundColor Green

Write-Host ""
Write-Host "다음 단계를 수행하여 GitHub에 연결하세요:" -ForegroundColor Magenta
Write-Host "1. GitHub에서 새로운 'Private' 저장소를 만드세요."
Write-Host "2. 아래 명령어를 실행하세요 (URL은 본인 것으로 변경):"
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git"
Write-Host "   git push -u origin main"
Write-Host ""
Write-Host "--- 초기화 완료 ---" -ForegroundColor Cyan
