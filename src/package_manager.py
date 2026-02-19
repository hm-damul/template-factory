import os
import shutil
from datetime import datetime
from typing import Any, Dict

from .config import Config
from .utils import (
    ProductionError,
    calculate_file_checksum,
    get_logger,
    handle_errors,
    retry_on_failure,
)

logger = get_logger(__name__)


class PackageManager:
    """제품 자산을 판매 가능한 형태로 패키징하는 클래스"""

    def __init__(self, download_root_dir: str = Config.DOWNLOAD_DIR):
        self.download_root_dir = download_root_dir
        os.makedirs(self.download_root_dir, exist_ok=True)
        logger.info(
            f"PackageManager 초기화 완료. 다운로드 루트 디렉토리: {self.download_root_dir}"
        )

    def _generate_version(self, product_id: str) -> str:
        """제품 버전을 생성합니다 (예: product_id-YYYYMMDD-HHMMSS)."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{product_id}-{timestamp}"

    def _create_dummy_file(self, target_dir: str, filename: str, content: str):
        """더미 파일을 생성합니다."""
        filepath = os.path.join(target_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(f"더미 파일 생성: {filepath}")
            return filepath
        except Exception as e:
            raise ProductionError(
                f"더미 파일 생성 실패: {filepath}, 오류: {e}", stage="Package Manager"
            )

    @handle_errors(stage="Package")
    @retry_on_failure(max_retries=2)
    def package_product(
        self, product_id: str, product_output_dir: str
    ) -> Dict[str, Any]:
#         """제품 자산을 ZIP 파일로 패키징하고 메타데이터를 생성합니다."""
        logger.info(
            f"제품 패키징 시작 - 제품 ID: {product_id}, 소스 디렉토리: {product_output_dir}"
        )

        if not os.path.isdir(product_output_dir):
            raise ProductionError(
                f"제품 출력 디렉토리가 존재하지 않습니다: {product_output_dir}",
                stage="Package",
                product_id=product_id,
            )

        # 패키징을 위한 임시 디렉토리 생성
        temp_package_dir = os.path.join(
            self.download_root_dir, f"temp_{product_id}_package"
        )
        os.makedirs(temp_package_dir, exist_ok=True)

        # 원본 제품 자산 복사
        try:
            # product_output_dir의 내용을 temp_package_dir/product_id_content로 복사
            # 이렇게 하면 ZIP 파일 내부에 불필요한 상위 디렉토리 없이 실제 콘텐츠가 바로 들어감
            final_content_dir = os.path.join(
                temp_package_dir, product_id
            )  # ZIP 내부의 최상위 폴더명
            shutil.copytree(product_output_dir, final_content_dir, dirs_exist_ok=True)
            logger.info(
                f"제품 자산 복사 완료: {product_output_dir} -> {final_content_dir}"
            )
        except Exception as e:
            shutil.rmtree(temp_package_dir, ignore_errors=True)
            raise ProductionError(
                f"제품 자산 복사 실패: {e}", stage="Package", product_id=product_id
            )

        # 필수 추가 파일 생성 (README, LICENSE 등 - 현재는 더미)
        readme_content = f"# {product_id} - 디지털 제품\n\n이것은 {product_id} 주제로 생성된 디지털 제품입니다.\n\n## 포함된 파일\n- `index.html`: 메인 랜딩 페이지\n- `generation_report.json`: 제품 생성 보고서\n\n## 사용 방법\n`index.html` 파일을 웹 브라우저에서 직접 열어보세요.\n\n## 지원\n문의 사항은 `support@example.com`으로 연락주세요.\n"
        license_content = "MIT License\n\nCopyright (c) 2026 {product_id}\n\nPermission is hereby granted...\n"  # 실제 라이선스 텍스트로 대체

        _ = self._create_dummy_file(final_content_dir, "README.md", readme_content)
        _ = self._create_dummy_file(final_content_dir, "LICENSE.md", license_content)

        # ZIP 파일 생성 경로 및 이름
        version = self._generate_version(product_id)
        zip_filename = f"{version}.zip"
        zip_filepath_base = os.path.join(self.download_root_dir, version)  # 확장자 제외

        try:
            # shutil.make_archive는 지정된 소스 디렉토리의 내용을 .zip으로 압축
            # base_dir이 temp_package_dir이면, ZIP 파일 안에 temp_product_package가 통째로 들어감
            # base_dir이 final_content_dir이면, ZIP 파일 안에 product_id가 통째로 들어감
            # root_dir을 download_root_dir로 하고 base_dir을 product_id로 하면,
            # download_root_dir/temp_product_package/product_id/ -> product_id/ 내의 파일들이 압축됨
            package_path = shutil.make_archive(
                zip_filepath_base, "zip", root_dir=temp_package_dir, base_dir=product_id
            )
            logger.info(f"제품 ZIP 파일 생성 완료: {package_path}")

            # 대시보드 연동을 위해 product_output_dir에 package.zip으로 복사
            dashboard_package_path = os.path.join(product_output_dir, "package.zip")
            shutil.copy2(package_path, dashboard_package_path)
            logger.info(f"대시보드용 package.zip 복사 완료: {dashboard_package_path}")

        except Exception as e:
            raise ProductionError(
                f"제품 ZIP 파일 생성 실패: {e}", stage="Package", product_id=product_id
            )
        finally:
            # 임시 디렉토리 정리
            shutil.rmtree(temp_package_dir, ignore_errors=True)
            logger.debug(f"임시 패키지 디렉토리 정리 완료: {temp_package_dir}")

        # ZIP 파일 체크섬 계산
        package_checksum = calculate_file_checksum(package_path)

        # dashboard_server.py 호환을 위해 product_output_dir에 package.zip으로 복사
        try:
            target_package_path = os.path.join(product_output_dir, "package.zip")
            shutil.copy2(package_path, target_package_path)
            logger.info(f"대시보드 호환용 package.zip 복사 완료: {target_package_path}")
            
            # 상위 디렉토리(outputs/<product_id>)에도 복사하여 확실히 접근 가능하게 함
            # product_output_dir이 이미 outputs/<product_id>인 경우도 있으므로 체크
            parent_dir = os.path.dirname(product_output_dir)
            if os.path.basename(parent_dir) == "outputs":
                 # 이미 올바른 위치
                 pass
            else:
                 # outputs/<product_id> 위치를 찾아서 복사
                 # Config.OUTPUT_DIR/product_id
                 target_root_package = os.path.join(Config.OUTPUT_DIR, product_id, "package.zip")
                 if target_root_package != target_package_path:
                     os.makedirs(os.path.dirname(target_root_package), exist_ok=True)
                     shutil.copy2(package_path, target_root_package)
                     logger.info(f"outputs 루트에 package.zip 복사 완료: {target_root_package}")

            # 3. downloads/product_id.zip으로 복사 (Vercel 정적 호스팅용)
            static_download_path = os.path.join(self.download_root_dir, f"{product_id}.zip")
            shutil.copy2(package_path, static_download_path)
            logger.info(f"Vercel 정적 호스팅용 zip 복사 완료: {static_download_path}")

        except Exception as e:
            logger.error(f"package.zip 복사 실패: {e}")
            # 이 복사는 부가적인 작업이므로 실패해도 전체 프로세스를 중단하지는 않음

        logger.info(
            f"제품 패키징 완료 - 제품 ID: {product_id}, 패키지 경로: {package_path}, 체크섬: {package_checksum}"
        )
        return {
            "ok": True,
            "product_id": product_id,
            "version": version,
            "package_path": package_path,
            "checksum": package_checksum,
            "packaged_at": datetime.now().isoformat(),
        }


# -----------------------------
# 로컬 단독 실행 테스트 (선택 사항)
# -----------------------------

if __name__ == "__main__":
    logger.info("PackageManager 모듈 로컬 테스트 시작")

    # 테스트를 위한 더미 제품 출력 디렉토리 생성
    test_product_id = "test-package-product-001"
    test_output_dir = os.path.join(Config.OUTPUT_DIR, test_product_id)
    test_download_dir = Config.DOWNLOAD_DIR

    os.makedirs(test_output_dir, exist_ok=True)
    os.makedirs(test_download_dir, exist_ok=True)

    # 테스트용 index.html 파일 생성
    test_html_content = """
    <!doctype html>
    <html lang="en">
    <head><title>Test Package Product</title></head>
    <body><h1>Hello from Test Package!</h1></body>
    </html>
    """
    with open(os.path.join(test_output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(test_html_content)
    with open(
        os.path.join(test_output_dir, "generation_report.json"), "w", encoding="utf-8"
    ) as f:
        json.dump({"status": "GENERATED_SUCCESS"}, f)

    package_manager = PackageManager()

    try:
        package_result = package_manager.package_product(
            test_product_id, test_output_dir
        )
        logger.info("패키징 결과:")
        logger.info(json.dumps(package_result, ensure_ascii=False, indent=2))

        # 생성된 ZIP 파일 확인
        if os.path.exists(package_result["package_path"]):
            logger.info(
                f"ZIP 파일이 성공적으로 생성되었습니다: {package_result['package_path']}"
            )
        else:
            logger.error("ZIP 파일 생성 실패.")

    except ProductionError as pe:
        logger.error(f"생산 오류 발생: {pe.message}")
        if pe.original_exception:
            logger.error(f"원본 예외: {pe.original_exception}")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}")
    finally:
        # 테스트 후 생성된 파일 및 디렉토리 정리
        if os.path.exists(test_output_dir):
            shutil.rmtree(test_output_dir, ignore_errors=True)
            logger.info(f"테스트 출력 디렉토리 정리: {test_output_dir}")

        # 생성된 ZIP 파일도 정리
        # zip_file_to_clean = os.path.join(test_download_dir, f"{test_product_id}-*.zip") # 와일드카드 정리 필요
        # glob.glob을 사용하여 패턴 매칭되는 파일 찾아서 삭제 (여기서는 단순화)
        for f_name in os.listdir(test_download_dir):
            if f_name.startswith(test_product_id) and f_name.endswith(".zip"):
                os.remove(os.path.join(test_download_dir, f_name))
                logger.info(f"테스트 ZIP 파일 정리: {f_name}")

    logger.info("PackageManager 모듈 로컬 테스트 완료")
