# MetaPassiveIncome Digital Product Factory (생산 등급)

이 프로젝트는 AI 기반의 디지털 제품 제조 공장으로, 제품 생성부터 품질 검사, 패키징, 발행, 결제 및 통제된 다운로드 이행까지 전체 파이프라인을 자동화합니다. 프로토타입 수준을 넘어 판매 가능한 디지털 제품을 효율적으로 생산하고 관리하는 것을 목표로 합니다.

## 🎯 시스템 역할

AI 기반 공장은 디지털 제품을 생성하고, 자동화된 품질 검사를 수행하며, 판매 가능한 자산으로 패키징하고, 통제된 결제 및 다운로드 시스템을 통해 배포합니다.

## 🧩 생산 파이프라인

모든 제품은 다음 구조화된 생산 단계를 거칩니다.

1.  **Generate (생성)**
    *   AI가 제품 자산(랜딩 페이지, 콘텐츠 파일 등)을 생성합니다.
2.  **QA Stage 1 – Generation Quality Gate (생성 품질 게이트)**
    *   생성 직후 다음을 자동 검증합니다:
        *   필수 구조 섹션(hero, features, CTA, FAQ 등) 존재 여부
        *   주요 출력 파일 존재 및 읽기 가능 여부
        *   명백한 깨진 링크 또는 누락된 자산 없음
        *   페이지가 주요 구조적 오류 없이 렌더링됨
    *   QA 실패 시: 자동 개선/재생성 시도 또는 제품을 `QA1_FAILED`로 표시합니다.
3.  **Package Stage – Productization (제품화 패키징)**
    *   QA를 통과한 제품만 판매 가능한 형태로 패키징됩니다:
        *   전달 가능한 ZIP 파일 생성
        *   필수 파일(메인 제품, 자산, README, 라이선스 등) 포함
        *   버전 메타데이터 및 체크섬 생성
        *   제품 메타데이터에 패키지 정보 기록
4.  **QA Stage 2 – Shipment Gate (배송 게이트)**
    *   제품이 게시/판매되기 전에 다음을 검증합니다:
        *   전달 가능한 ZIP 파일 존재 여부
        *   ZIP 파일에 필수 파일 포함 여부
        *   다운로드 엔드포인트가 실제로 파일을 제공할 수 있는지 확인
        *   메타데이터가 패키징된 아티팩트와 일치하는지 확인
    *   QA 실패 시: 제품을 발행할 수 없습니다.
5.  **Publish Stage (발행)**
    *   제품은 다음 조건을 모두 충족할 때만 `Published`로 간주됩니다:
        *   QA Stage 1 통과
        *   패키징 완료
        *   QA Stage 2 통과
    *   대시보드는 `DRAFT → QA1_FAILED → PACKAGED → QA2_FAILED → PUBLISHED`와 같은 제품 상태를 반영합니다.
6.  **Payment Gate (결제 게이트)**
    *   고객은 제품 파일에 직접 접근할 수 없습니다.
    *   구매 시 주문이 생성됩니다.
    *   결제 확인 시 주문이 `PAID`로 표시됩니다.
    *   `PAID` 주문만 다운로드 접근 권한을 받을 수 있습니다.
7.  **Controlled Fulfillment (통제된 이행)**
    *   다운로드는 토큰 기반으로 이루어집니다:
        *   결제 후 안전한 다운로드 토큰 생성
        *   토큰은 만료 시간이 있어야 함
        *   토큰은 1회 사용 또는 사용 제한이 있어야 함
        *   다운로드 로그 기록

## 📊 품질 평가 시스템

제품 품질은 측정 가능하게 다루어지며, 다음을 포함하는 구조화된 평가가 도입됩니다:

*   기능적 준비성
*   구조적 완전성
*   기술적 유효성
*   제품화 완전성

최소 품질 임계값 미만의 제품은 발행 가능한 카탈로그에 진입할 수 없습니다.

## 🗂 데이터 무결성

다음과 같은 구조화된 원장(ledger)이 도입 또는 개선되어 시스템 상태의 단일 정보 소스 역할을 합니다:

*   **Products**: 상태, 버전, 패키지 정보
*   **Orders**: 생성일, 결제 여부, 배송 여부
*   **Downloads**: 누가 언제 무엇을 다운로드했는지
*   **Publish history**: 발행 이력

## 🔁 오류 처리

시스템은 탄력적이어야 합니다:

*   파일 누락 시에도 조용히 실패하지 않습니다.
*   QA 실패는 로깅됩니다.
*   패키징 오류는 발행을 방지합니다.
*   다운로드 오류는 추적 가능해야 합니다.

## ✅ 최종 목표

리팩토링 후 제품은 다음 조건을 충족할 때만 판매 가능합니다:

*   생성 QA 통과
*   적절히 패키징됨
*   배송 QA 통과
*   통제된 파이프라인을 통해 발행됨
*   보안 토큰 기반 다운로드를 통해 결제 확인 후 전달됨

이것은 이제 프로토타입이 아닌 `생산 제조 시스템`입니다.

## 🚀 시작하기

### 1. 프로젝트 설정

