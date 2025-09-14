from __future__ import annotations

import os
import random
from typing import List

from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    UniqueConstraint,
    create_engine,
    Column
)
from sqlalchemy.orm import (
    declarative_base,  # <-- 1.4 way
    Mapped,
    relationship,
    sessionmaker,
)

# Make a Base the 1.4 way
Base = declarative_base()

# Reuse your existing fake data generators
from script.data_generators import (
    CustomerGenerator,
    AddressGenerator,
    ProductGenerator,
    InventoryGenerator,
    OrderGenerator,
    OrderItemGenerator,
    PaymentGenerator,
    ShipmentGenerator,
    compute_order_totals,
)

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/main",
)

class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = Column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = Column(String(200), nullable=False)
    phone: Mapped[str | None] = Column(String(40))

    addresses: Mapped[List["Address"]] = relationship(
        "Address", back_populates="customer", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="customer"
    )


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = Column(ForeignKey("customers.customer_id"), nullable=False)
    label: Mapped[str | None] = Column(String(50))
    line1: Mapped[str] = Column(String(200), nullable=False)
    line2: Mapped[str | None] = Column(String(200))
    city: Mapped[str] = Column(String(100), nullable=False)
    state: Mapped[str | None] = Column(String(100))
    postal_code: Mapped[str | None] = Column(String(20))
    country_code: Mapped[str] = Column(String(2), nullable=False)
    is_default: Mapped[bool] = Column(Boolean, nullable=False, default=False)

    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="addresses"
    )


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[str] = Column(String(64), unique=True, nullable=False)
    name: Mapped[str] = Column(String(200), nullable=False)
    price_cents: Mapped[int] = Column(Integer, nullable=False)
    active: Mapped[bool] = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_products_price_nonneg"),
    )

    inventory: Mapped["Inventory"] = relationship(
        "Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="product"
    )


class Inventory(Base):
    __tablename__ = "inventory"

    product_id: Mapped[int] = Column(ForeignKey("products.product_id"), primary_key=True)
    qty_on_hand: Mapped[int] = Column(Integer, nullable=False)
    qty_reserved: Mapped[int] = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("qty_on_hand >= 0", name="ck_inventory_on_hand_nonneg"),
        CheckConstraint("qty_reserved >= 0", name="ck_inventory_reserved_nonneg"),
    )

    product: Mapped["Product"] = relationship(
        "Product", back_populates="inventory"
    )


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = Column(ForeignKey("customers.customer_id"), nullable=False)
    ship_to_address_id: Mapped[int] = Column(ForeignKey("addresses.address_id"), nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False)
    currency: Mapped[str] = Column(String(3), nullable=False)
    subtotal_cents: Mapped[int] = Column(Integer, nullable=False)
    shipping_cents: Mapped[int] = Column(Integer, nullable=False)
    tax_cents: Mapped[int] = Column(Integer, nullable=False)
    total_cents: Mapped[int] = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_orders_subtotal_nonneg"),
        CheckConstraint("shipping_cents >= 0", name="ck_orders_shipping_nonneg"),
        CheckConstraint("tax_cents >= 0", name="ck_orders_tax_nonneg"),
        CheckConstraint("total_cents >= 0", name="ck_orders_total_nonneg"),
        CheckConstraint("status in ('PLACED','PAID','FULFILLED','CANCELED')", name="ck_orders_status"),
    )

    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="orders"
    )
    address: Mapped["Address"] = relationship("Address")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan"
    )
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    order_id: Mapped[int] = Column(ForeignKey("orders.order_id"), primary_key=True)
    product_id: Mapped[int] = Column(ForeignKey("products.product_id"), primary_key=True)
    qty: Mapped[int] = Column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_items_qty_positive"),
        CheckConstraint("unit_price_cents >= 0", name="ck_order_items_price_nonneg"),
    )

    order: Mapped["Order"] = relationship(
        "Order", back_populates="items"
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="order_items"
    )


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.order_id"), nullable=False)
    provider: Mapped[str] = Column(String(40), nullable=False)
    provider_ref: Mapped[str] = Column(String(100), nullable=False)
    amount_cents: Mapped[int] = Column(Integer, nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_ref", name="uq_payments_provider_ref"),
        CheckConstraint("amount_cents >= 0", name="ck_payments_amount_nonneg"),
        CheckConstraint("status in ('AUTHORIZED','CAPTURED','REFUNDED','FAILED')", name="ck_payments_status"),
    )

    order: Mapped["Order"] = relationship(
        "Order", back_populates="payments"
    )


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[int] = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.order_id"), nullable=False)
    carrier: Mapped[str | None] = Column(String(40))
    tracking_no: Mapped[str | None] = Column(String(80))
    status: Mapped[str] = Column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('READY','IN_TRANSIT','DELIVERED')", name="ck_shipments_status"),
    )

    order: Mapped["Order"] = relationship(
        "Order", back_populates="shipments"
    )


