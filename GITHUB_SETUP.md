# GitHub Repository Setup Guide

이 프로젝트를 GitHub Actions로 무인 운영하기 위한 설정 가이드입니다.

## 1. GitHub Secrets 설정
GitHub 저장소의 **Settings > Secrets and variables > Actions** 메뉴에서 아래 항목들을 `New repository secret`으로 등록하세요.

| Secret Name | Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `VERCEL_API_TOKEN` | Vercel 계정의 Access Token |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST Token |
| `NOWPAYMENTS_API_KEY` | NOWPayments API 키 |
| `MERCHANT_WALLET_ADDRESS` | 암호화폐 결제 대금을 받을 지갑 주소 |
| `DOWNLOAD_TOKEN_SECRET` | 다운로드 링크 생성용 JWT 시크릿 (아무 문자열이나 가능) |

## 2. 저장소 초기화 및 푸시 (PowerShell)
로컬 코드를 GitHub에 처음 올릴 때 아래 명령어를 사용하세요. (또는 `init_repo.ps1` 실행)

```powershell
# git 초기화
git init

# 불필요한 파일 제외 (.gitignore 확인)
git add .

# 첫 커밋
git commit -m "Initial commit for Meta Passive Income"

# 원격 저장소 연결 (본인의 저장소 URL로 변경)
# git remote add origin https://github.com/사용자명/저장소명.git

# 푸시
# git push -u origin main
```

## 3. GitHub Actions 권한 설정
저장소의 **Settings > Actions > General**에서:
- **Workflow permissions**: `Read and write permissions` 선택
- **Allow GitHub Actions to create and approve pull requests**: 체크

이 설정이 완료되면 6시간마다 자동으로 제품이 생성되고 배포됩니다.
