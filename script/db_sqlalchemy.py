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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

# Reuse your existing fake data generators
from data_generators import (
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


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))

    addresses: Mapped[List["Address"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(50))
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customer: Mapped[Customer] = relationship(back_populates="addresses")


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_products_price_nonneg"),
    )

    inventory: Mapped["Inventory"] = relationship(back_populates="product", uselist=False, cascade="all, delete-orphan")
    order_items: Mapped[List["OrderItem"]] = relationship(back_populates="product")


class Inventory(Base):
    __tablename__ = "inventory"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("qty_on_hand >= 0", name="ck_inventory_on_hand_nonneg"),
        CheckConstraint("qty_reserved >= 0", name="ck_inventory_reserved_nonneg"),
    )

    product: Mapped[Product] = relationship(back_populates="inventory")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    ship_to_address_id: Mapped[int] = mapped_column(ForeignKey("addresses.address_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    shipping_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_orders_subtotal_nonneg"),
        CheckConstraint("shipping_cents >= 0", name="ck_orders_shipping_nonneg"),
        CheckConstraint("tax_cents >= 0", name="ck_orders_tax_nonneg"),
        CheckConstraint("total_cents >= 0", name="ck_orders_total_nonneg"),
        CheckConstraint("status in ('PLACED','PAID','FULFILLED','CANCELED')", name="ck_orders_status"),
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    address: Mapped[Address] = relationship()
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    shipments: Mapped[List["Shipment"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_items_qty_positive"),
        CheckConstraint("unit_price_cents >= 0", name="ck_order_items_price_nonneg"),
    )

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_ref", name="uq_payments_provider_ref"),
        CheckConstraint("amount_cents >= 0", name="ck_payments_amount_nonneg"),
        CheckConstraint("status in ('AUTHORIZED','CAPTURED','REFUNDED','FAILED')", name="ck_payments_status"),
    )

    order: Mapped[Order] = relationship(back_populates="payments")


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id"), nullable=False)
    carrier: Mapped[str | None] = mapped_column(String(40))
    tracking_no: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('READY','IN_TRANSIT','DELIVERED')", name="ck_shipments_status"),
    )

    order: Mapped[Order] = relationship(back_populates="shipments")


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
            # 1-2 addresses
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
    # Create tables (no-op if already exist) and seed a small dataset
    create_schema()
    seed_sample()


