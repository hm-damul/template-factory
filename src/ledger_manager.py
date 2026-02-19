import json
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import Config
from .utils import ProductionError, get_logger, handle_errors

logger = get_logger(__name__)
Base = declarative_base()


class Product(Base):
    """제품 정보를 저장하는 데이터 모델"""

    __tablename__ = "products"
    id = Column(String, primary_key=True)  # 제품 고유 ID (예: UUID)
    topic = Column(String, nullable=False)  # 제품 주제
    status = Column(
        String, default="DRAFT"
    )  # 제품 상태 (DRAFT, QA1_FAILED, PACKAGED, QA2_FAILED, PUBLISHED)
    version = Column(String)  # 제품 버전
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    package_path = Column(String)  # 패키징된 ZIP 파일 경로
    checksum = Column(String)  # 패키지 파일 체크섬
    content_hash = Column(String)  # 콘텐츠 내용 해시 (중복 생성 방지용)
    metadata_json = Column(Text)  # 제품 메타데이터 (JSON 형태)

    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "package_path": self.package_path,
            "checksum": self.checksum,
            "content_hash": self.content_hash,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
        }


class Order(Base):
    """주문 정보를 저장하는 데이터 모델"""

    __tablename__ = "orders"
    id = Column(String, primary_key=True)  # 주문 고유 ID
    product_id = Column(String, nullable=False)  # 관련 제품 ID
    customer_email = Column(String, nullable=False)  # 구매자 이메일
    amount = Column(Integer, nullable=False)  # 결제 금액
    currency = Column(String, default="USD")  # 결제 통화
    status = Column(
        String, default="PENDING"
    )  # 주문 상태 (PENDING, PAID, FAILED, REFUNDED)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    payment_details_json = Column(Text)  # 결제 상세 정보 (JSON 형태)
    download_token = Column(String)  # 발급된 다운로드 토큰
    token_expiry = Column(DateTime)  # 토큰 만료 시간
    token_used = Column(Boolean, default=False)  # 토큰 사용 여부

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "customer_email": self.customer_email,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "payment_details": (
                json.loads(self.payment_details_json)
                if self.payment_details_json
                else {}
            ),
            "download_token": self.download_token,
            "token_expiry": (
                self.token_expiry.isoformat() if self.token_expiry else None
            ),
            "token_used": self.token_used,
        }


class Download(Base):
    """다운로드 이력을 저장하는 데이터 모델"""

    __tablename__ = "downloads"
    id = Column(String, primary_key=True)  # 다운로드 고유 ID
    order_id = Column(String, nullable=False)  # 관련 주문 ID
    product_id = Column(String, nullable=False)  # 관련 제품 ID
    download_time = Column(DateTime, default=datetime.now)
    ip_address = Column(String)  # 다운로드 요청 IP 주소
    user_agent = Column(Text)  # 사용자 에이전트 정보
    token_used = Column(String)  # 사용된 다운로드 토큰

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "download_time": (
                self.download_time.isoformat() if self.download_time else None
            ),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "token_used": self.token_used,
        }


