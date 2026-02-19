import json
import os
import re
import zipfile  # ZIP 파일 처리를 위해 추가
from typing import List

import requests  # 다운로드 엔드포인트 유효성 검사를 위해 추가

from .ai_quality import run_quality_inspection
from .config import Config
from .ledger_manager import LedgerManager  # LedgerManager 임포트
from .schema_validator import run_rule_based_validation
from .utils import (
    ProductionError,
    calculate_file_checksum,
    ensure_parent_dir,
    get_logger,
    handle_errors,
    write_json,
)

logger = get_logger(__name__)


class QAResult:
    """QA 검사 결과를 담는 데이터 클래스"""

    def __init__(
        self, passed: bool, stage: str, product_id: str, messages: List[str] = None
    ):
        self.passed = passed
        self.stage = stage
        self.product_id = product_id
        self.messages = messages if messages is not None else []

    def to_dict(self):
        return {
            "passed": self.passed,
            "stage": self.stage,
            "product_id": self.product_id,
            "messages": self.messages,
        }


class QAManager:
    """제품의 품질 검사 단계를 관리하는 클래스"""

    def __init__(self):
        self.ledger_manager = LedgerManager()  # LedgerManager 인스턴스 초기화
        logger.info("QAManager 초기화 완료")

    @handle_errors(stage="QA Stage 1")
    def run_qa_stage_1(self, product_id: str, output_dir: str) -> QAResult:
        """1단계 QA (생성 품질 게이트)를 실행합니다."""
        logger.info(
            f"QA Stage 1 시작 - 제품 ID: {product_id}, 출력 디렉토리: {output_dir}"
        )
        qa_messages = []
        passed = True

        # 1. 주요 출력 파일 존재 및 읽기 가능 여부 확인
        index_html_path = os.path.join(output_dir, "index.html")
        if not os.path.exists(index_html_path):
            qa_messages.append(
                f"CRITICAL: index.html 파일이 존재하지 않습니다: {index_html_path}"
            )
            passed = False
        elif not os.path.isfile(index_html_path):
            qa_messages.append(
                f"CRITICAL: index.html 경로가 파일이 아닙니다: {index_html_path}"
            )
            passed = False
        else:
            try:
                with open(index_html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                qa_messages.append("SUCCESS: index.html 파일을 성공적으로 읽었습니다.")
            except Exception as e:
                qa_messages.append(
                    f"CRITICAL: index.html 파일을 읽을 수 없습니다: {index_html_path}, 오류: {e}"
                )
                passed = False
                html_content = ""

        if not passed:  # 파일 읽기 실패 시 추가 검사 무의미
            logger.warning(
                f"QA Stage 1 실패 (파일 없음/읽기 불가) - 제품 ID: {product_id}"
            )
            return QAResult(False, "QA Stage 1", product_id, qa_messages)

        # 2. 필수 HTML 구조 요소 검사
        required_html_elements = ["<html", "<head", "<body", "</html>"]
        for element in required_html_elements:
            if element.lower() not in html_content.lower():
                qa_messages.append(
                    f"ERROR: 필수 HTML 요소 '{element}'가 누락되었습니다."
                )
                passed = False
            else:
                qa_messages.append(f"SUCCESS: 필수 HTML 요소 '{element}'가 존재합니다.")

        # [NEW] 로컬 프리뷰 리다이렉트 방지 로직 검증 (8090 포트 예외 처리 확인)
        if 'function isLocalPreview()' in html_content:
            if '8090' in html_content:
                qa_messages.append("SUCCESS: isLocalPreview()에 8090 포트 예외 처리가 포함되어 있습니다.")
            else:
                qa_messages.append("ERROR: isLocalPreview()에 8090 포트 예외 처리가 누락되었습니다. (프리뷰 리다이렉트 위험)")
                passed = False
        
        # [NEW] 결제 로직 중복 삽입 검증 (startPay 함수가 하나만 존재하는지 확인)
        start_pay_count = html_content.count('async function startPay(')
        if start_pay_count > 1:
            qa_messages.append(f"ERROR: startPay() 함수가 {start_pay_count}개 발견되었습니다. (중복 삽입 의심)")
            passed = False
        elif start_pay_count == 1:
            qa_messages.append("SUCCESS: startPay() 함수가 정상적으로 하나만 존재합니다.")
            
            # startPay 내부의 fetch 메서드 및 URL 검증
            if "fetch(`${API_BASE}/api/pay/start`" in html_content or "fetch(`${API_BASE}/api/pay/check`" in html_content:
                qa_messages.append("SUCCESS: startPay()가 올바른 API 엔드포인트를 호출합니다.")
            else:
                 # 하드코딩된 URL이나 다른 형태일 수 있으니 경고만
                qa_messages.append("WARNING: startPay()에서 표준 API 엔드포인트 호출 패턴을 찾을 수 없습니다.")

            # 405 에러 방지를 위한 method 체크 (GET 권장)
            if "method: 'POST'" in html_content and "fetch(`${API_BASE}/api/pay/start`" in html_content:
                 qa_messages.append("WARNING: 결제 시작 요청에 POST가 사용됨. (GET 권장)")
            elif "method: 'GET'" in html_content or ('method' not in html_content and "fetch" in html_content):
                 # fetch default is GET
                 qa_messages.append("SUCCESS: 결제 시작 요청에 GET 메서드가 사용됩니다 (405 회피).")
        else:
            qa_messages.append("WARNING: startPay() 함수가 발견되지 않았습니다. (결제 위젯 미삽입 가능성)")

        # [NEW] 가격 동기화 검증 (product_schema.json의 가격과 index.html의 가격 일치 여부)
        schema_path = os.path.join(output_dir, "product_schema.json")
        if os.path.isfile(schema_path):
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                schema_price = (schema_data.get("sections") or {}).get("pricing", {}).get("price", "")
                if schema_price and schema_price not in html_content:
                    qa_messages.append(f"ERROR: 스키마 가격({schema_price})이 index.html에서 발견되지 않았습니다. (가격 불일치 위험)")
                    passed = False
                elif schema_price:
                    qa_messages.append(f"SUCCESS: 스키마 가격({schema_price})이 index.html에 포함되어 있습니다.")
            except Exception as e:
                qa_messages.append(f"WARNING: 가격 동기화 검증 중 오류: {e}")

        # [NEW] 가격 동기화 검증 (premium_content_report.json vs product_schema.json)
        premium_report_path = os.path.join(output_dir, "premium_content_report.json")
        if os.path.isfile(premium_report_path) and os.path.isfile(schema_path):
            try:
                with open(premium_report_path, "r", encoding="utf-8") as f:
                    premium_data = json.load(f)
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                
                premium_price = premium_data.get("meta", {}).get("final_price_usd")
                schema_price_str = (schema_data.get("sections") or {}).get("pricing", {}).get("price", "")
                
                # schema_price_str은 "$49.00" 형식일 수 있으므로 숫자만 추출
                schema_price = None
                if schema_price_str:
                    match = re.search(r"(\d+\.?\d*)", schema_price_str)
                    if match:
                        schema_price = float(match.group(1))
                
                if premium_price is not None and schema_price is not None:
                    if abs(premium_price - schema_price) > 0.01:
                        qa_messages.append(f"ERROR: 프리미엄 엔진 가격({premium_price}$)과 스키마 가격({schema_price}$)이 불일치합니다.")
                        passed = False
                    else:
                        qa_messages.append(f"SUCCESS: 프리미엄 엔진과 스키마 간 가격 동기화 확인됨 ({premium_price}$).")
            except Exception as e:
                qa_messages.append(f"WARNING: 프리미엄 엔진-스키마 가격 검증 중 오류: {e}")

        # 3. 필수 구조 섹션 존재 여부 확인 (헤딩 태그나 ID/클래스 기반으로 검색)
        required_sections = {
            "hero": [r"<section[^>]*id=\"hero\"", r"<div[^>]*class=\".*hero\""],
            "features": [r"<section[^>]*id=\"features\"", r"<h2[^>]*>Features</h2>"],
            "pricing": [r"<section[^>]*id=\"pricing\"", r"<h2[^>]*>Pricing</h2>"],
            "faq": [r"<section[^>]*id=\"faq\"", r"<h2[^>]*>FAQ</h2>"],
            "cta": [
                r"<button[^>]*data-action=\"open-plans\"",
                r"<button[^>]*class=\".*btn-primary\"",
            ],  # primary_cta 버튼
        }

        for section, patterns in required_sections.items():
            found = False
            for pattern in patterns:
                if re.search(pattern, html_content, re.IGNORECASE):
                    found = True
                    break
            if not found:
                qa_messages.append(
                    f"ERROR: 필수 섹션 '{section}'이 HTML에 존재하지 않습니다."
                )
                passed = False
            else:
                qa_messages.append(f"SUCCESS: 필수 섹션 '{section}'이 존재합니다.")

        # 3.1. HTML 최소 길이 검사(콘텐츠 밀도 확인)
        min_len = 1500  # 최소 길이를 1200 -> 1500으로 상향
        if len(html_content) < min_len:
            qa_messages.append(
                f"ERROR: HTML 콘텐츠가 너무 짧습니다({len(html_content)}자). 최소 {min_len}자 필요."
            )
            passed = False
        else:
            qa_messages.append(
                f"SUCCESS: HTML 콘텐츠 길이 충분({len(html_content)}자 >= {min_len}자)."
            )

        # [NEW] 타이틀 태그 검사 (Generic Title 방지)
        title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE)
        if title_match:
            title_text = title_match.group(1).strip().lower()
            generic_titles = ["document", "untitled", "loading", "page", "home"]
            if title_text in generic_titles or not title_text:
                qa_messages.append(f"ERROR: 타이틀이 너무 일반적입니다: '{title_match.group(1)}'. 구체적인 제품명을 사용하세요.")
                passed = False
            else:
                qa_messages.append(f"SUCCESS: 유효한 타이틀이 존재합니다: '{title_match.group(1)}'")
        else:
            qa_messages.append("ERROR: <title> 태그가 없습니다.")
            passed = False


        # 4. 깨진 링크 또는 누락된 이미지 자산 검사 (간단한 정규식 기반)
        # <img src="" ...>, <a href="" ...> 와 같이 비어있는 src/href를 찾음
        broken_links_imgs = re.findall(
            r'<(?:img[^>]*src|a[^>]*href)=""[^>]*>', html_content, re.IGNORECASE
        )
        if broken_links_imgs:
            qa_messages.append(
                f"ERROR: {len(broken_links_imgs)}개의 깨진 링크 또는 누락된 이미지 src가 발견되었습니다."
            )
            passed = False
        else:
            qa_messages.append(
                "SUCCESS: 깨진 링크 또는 누락된 이미지 src가 발견되지 않았습니다."
            )

        # 5. 스키마 검증 + 규칙 기반 검증 (Schema-enforced pipeline)
        schema = None
        schema_path = os.path.join(output_dir, "product_schema.json")
        if not os.path.isfile(schema_path):
            qa_messages.append("CRITICAL: product_schema.json이 없습니다. 스키마 기반 생성이 필요합니다.")
            passed = False
        else:
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                rule_result = run_rule_based_validation(schema)
                if not rule_result.passed:
                    qa_messages.append(f"ERROR: 스키마 규칙 검증 실패: {rule_result.errors}")
                    passed = False
                else:
                    qa_messages.append("SUCCESS: 스키마 규칙 검증 통과.")
            except Exception as e:
                qa_messages.append(f"CRITICAL: product_schema.json 로드/검증 실패: {e}")
                passed = False
                schema = None

        # 6. AI 품질 검사 (점수 >= 75 통과). 미달 시 quality_report.json 저장 → 자동 개선 사이클에서 활용 가능
        if passed and schema is not None:
            try:
                quality_result = run_quality_inspection(schema)
                qa_messages.append(
                    f"AI 품질 점수: {quality_result.score}/100 (임계값 75)"
                )
                # 품질 결과를 파일로 저장 (개선 사이클 또는 수동 개선 시 참고)
                quality_report_path = os.path.join(output_dir, "quality_report.json")
                write_json(quality_report_path, quality_result.to_dict())
                if not quality_result.passed:
                    qa_messages.append(
                        f"ERROR: AI 품질 점수 미달. 결함: {quality_result.defects}"
                    )
                    passed = False
                else:
                    qa_messages.append("SUCCESS: AI 품질 검사 통과.")
            except Exception as e:
                logger.error(f"AI 품질 검사 필수 정책 위반/오류: {e}")
                qa_messages.append(f"CRITICAL: AI 품질 검사 실패. AI 참여 필수 정책에 따라 QA 불합격 처리합니다. 오류: {e}")
                passed = False


        if passed:
            logger.info(f"QA Stage 1 성공 - 제품 ID: {product_id}")
        else:
            logger.warning(
                f"QA Stage 1 실패 - 제품 ID: {product_id}, 사유: {qa_messages}"
            )

        return QAResult(passed, "QA Stage 1", product_id, qa_messages)

    @handle_errors(stage="QA Stage 2")
    def run_qa_stage_2(
        self, product_id: str, package_path: str, download_url: str = None
    ) -> QAResult:
