import sys
from pathlib import Path
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.ledger_manager import Order, Config

def check_orders():
    print("Checking orders...")
    engine = create_engine(Config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Count all orders
        total_orders = session.query(Order).count()
        print(f"Total orders: {total_orders}")
        
        # Count paid orders
        paid_orders = session.query(Order).filter(Order.status == 'PAID').count()
        print(f"Paid orders: {paid_orders}")
        
        # Calculate revenue
        revenue = session.query(func.sum(Order.amount)).filter(Order.status == 'PAID').scalar() or 0
        print(f"Total revenue: ${revenue}")
        
        # List recent orders
        orders = session.query(Order).order_by(Order.created_at.desc()).limit(5).all()
        for o in orders:
            print(f"ID: {o.id}, Product: {o.product_id}, Amount: {o.amount}, Status: {o.status}, Date: {o.created_at}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_orders()