프로젝트 레포지토리를 클론합니다:

```bash
git clone https://github.com/your-repo/MetaPassiveIncome_FINAL.git
cd MetaPassiveIncome_FINAL
```

### 2. Python 환경 설정

가상 환경을 생성하고 활성화합니다:

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
```

필요한 의존성을 설치합니다:

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (`.env`)

프로젝트 루트에 `.env` 파일을 생성하고 다음 환경 변수를 설정합니다. (`LEMON_SQUEEZY_API_KEY`, `GITHUB_TOKEN`, `VERCEL_API_TOKEN`, `JWT_SECRET_KEY`는 실제 값을 사용해야 합니다.)

```dotenv
LEMON_SQUEEZY_API_KEY="your_lemon_squeezy_api_key_here"
GITHUB_TOKEN="your_github_token_here"
VERCEL_API_TOKEN="your_vercel_api_token_here"
JWT_SECRET_KEY="a_very_secret_key_for_jwt_signing_12345"
DOWNLOAD_TOKEN_EXPIRY_SECONDS=3600 # 다운로드 토큰 만료 시간 (초)
DATABASE_URL="sqlite:///./product_factory.db" # SQLite 데이터베이스 파일 경로
OUTPUT_DIR="d:/auto/MetaPassiveIncome_FINAL/outputs" # 생성된 제품 자산 저장 경로
DOWNLOAD_DIR="d:/auto/MetaPassiveIncome_FINAL/downloads" # 패키징된 제품 파일 저장 경로
LOG_FILE="d:/auto/MetaPassiveIncome_FINAL/logs/product_factory.log" # 메인 로그 파일 경로
DASHBOARD_PORT=8099 # 대시보드 서버 포트
VERCEL_PROJECT_ID="your_vercel_project_id" # Vercel 프로젝트 ID (선택 사항)
VERCEL_ORG_ID="your_vercel_org_id" # Vercel 조직 ID (선택 사항)
```

**중요**: `JWT_SECRET_KEY`는 강력하고 고유한 문자열로 설정해야 합니다.

### 4. 대시보드 실행

대시보드 서버를 실행하여 제품 생산 파이프라인을 시각적으로 관리하고 모니터링할 수 있습니다.

```bash
python src/dashboard_service.py
```

브라우저에서 `http://127.0.0.1:8099/` (또는 `.env`에서 설정한 `DASHBOARD_PORT`)에 접속하여 대시보드를 확인합니다.

### 5. 제품 파이프라인 실행 (CLI)

`main.py` 스크립트를 통해 전체 제품 생산 파이프라인을 실행할 수 있습니다:

```bash
python main.py --topic "Decentralized Finance Tracker App" --batch 1
```

*   `--topic`: 생성할 제품의 주제를 지정합니다. (선택 사항, 비워두면 기본 주제 사용)
*   `--batch`: 생성할 제품의 배치 개수를 지정합니다. (기본값: 1)
*   `--languages`: 쉼표로 구분된 언어 목록을 지정합니다. (기본값: `en,ko`, 현재 `ProductGenerator`에서 HTML만 생성하며, 언어별 콘텐츠 생성 및 번역 기능은 추후 통합 예정)

## 🛠 주요 모듈 및 파일

*   `main.py`: 전체 제품 파이프라인의 메인 진입점.
*   `src/`: 핵심 비즈니스 로직을 포함하는 디렉토리.
    *   `config.py`: 환경 변수 및 공통 설정 관리.
    *   `utils.py`: 로깅, 오류 처리, 파일 유틸리티 등 공통 유틸리티 함수.
    *   `ledger_manager.py`: 제품, 주문, 다운로드 이력 등을 관리하는 데이터 원장. (SQLAlchemy 기반)
    *   `product_generator.py`: AI가 제품 자산(예: 랜딩 페이지 HTML)을 생성하는 모듈.
    *   `qa_manager.py`: 생성 품질 게이트(QA Stage 1) 및 배송 게이트(QA Stage 2)를 담당하는 모듈.
    *   `package_manager.py`: 제품을 판매 가능한 ZIP 파일로 패키징하는 모듈.
    *   `publisher.py`: 제품을 발행하고 Vercel과 같은 외부 플랫폼에 배포하는 모듈.
    *   `payment_processor.py`: Lemon Squeezy API를 통한 결제 처리 및 웹훅 관리.
    *   `fulfillment_manager.py`: JWT 기반의 안전한 다운로드 토큰 생성 및 다운로드 이행 관리.
    *   `dashboard_service.py`: 웹 기반 관리 대시보드.
*   `requirements.txt`: Python 의존성 목록.
*   `.env`: 환경 변수 설정 파일.
*   `outputs/`: 생성된 제품 자산이 임시로 저장되는 디렉토리.
*   `downloads/`: 패키징된 최종 제품 ZIP 파일이 저장되는 디렉토리.
*   `logs/`: 애플리케이션 로그 파일 저장 디렉토리.

## 🤝 기여

이 프로젝트는 지속적으로 개선될 예정입니다. 기여를 환영합니다!

---
**MetaPassiveIncome Production Team**