class LedgerManager:
    """제품 생산 파이프라인의 모든 상태와 이력을 관리하는 원장 매니저"""

    def __init__(self, database_url=Config.DATABASE_URL):
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)  # DB 스키마 생성
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"LedgerManager 초기화 완료. 데이터베이스: {database_url}")

    @handle_errors(stage="Ledger Initialization")
    def get_session(self):
        """새로운 DB 세션을 반환합니다."""
        return self.Session()

    @handle_errors(stage="Ledger Query")
    def get_all_topics(self):
        """지금까지 생성된 모든 상품의 주제 목록을 반환합니다."""
        session = self.get_session()
        try:
            topics = session.query(Product.topic).distinct().all()
            return [t[0] for t in topics]
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_product(self, product_id: str):
        """특정 ID의 제품 정보를 가져옵니다."""
        session = self.get_session()
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            return product.to_dict() if product else None
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_recent_products(self, limit: int = 3):
        session = self.get_session()
        try:
            products = (
                session.query(Product)
                .order_by(Product.created_at.desc())
                .limit(limit)
                .all()
            )
            return [p.to_dict() for p in products]
        finally:
            session.close()

    def get_product_by_topic(self, topic: str):
        """특정 주제의 제품 정보를 가져옵니다 (가장 최근 것)."""
        session = self.get_session()
        try:
            product = (
                session.query(Product)
                .filter_by(topic=topic)
                .order_by(Product.created_at.desc())
                .first()
            )
            return product.to_dict() if product else None
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_product_by_hash(self, content_hash: str):
        """특정 콘텐츠 해시의 제품 정보를 가져옵니다."""
        session = self.get_session()
        try:
            product = session.query(Product).filter_by(content_hash=content_hash).first()
            return product.to_dict() if product else None
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def create_product(self, product_id: str, topic: str, metadata: dict = None, content_hash: str = None):
        """새 제품을 원장에 기록합니다. 이미 존재하는 경우 정보를 업데이트합니다 (Upsert)."""
        session = self.get_session()
        try:
            # 기존 제품 확인
            product = session.query(Product).filter(Product.id == product_id).first()
            
            if product:
                logger.info(f"기존 제품 발견 - ID: {product_id}, 정보를 업데이트합니다.")
                product.topic = topic
                if content_hash:
                    product.content_hash = content_hash
                if metadata:
                    product.metadata_json = json.dumps(metadata)
                product.updated_at = datetime.now()
            else:
                product = Product(
                    id=product_id,
                    topic=topic,
                    content_hash=content_hash,
                    metadata_json=json.dumps(metadata) if metadata else "{}",
                )
                session.add(product)
            
            session.commit()
            logger.info(f"제품 정보 저장 완료 - ID: {product_id}, 주제: {topic}")
            return product.to_dict()
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"제품 정보 저장 실패: {e}",
                stage="Create Product",
                product_id=product_id,
                original_exception=e,
            )
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def update_product_status(
        self,
        product_id: str,
        status: str,
        package_path: str = None,
        checksum: str = None,
        content_hash: str = None,
        version: str = None,
        metadata: dict = None,
    ):
        """제품 상태 및 관련 정보를 업데이트합니다."""
        session = self.get_session()
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ProductionError(
                    f"제품을 찾을 수 없습니다 - ID: {product_id}",
                    stage="Update Product Status",
                    product_id=product_id,
                )

            product.status = status
            if package_path:
                product.package_path = package_path
            if checksum:
                product.checksum = checksum
            if content_hash:
                product.content_hash = content_hash
            if version:
                product.version = version
            if metadata:
                current_meta = (
                    json.loads(product.metadata_json) if product.metadata_json else {}
                )
                current_meta.update(metadata)
                product.metadata_json = json.dumps(current_meta)
            product.updated_at = datetime.now()

            session.commit()
            logger.info(f"제품 상태 업데이트 - ID: {product_id}, 새 상태: {status}")
            return product.to_dict()
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"제품 상태 업데이트 실패: {e}",
                stage="Update Product Status",
                product_id=product_id,
                original_exception=e,
            )
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def update_product(self, product_id: str, **kwargs):
        """제품 정보를 일반적인 방식으로 업데이트합니다."""
        session = self.get_session()
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ProductionError(f"제품을 찾을 수 없습니다: {product_id}")

            for key, value in kwargs.items():
                if key == "metadata":
                    current_meta = (
                        json.loads(product.metadata_json) if product.metadata_json else {}
                    )
                    current_meta.update(value)
                    product.metadata_json = json.dumps(current_meta)
                elif hasattr(product, key):
                    setattr(product, key, value)

            product.updated_at = datetime.now()
            session.commit()
            return product.to_dict()
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_product(self, product_id: str):
        """제품 ID로 제품 정보를 조회합니다."""
        session = self.get_session()
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            return product.to_dict() if product else None
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_all_products(self):
        """모든 제품 정보를 조회합니다."""
        session = self.get_session()
        try:
            products = session.query(Product).all()
            return [p.to_dict() for p in products]
        finally:
            session.close()

    @handle_errors(stage="Order Management")
    def create_order(
        self,
        order_id: str,
        product_id: str,
        customer_email: str,
        amount: int,
        currency: str = "USD",
        payment_details: dict = None,
    ):
#         """새 주문을 원장에 기록합니다."""
        session = self.get_session()
        try:
            order = Order(
                id=order_id,
                product_id=product_id,
                customer_email=customer_email,
                amount=amount,
                currency=currency,
                payment_details_json=(
                    json.dumps(payment_details) if payment_details else "{}"
                ),
            )
            session.add(order)
            session.commit()
            logger.info(
                f"주문 생성 - ID: {order_id}, 제품 ID: {product_id}, 이메일: {customer_email}"
            )
            return order.to_dict()
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"주문 생성 실패: {e}", stage="Create Order", original_exception=e
            )
        finally:
            session.close()

    @handle_errors(stage="Order Management")
    def update_order_status(
        self,
        order_id: str,
        status: str,
        download_token: str = None,
        token_expiry: datetime = None,
        token_used: bool = None,
    ):
