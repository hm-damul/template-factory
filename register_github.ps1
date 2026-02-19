# GitHub 등록 스크립트
$repoUrl = "https://github.com/hm-damul/template-factory.git"

# Git 경로 탐색
$gitPaths = @(
    "git",
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files\Git\bin\git.exe",
    "C:\Program Files (x86)\Git\cmd\git.exe",
    "C:\Program Files (x86)\Git\bin\git.exe",
    "$env:USERPROFILE\AppData\Local\Programs\Git\cmd\git.exe",
    "$env:USERPROFILE\AppData\Local\Programs\Git\bin\git.exe"
)

$gitExe = $null
foreach ($path in $gitPaths) {
    if (Get-Command $path -ErrorAction SilentlyContinue) {
        $gitExe = $path
        break
    }
}

if (-not $gitExe) {
    Write-Host "----------------------------------------------------" -ForegroundColor Red
    Write-Host "오류: Git을 찾을 수 없습니다!" -ForegroundColor Red
    Write-Host "1. Git이 설치되어 있지 않다면 설치해 주세요: https://git-scm.com/download/win"
    Write-Host "2. 이미 설치되어 있다면, git.exe의 전체 경로를 아래에 입력해 주세요."
    Write-Host "   (예: C:\Program Files\Git\bin\git.exe)"
    $manualPath = Read-Host "git.exe 경로 입력 (비워두면 종료)"
    if ($manualPath -and (Test-Path $manualPath)) {
        $gitExe = $manualPath
    } else {
        Write-Error "Git 경로가 유효하지 않습니다. 스크립트를 종료합니다."
        exit 1
    }
}

Write-Host "Git 실행 파일 발견: $gitExe" -ForegroundColor Green

# 1. Git 초기화
if (-not (Test-Path .git)) {
    & $gitExe init
    Write-Host "Git 저장소 초기화 완료." -ForegroundColor Green
}

# 2. Remote 추가 (이미 있으면 업데이트)
$remotes = & $gitExe remote
if ($remotes -contains "origin") {
    & $gitExe remote set-url origin $repoUrl
} else {
    & $gitExe remote add origin $repoUrl
}
Write-Host "Remote URL 설정 완료: $repoUrl" -ForegroundColor Green

# 3. 브랜치 이름 변경 (main)
& $gitExe branch -M main

# 4. Git 사용자 정보 설정 (커밋 에러 방지)
$gitEmail = & $gitExe config user.email
$gitName = & $gitExe config user.name

if (-not $gitEmail) {
    Write-Host "Git 이메일이 설정되지 않아 임시로 설정합니다." -ForegroundColor Yellow
    & $gitExe config --local user.email "hm-damul@users.noreply.github.com"
}
if (-not $gitName) {
    Write-Host "Git 이름이 설정되지 않아 임시로 설정합니다." -ForegroundColor Yellow
    & $gitExe config --local user.name "hm-damul"
}

# 5. 파일 추가 및 커밋
& $gitExe add .
$commitMsg = "Initial commit for Meta Passive Income (Autonomous System)"
$commitRes = & $gitExe commit -m $commitMsg 2>&1

# "nothing to commit"은 에러가 아니므로 무시하고 진행
if ($LASTEXITCODE -ne 0 -and $commitRes -notmatch "nothing to commit" -and $commitRes -notmatch "working tree clean") {
    Write-Host "----------------------------------------------------" -ForegroundColor Red
    Write-Host "오류: 커밋에 실패했습니다!" -ForegroundColor Red
    Write-Host $commitRes
    exit 1
} else {
    Write-Host "커밋 확인 완료 (새로운 변경사항이 없거나 이미 커밋됨)." -ForegroundColor Green
}

# 6. 푸시 (강제 푸시 옵션 포함)
Write-Host "GitHub로 푸시를 시도합니다... (로그인이 필요할 수 있습니다)" -ForegroundColor Cyan
Write-Host "참고: 원격 저장소에 이미 파일이 있는 경우 덮어씁니다 (--force)." -ForegroundColor Yellow
& $gitExe push -u origin main --force