#         """2단계 QA (배송 게이트)를 실행합니다."""
        logger.info(
            f"QA Stage 2 시작 - 제품 ID: {product_id}, 패키지 경로: {package_path}"
        )
        qa_messages = []
        passed = True

        # 1. Deliverable ZIP 파일 존재 여부 확인
        if not os.path.exists(package_path):
            qa_messages.append(
                f"CRITICAL: 패키지 ZIP 파일이 존재하지 않습니다: {package_path}"
            )
            passed = False
        elif not os.path.isfile(package_path):
            qa_messages.append(
                f"CRITICAL: 패키지 경로가 파일이 아닙니다: {package_path}"
            )
            passed = False
        else:
            qa_messages.append("SUCCESS: 패키지 ZIP 파일이 존재합니다.")

        if not passed:
            logger.warning(
                f"QA Stage 2 실패 (ZIP 파일 없음/읽기 불가) - 제품 ID: {product_id}"
            )
            return QAResult(False, "QA Stage 2", product_id, qa_messages)

        # 2. ZIP 파일 내부 검사 (필수 파일 포함 여부)
        expected_zip_contents = [
            f"{product_id}/index.html",
            f"{product_id}/generation_report.json",
            f"{product_id}/product_schema.json",
            f"{product_id}/README.md",
            f"{product_id}/LICENSE.md",
        ]
        try:
            with zipfile.ZipFile(package_path, "r") as zip_ref:
                actual_contents = zip_ref.namelist()
                for expected_file in expected_zip_contents:
                    if expected_file not in actual_contents:
                        qa_messages.append(
                            f"ERROR: ZIP 파일에 필수 파일이 누락되었습니다: {expected_file}"
                        )
                        passed = False
                    else:
                        qa_messages.append(
                            f"SUCCESS: ZIP 파일에 필수 파일이 존재합니다: {expected_file}"
                        )
            if passed:
                qa_messages.append("SUCCESS: ZIP 파일 내부 검사를 통과했습니다.")
            else:
                qa_messages.append("ERROR: ZIP 파일 내부 검사에 실패했습니다.")
        except zipfile.BadZipFile:
            qa_messages.append(f"CRITICAL: 손상된 ZIP 파일입니다: {package_path}")
            passed = False
        except Exception as e:
            qa_messages.append(f"CRITICAL: ZIP 파일 내부 검사 중 오류 발생: {e}")
            passed = False

        # 3. 다운로드 엔드포인트 실제 서비스 가능 여부
        if download_url:
            try:
                response = requests.head(
                    download_url, timeout=5
                )  # HEAD 요청으로 파일 존재 여부만 확인
                if response.status_code == 200:
                    qa_messages.append(
                        f"SUCCESS: 다운로드 엔드포인트가 정상적으로 작동합니다: {download_url}"
                    )
                else:
                    qa_messages.append(
                        f"ERROR: 다운로드 엔드포인트 접근 실패 - 상태 코드: {response.status_code}, URL: {download_url}"
                    )
                    passed = False
            except requests.exceptions.RequestException as e:
                qa_messages.append(
                    f"CRITICAL: 다운로드 엔드포인트 연결 실패: {download_url}, 오류: {e}"
                )
                passed = False
        else:
            qa_messages.append(
                "INFO: 다운로드 URL이 제공되지 않아 엔드포인트 검사를 건너_ensure_parent_dir"
            )

        # 4. 메타데이터와 패키징된 아티팩트 일치 여부 (LedgerManager와 연동)
        try:
            product_info = self.ledger_manager.get_product(product_id)
            if product_info:
                ledger_checksum = product_info.get("checksum")
                actual_package_checksum = calculate_file_checksum(package_path)

                if ledger_checksum and ledger_checksum == actual_package_checksum:
                    qa_messages.append(
                        "SUCCESS: 원장 메타데이터의 체크섬과 실제 패키지 체크섬이 일치합니다."
                    )
                else:
                    qa_messages.append(
                        f"ERROR: 체크섬 불일치. 원장: {ledger_checksum}, 실제: {actual_package_checksum}"
                    )
                    passed = False
            else:
                qa_messages.append(
                    f"ERROR: 원장에서 제품 정보를 찾을 수 없어 메타데이터 검증 불가: {product_id}"
                )
                passed = False
        except ProductionError as e:
            qa_messages.append(f"CRITICAL: 원장 조회 중 오류 발생: {e.message}")
            passed = False
        except Exception as e:
            qa_messages.append(
                f"CRITICAL: 메타데이터 검증 중 예기치 않은 오류 발생: {e}"
            )
            passed = False

        if passed:
            logger.info(f"QA Stage 2 성공 - 제품 ID: {product_id}")
        else:
            logger.warning(
                f"QA Stage 2 실패 - 제품 ID: {product_id}, 사유: {qa_messages}"
            )

        return QAResult(passed, "QA Stage 2", product_id, qa_messages)