#         """주문 상태 및 다운로드 토큰 정보를 업데이트합니다."""
        session = self.get_session()
        try:
            order = session.query(Order).filter_by(id=order_id).first()
            if not order:
                raise ProductionError(
                    f"주문을 찾을 수 없습니다 - ID: {order_id}",
                    stage="Update Order Status",
                )

            order.status = status
            if download_token:
                order.download_token = download_token
            if token_expiry:
                order.token_expiry = token_expiry
            if token_used is not None:
                order.token_used = token_used
            order.updated_at = datetime.now()

            session.commit()
            logger.info(f"주문 상태 업데이트 - ID: {order_id}, 새 상태: {status}")
            return order.to_dict()
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"주문 상태 업데이트 실패: {e}",
                stage="Update Order Status",
                original_exception=e,
            )
        finally:
            session.close()

    @handle_errors(stage="Order Management")
    def get_order(self, order_id: str):
        """주문 ID로 주문 정보를 조회합니다."""
        session = self.get_session()
        try:
            order = session.query(Order).filter_by(id=order_id).first()
            return order.to_dict() if order else None
        finally:
            session.close()

    @handle_errors(stage="Order Management")
    def get_orders_by_product_id(self, product_id: str):
        """제품 ID로 모든 주문 정보를 조회합니다."""
        session = self.get_session()
        try:
            orders = session.query(Order).filter_by(product_id=product_id).all()
            return [order.to_dict() for order in orders]
        finally:
            session.close()

    @handle_errors(stage="Download Management")
    def record_download(
        self,
        download_id: str,
        order_id: str,
        product_id: str,
        ip_address: str,
        user_agent: str,
        token_used: str,
    ):
#         """다운로드 이력을 원장에 기록합니다."""
        session = self.get_session()
        try:
            download = Download(
                id=download_id,
                order_id=order_id,
                product_id=product_id,
                ip_address=ip_address,
                user_agent=user_agent,
                token_used=token_used,
            )
            session.add(download)
            session.commit()
            logger.info(
                f"다운로드 기록 - ID: {download_id}, 주문 ID: {order_id}, 제품 ID: {product_id}"
            )
            return download.to_dict()
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"다운로드 기록 실패: {e}",
                stage="Record Download",
                original_exception=e,
            )
        finally:
            session.close()

    @handle_errors(stage="Download Management")
    def get_downloads_by_product_id(self, product_id: str):
        """제품 ID로 모든 다운로드 이력을 조회합니다."""
        session = self.get_session()
        try:
            downloads = session.query(Download).filter_by(product_id=product_id).all()
            return [download.to_dict() for download in downloads]
        finally:
            session.close()

    @handle_errors(stage="Download Management")
    def get_downloads_by_order_id(self, order_id: str):
        """주문 ID로 모든 다운로드 이력을 조회합니다."""
        session = self.get_session()
        try:
            downloads = session.query(Download).filter_by(order_id=order_id).all()
            return [d.to_dict() for d in downloads]
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def list_products(self, limit: int = 100, offset: int = 0):
        """전체 제품 목록을 조회합니다."""
        session = self.get_session()
        try:
            products = (
                session.query(Product)
                .order_by(Product.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [p.to_dict() for p in products]
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def get_products_by_status(self, status: str, limit: int = 100):
        """특정 상태의 제품 목록을 조회합니다."""
        session = self.get_session()
        try:
            products = (
                session.query(Product)
                .filter_by(status=status)
                .order_by(Product.created_at.desc())
                .limit(limit)
                .all()
            )
            return [p.to_dict() for p in products]
        finally:
            session.close()

    @handle_errors(stage="Product Management")
    def delete_product_record(self, product_id: str):
        """제품 ID로 제품 레코드를 원장에서 삭제합니다. 관련 주문 및 다운로드 기록도 삭제합니다."""
        session = self.get_session()
        try:
            # 관련 다운로드 기록 삭제
            session.query(Download).filter_by(product_id=product_id).delete()
            # 관련 주문 기록 삭제
            session.query(Order).filter_by(product_id=product_id).delete()
            # 제품 레코드 삭제
            product = session.query(Product).filter_by(id=product_id).first()
            if product:
                session.delete(product)
                session.commit()
                logger.info(f"제품 레코드 및 관련 데이터 삭제 완료 - ID: {product_id}")
                return {
                    "ok": True,
                    "message": f"Product {product_id} and related records deleted.",
                }
            else:
                session.rollback()
                raise ProductionError(
                    f"삭제할 제품을 찾을 수 없습니다 - ID: {product_id}",
                    stage="Delete Product Record",
                    product_id=product_id,
                )
        except Exception as e:
            session.rollback()
            raise ProductionError(
                f"제품 레코드 삭제 실패: {e}",
                stage="Delete Product Record",
                product_id=product_id,
                original_exception=e,
            )
        finally:
            session.close()
