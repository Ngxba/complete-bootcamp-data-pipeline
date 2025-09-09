from __future__ import annotations

import argparse
import os
import random
import sys
import time
from typing import List, Tuple

# Allow running as a standalone script while importing sibling module
CURRENT_DIR = os.path.dirname(__file__)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from sqlalchemy.orm import sessionmaker

from db_sqlalchemy import get_engine, Address, Order


def load_customer_addresses(session) -> List[Tuple[int, int]]:
    rows = (
        session.query(Address.address_id, Address.customer_id)
        .order_by(Address.address_id)
        .all()
    )
    return [(addr_id, cust_id) for addr_id, cust_id in rows]


def insert_order(session, customer_id: int, ship_to_address_id: int) -> int:
    order = Order(
        customer_id=customer_id,
        ship_to_address_id=ship_to_address_id,
        status="PLACED",
        currency="USD",
        subtotal_cents=0,
        shipping_cents=0,
        tax_cents=0,
        total_cents=0,
    )
    session.add(order)
    session.flush()
    oid = order.order_id
    session.commit()
    return oid


def run_stream(database_url: str | None, interval_seconds: float, max_count: int | None) -> None:
    engine = get_engine(database_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        address_pairs = load_customer_addresses(session)
        if not address_pairs:
            print("No addresses found; ensure the database is seeded.")
            return

        count_inserted = 0
        while True:
            addr_id, cust_id = random.choice(address_pairs)
            order_id = insert_order(session, customer_id=cust_id, ship_to_address_id=addr_id)
            print(f"Inserted order_id={order_id} for customer_id={cust_id} ship_to_address_id={addr_id}")
            count_inserted += 1

            if max_count is not None and max_count > 0 and count_inserted >= max_count:
                break

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream new orders into the database.")
    parser.add_argument(
        "--url",
        dest="database_url",
        default=os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/main"),
        help="Database URL (defaults to env DATABASE_URL or library default)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Seconds between inserts (default: 3.0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of orders to insert (0 means run until interrupted)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    max_count = None if args.count == 0 else args.count
    run_stream(args.database_url, args.interval, max_count)