def get_engine(url: str | None = None):
    engine = create_engine(url or DEFAULT_DATABASE_URL, pool_pre_ping=True)
    return engine


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)

def create_schema(url: str | None = None) -> None:
    engine = get_engine(url)
    Base.metadata.create_all(engine)

def seed_sample(url: str | None = None, num_customers: int = 5, num_products: int = 10) -> None:
    engine = get_engine(url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        customer_gen = CustomerGenerator()
        address_gen = AddressGenerator()
        product_gen = ProductGenerator()
        inventory_gen = InventoryGenerator()
        order_gen = OrderGenerator()
        order_item_gen = OrderItemGenerator()
        payment_gen = PaymentGenerator()
        shipment_gen = ShipmentGenerator()

        # Products
        products: List[Product] = []
        for _ in range(num_products):
            pdata = product_gen.generate()
            p = Product(**pdata)
            session.add(p)
            session.flush()  # get product_id
            inv_data = inventory_gen.generate(product_id=p.product_id)
            session.add(Inventory(**inv_data))
            products.append(p)

        # Customers and addresses
        customers: List[Customer] = []
        addresses: List[Address] = []
        for _ in range(num_customers):
            c = Customer(**customer_gen.generate())
            session.add(c)
            session.flush()
            for _ in range(random.randint(1, 2)):
                a = Address(**address_gen.generate(customer_id=c.customer_id))
                session.add(a)
                addresses.append(a)
            customers.append(c)

        session.flush()

        # Orders
        for c in customers:
            cust_addrs = [a for a in addresses if a.customer_id == c.customer_id]
            if not cust_addrs:
                continue
            ship_addr = cust_addrs[0]
            for _ in range(random.randint(0, 3)):
                o = Order(**order_gen.generate(customer_id=c.customer_id, ship_to_address_id=ship_addr.address_id))
                session.add(o)
                session.flush()
                items_for_order = []
                num_items = random.randint(1, 5)
                selected_products = random.sample(products, k=min(num_items, len(products)))
                for prod in selected_products:
                    item_data = order_item_gen.generate(
                        order_id=o.order_id,
                        product_id=prod.product_id,
                        unit_price_cents=prod.price_cents,
                    )
                    session.add(OrderItem(**item_data))
                    items_for_order.append(item_data)
                totals = compute_order_totals(items_for_order)
                o.subtotal_cents = totals["subtotal_cents"]
                o.shipping_cents = totals["shipping_cents"]
                o.tax_cents = totals["tax_cents"]
                o.total_cents = totals["total_cents"]

                if o.status in ("PAID", "FULFILLED"):
                    session.add(Payment(**payment_gen.generate(o.order_id, o.total_cents)))
                if o.status in ("PLACED", "PAID", "FULFILLED"):
                    session.add(Shipment(**shipment_gen.generate(o.order_id)))

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    create_schema()
    seed_sample()