# -----------------------------
# 로컬 단독 실행 테스트 (선택 사항)
# -----------------------------

if __name__ == "__main__":
    logger.info("QAManager 모듈 로컬 테스트 시작")

    # 테스트를 위한 가짜 제품 출력 디렉토리 생성
    test_product_id = "test-qa-product-001"
    test_output_dir = os.path.join(Config.OUTPUT_DIR, test_product_id)
    os.makedirs(test_output_dir, exist_ok=True)

    # 테스트용 index.html 파일 생성
    valid_html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Test Product</title>
    </head>
    <body>
      <div class="hero">Hero Section</div>
      <section id="features">Features Section</section>
      <section id="pricing">Pricing Section</section>
      <section id="faq">FAQ Section</section>
      <button data-action="open-plans" class="btn-primary">CTA Button</button>
      <a href="/valid-link">Valid Link</a>
      <img src="/valid-image.png">
    </body>
    </html>
    """
    invalid_html_missing_section = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Test Product</title>
    </head>
    <body>
      <div class="hero">Hero Section</div>
    </body>
    </html>
    """
    invalid_html_broken_link = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Test Product</title>
    </head>
    <body>
      <div class="hero">Hero Section</div>
      <a href="">Broken Link</a>
    </body>
    </html>
    """

    qa_manager = QAManager()

    # 유효한 HTML 테스트
    valid_html_path = os.path.join(test_output_dir, "index.html")
    with open(valid_html_path, "w", encoding="utf-8") as f:
        f.write(valid_html_content)
    logger.info(f"\n--- QA Stage 1 테스트: 유효한 HTML ({valid_html_path}) ---")
    result_valid = qa_manager.run_qa_stage_1(test_product_id, test_output_dir)
    logger.info(f"결과: {result_valid.passed}, 메시지: {result_valid.messages}")

    # 섹션 누락된 HTML 테스트
    invalid_section_html_path = os.path.join(test_output_dir, "index.html")
    with open(invalid_section_html_path, "w", encoding="utf-8") as f:
        f.write(invalid_html_missing_section)
    logger.info(
        f"\n--- QA Stage 1 테스트: 섹션 누락 HTML ({invalid_section_html_path}) ---"
    )
    result_missing = qa_manager.run_qa_stage_1(test_product_id, test_output_dir)
    logger.info(f"결과: {result_missing.passed}, 메시지: {result_missing.messages}")

    # 깨진 링크 HTML 테스트
    invalid_link_html_path = os.path.join(test_output_dir, "index.html")
    with open(invalid_link_html_path, "w", encoding="utf-8") as f:
        f.write(invalid_html_broken_link)
    logger.info(
        f"\n--- QA Stage 1 테스트: 깨진 링크 HTML ({invalid_link_html_path}) ---"
    )
    result_broken_link = qa_manager.run_qa_stage_1(test_product_id, test_output_dir)
    logger.info(
        f"결과: {result_broken_link.passed}, 메시지: {result_broken_link.messages}"
    )

    # QA Stage 2 테스트 (더미 패키지 경로)
    dummy_package_path = os.path.join(Config.DOWNLOAD_DIR, f"{test_product_id}.zip")
    # 가짜 ZIP 파일 생성 (실제 내용은 없지만 파일 존재는 확인)
    ensure_parent_dir(dummy_package_path)
    with open(dummy_package_path, "w") as f:
        f.write("dummy zip content")

    logger.info(f"\n--- QA Stage 2 테스트: 더미 패키지 ({dummy_package_path}) ---")
    result_qa2 = qa_manager.run_qa_stage_2(test_product_id, dummy_package_path)
    logger.info(f"결과: {result_qa2.passed}, 메시지: {result_qa2.messages}")

    # 테스트 후 생성된 파일 정리 (선택 사항)
    # import shutil
    # shutil.rmtree(test_output_dir)
    # os.remove(dummy_package_path)

    logger.info("QAManager 모듈 로컬 테스트 완료")
